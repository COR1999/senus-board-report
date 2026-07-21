"""
Investor-relations filing sync: filings on Senus's own investor-relations
API not yet in this system, and the "hide/unhide" out-of-scope list for a
non-financial filing a human has already reviewed and dismissed. See the
root README's "Investor relations API" section.
"""
import logging
from typing import List

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import require_admin
from app.models.document import Document
from app.models.hidden_external_filing import HiddenExternalFiling
from app.schemas.financial import DocumentWithText, ExternalFilingSummary
from app.services import investor_relations_client

from . import _ingest_document, router

logger = logging.getLogger(__name__)


@router.get("/external/available", response_model=List[ExternalFilingSummary])
async def list_available_external_filings(db: AsyncSession = Depends(get_db)):
    """
    Filings on Senus's investor relations API not yet in this system.
    Read-only -- doesn't download or ingest anything, just compares
    metadata so the frontend can show an "import?" prompt.
    """
    try:
        filings = await investor_relations_client.list_available_filings()
    except Exception as e:
        logger.error(f"Failed to reach investor relations API: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail="Could not reach the investor relations API")

    existing = await db.execute(select(Document.external_attachment_id, Document.filename))
    known_attachment_ids = set()
    known_filenames = set()
    for attachment_id, filename in existing.all():
        if attachment_id:
            known_attachment_ids.add(attachment_id)
        known_filenames.add(filename)

    hidden = await db.execute(select(HiddenExternalFiling.attachment_id))
    hidden_attachment_ids = {row[0] for row in hidden.all()}

    # Filtered by both attachment_id AND filename -- the real API has
    # already shown one edge case where the exact same filing (the
    # half-year results, manually uploaded here, so its
    # external_attachment_id is NULL) appears under two different
    # attachment_ids across different category listings. An
    # attachment_id-only check would wrongly flag it as "new" every time.
    # Also excludes anything the user has explicitly marked out of scope
    # (see /external/{attachment_id}/hide) -- a rejected import (422, low
    # confidence) creates no Document row by design, so without this
    # exclusion a governance filing the user has already reviewed and
    # dismissed would keep re-appearing here forever.
    return [
        ExternalFilingSummary(**f)
        for f in filings
        if f["attachment_id"] not in known_attachment_ids
        and f["file_name"] not in known_filenames
        and f["attachment_id"] not in hidden_attachment_ids
    ]


@router.get("/external/hidden", response_model=List[ExternalFilingSummary])
async def list_hidden_external_filings(db: AsyncSession = Depends(get_db)):
    """
    Filings the user has explicitly marked out of scope (see
    /external/{attachment_id}/hide) -- a secondary, out-of-the-way list so
    a dismissed non-financial filing (an AGM notice, Memo & Articles) can
    still be reviewed/restored later without permanently disappearing.
    """
    result = await db.execute(
        select(HiddenExternalFiling).order_by(HiddenExternalFiling.hidden_at.desc())
    )
    return [
        ExternalFilingSummary(
            attachment_id=row.attachment_id,
            file_name=row.file_name,
            file_size=row.file_size,
            published_date=row.published_date,
        )
        for row in result.scalars().all()
    ]


@router.post("/external/{attachment_id}/hide", response_model=ExternalFilingSummary, dependencies=[Depends(require_admin)])
async def hide_external_filing(attachment_id: str, db: AsyncSession = Depends(get_db)):
    """
    Marks a filing as out of scope so it stops cluttering "available
    filings" -- for a document with no extractable financial data (a
    governance filing, or one that failed the confidence gate) that the
    user has already reviewed and doesn't want to keep seeing. Idempotent:
    hiding an already-hidden filing just returns it unchanged.
    """
    existing = await db.execute(
        select(HiddenExternalFiling).where(HiddenExternalFiling.attachment_id == attachment_id)
    )
    row = existing.scalars().first()
    if row is not None:
        return ExternalFilingSummary(
            attachment_id=row.attachment_id, file_name=row.file_name,
            file_size=row.file_size, published_date=row.published_date,
        )

    filing = await investor_relations_client.find_filing(attachment_id)
    if filing is None:
        raise HTTPException(status_code=404, detail="Filing not found on the investor relations API")

    row = HiddenExternalFiling(
        attachment_id=filing["attachment_id"],
        file_name=filing["file_name"],
        file_size=filing.get("file_size"),
        published_date=filing.get("published_date"),
    )
    db.add(row)
    await db.commit()

    return ExternalFilingSummary(
        attachment_id=row.attachment_id, file_name=row.file_name,
        file_size=row.file_size, published_date=row.published_date,
    )


@router.post("/external/{attachment_id}/unhide", status_code=204, dependencies=[Depends(require_admin)])
async def unhide_external_filing(attachment_id: str, db: AsyncSession = Depends(get_db)):
    """Restores a hidden filing back to the "available" list. Idempotent."""
    existing = await db.execute(
        select(HiddenExternalFiling).where(HiddenExternalFiling.attachment_id == attachment_id)
    )
    row = existing.scalars().first()
    if row is not None:
        await db.delete(row)
        await db.commit()


@router.post("/external/{attachment_id}/import", response_model=DocumentWithText, dependencies=[Depends(require_admin)])
async def import_external_filing(attachment_id: str, db: AsyncSession = Depends(get_db)):
    try:
        filing = await investor_relations_client.find_filing(attachment_id)
        if filing is None:
            raise HTTPException(status_code=404, detail="Filing not found on the investor relations API")

        content = await investor_relations_client.download_filing(attachment_id)
        filename = filing["file_name"]
        if not filename.lower().endswith(".pdf"):
            filename = f"{filename}.pdf"

        return await _ingest_document(content, filename, db, external_attachment_id=attachment_id)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"External filing import failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Import failed")
