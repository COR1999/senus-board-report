"""
Same-period document merging.

Why this exists
----------------
A real production incident: ADF Farm Solutions' audited statements (vision-
extracted) and the Information Document (text-extracted) both genuinely
report FY2025 (Jul 2024 - Jun 2025) -- Senus's predecessor entity and the
Euronext listing prospectus describing the exact same underlying financial
year. Nothing previously stopped both from independently appearing in the
period selector with identical labels and no way to tell them apart, while
actually carrying different (complementary, not conflicting) figures --
one had EBITDA but no customer count, the other had customers but no
EBITDA, and every field they both reported (revenue, cash, margins) agreed
exactly.

This module detects that situation -- at ingest time for every new upload,
and via a one-off `reconcile_all_periods` sweep for documents that slipped
through before this existed -- and merges the two into a new, synthetic
"merged" Document/Report/FinancialMetrics triad (reusing those exact models,
not a new table) that becomes the one eligible entry for that period. Both
original documents are left completely untouched and independently visible/
downloadable -- only their `FinancialMetrics.superseded_by_document_id` gets
set, which the dashboard-eligibility filters in metrics.py already treat the
same way they treat any other excluded-but-real row.

A genuine conflict (both sources report the SAME field with DIFFERENT
values) is never silently resolved -- the merged row is tagged
`needs_review` with both candidate values and their source filenames named
in `extraction_confidence_reasons`, so a human confirms it via the existing
review panel (see documents.py's `approve_document`) exactly the way any
other needs_review document already works. Only a clean merge (every
shared field agrees, or one side simply didn't report it) reaches
`auto_accept` directly.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.report import Report
from app.models.financial_metrics import FinancialMetrics
from app.api.routes.metrics import _IS_CONFIDENT_ENOUGH_FOR_DASHBOARD

# The six core figures this project ever extracts -- see FinancialMetrics'
# own docstrings for what each means. Prior-period comparatives are merged
# too (gap-fill only, preferring whichever source has them) but aren't
# conflict-checked -- a disagreement there is much lower-stakes than on the
# current-period figures actually driving today's dashboard.
_MERGEABLE_FIELDS = ["revenue", "customers", "cash", "ebitda", "gross_margin", "operating_margin"]
_PRIOR_FALLBACK_FIELDS = [
    "revenue_prior", "cash_prior", "ebitda_prior", "gross_margin_prior", "operating_margin_prior",
    "reporting_period_start_prior", "reporting_period_end_prior", "reporting_period_prior",
]

# Two floats extracted independently (different OCR/parsing paths, possible
# rounding) are treated as "the same value" within this tolerance rather
# than flagged as a spurious conflict.
_FLOAT_TOLERANCE = 0.01


def _values_agree(a, b) -> bool:
    if isinstance(a, float) or isinstance(b, float):
        return abs(float(a) - float(b)) < _FLOAT_TOLERANCE
    return a == b


async def find_same_period_match(
    db: AsyncSession, new_row: FinancialMetrics
) -> Optional[FinancialMetrics]:
    """
    An existing, eligible (dashboard-worthy, not already superseded) row
    reporting the exact same calendar period as `new_row` -- `None` when
    either period label is unknown (never guessed into a false match) or no
    other document shares it.
    """
    if not new_row.reporting_period_start or not new_row.reporting_period_end:
        return None

    # `_IS_CONFIDENT_ENOUGH_FOR_DASHBOARD` already excludes a superseded row
    # (see its own docstring in metrics.py) -- not repeated here.
    stmt = select(FinancialMetrics).where(
        FinancialMetrics.reporting_period_start == new_row.reporting_period_start,
        FinancialMetrics.reporting_period_end == new_row.reporting_period_end,
        FinancialMetrics.document_id != new_row.document_id,
        _IS_CONFIDENT_ENOUGH_FOR_DASHBOARD,
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def merge_documents(
    db: AsyncSession, existing_row: FinancialMetrics, new_row: FinancialMetrics
) -> Document:
    """
    Merges `existing_row` (the previously-eligible, first-seen source) and
    `new_row` (the just-ingested one) into a new Document/Report/
    FinancialMetrics triad, marking both originals as superseded. On a
    genuine conflict, `existing_row`'s value is used provisionally and the
    disagreement is recorded for human review -- never silently resolved in
    favor of whichever extraction merely happened to run more recently.
    """
    existing_doc = await db.get(Document, existing_row.document_id)
    new_doc = await db.get(Document, new_row.document_id)

    merged_values = {}
    reasons: List[str] = []
    has_conflict = False

    for field in _MERGEABLE_FIELDS:
        existing_val = getattr(existing_row, field)
        new_val = getattr(new_row, field)
        if existing_val is None:
            merged_values[field] = new_val
        elif new_val is None or _values_agree(existing_val, new_val):
            merged_values[field] = existing_val
        else:
            has_conflict = True
            merged_values[field] = existing_val
            reasons.append(
                f"{field} conflicts between source documents: {existing_val} "
                f"({existing_doc.filename}) vs {new_val} ({new_doc.filename}) -- "
                f"using {existing_val} pending human confirmation."
            )

    prior_values = {
        field: getattr(existing_row, field) if getattr(existing_row, field) is not None else getattr(new_row, field)
        for field in _PRIOR_FALLBACK_FIELDS
    }

    period_label = existing_row.reporting_period_end or existing_row.reporting_period or "Unknown period"

    if not has_conflict:
        reasons.append(
            f"Merged from {existing_doc.filename} and {new_doc.filename} -- "
            "every field they both reported agreed, no conflicts found."
        )

    merged_document = Document(
        filename=f"{period_label} (merged: {existing_doc.filename} + {new_doc.filename})",
        file_path=None,
        status="completed",
        created_at=datetime.utcnow(),
        extracted_at=datetime.utcnow(),
    )
    db.add(merged_document)
    await db.flush()

    merged_report = Report(
        document_id=merged_document.id,
        status="completed",
        summary={
            "company_name": existing_doc.filename,
            "reporting_period": existing_row.reporting_period or new_row.reporting_period,
            "merged_from": [existing_row.document_id, new_row.document_id],
        },
        ai_commentary=(
            "This period's financial data was merged from two independently-extracted "
            "source documents reporting the same underlying filing period."
        ),
        generation_source="merged",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(merged_report)

    merged_metrics = FinancialMetrics(
        document_id=merged_document.id,
        revenue=merged_values["revenue"],
        customers=merged_values["customers"],
        cash=merged_values["cash"],
        ebitda=merged_values["ebitda"],
        gross_margin=merged_values["gross_margin"],
        operating_margin=merged_values["operating_margin"],
        revenue_prior=prior_values["revenue_prior"],
        cash_prior=prior_values["cash_prior"],
        ebitda_prior=prior_values["ebitda_prior"],
        gross_margin_prior=prior_values["gross_margin_prior"],
        operating_margin_prior=prior_values["operating_margin_prior"],
        reporting_period=existing_row.reporting_period or new_row.reporting_period,
        reporting_period_prior=prior_values["reporting_period_prior"],
        reporting_period_start=existing_row.reporting_period_start,
        reporting_period_end=existing_row.reporting_period_end,
        reporting_period_start_prior=prior_values["reporting_period_start_prior"],
        reporting_period_end_prior=prior_values["reporting_period_end_prior"],
        extraction_confidence=85.0 if has_conflict else 100.0,
        extraction_confidence_tier="needs_review" if has_conflict else "auto_accept",
        extraction_confidence_reasons=reasons,
        extracted_at=datetime.utcnow(),
    )
    db.add(merged_metrics)

    existing_row.superseded_by_document_id = merged_document.id
    new_row.superseded_by_document_id = merged_document.id

    await db.commit()
    await db.refresh(merged_document)
    return merged_document


async def reconcile_all_periods(db: AsyncSession) -> List[Document]:
    """
    One-off sweep for same-period duplicates that slipped through before
    `find_same_period_match` existed (or before a document's period fields
    were derivable at all -- see the vision-extraction cadence fix). Safe to
    call repeatedly: an already-superseded row is never re-matched, so a
    second call is a no-op. Returns the list of newly-created merged
    Documents (empty if nothing needed merging).
    """
    stmt = select(FinancialMetrics).where(_IS_CONFIDENT_ENOUGH_FOR_DASHBOARD)
    result = await db.execute(stmt)
    rows = result.scalars().all()

    merged_documents: List[Document] = []
    already_merged_ids = set()

    for row in rows:
        if row.document_id in already_merged_ids:
            continue
        match = await find_same_period_match(db, row)
        if match is None or match.document_id in already_merged_ids:
            continue
        merged_document = await merge_documents(db, match, row)
        merged_documents.append(merged_document)
        already_merged_ids.add(row.document_id)
        already_merged_ids.add(match.document_id)

    return merged_documents
