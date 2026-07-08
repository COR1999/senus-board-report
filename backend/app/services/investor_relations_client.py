"""
Client for Senus's investor relations API.

The IR page (app.assiduous.tech/investor-relations/senus) is a
client-rendered SPA -- there's no official API documentation, this was
found by inspecting the page's own network requests. It's a plain JSON
REST API with no auth required for public filing metadata/downloads.
"""
from typing import Any, Dict, List, Optional

import httpx

BASE_URL = "https://api.app.assiduous.tech/v1/investor-relations/senus"

# Only categories that can actually contain financial-statement PDFs the
# extractor can use. "corporate" (presentations) and "regulatory" (press
# releases/AGM notices) are deliberately excluded -- confirmed by manually
# inspecting a sample of each category that none carry extractable P&L/
# balance-sheet/cash-flow figures (see backend/docs/source-documents/README.md).
_FILING_CATEGORIES = ("documents", "reports")


async def list_available_filings() -> List[Dict[str, Any]]:
    """
    Returns filing metadata across the categories that can contain real
    financial statements: [{attachment_id, file_name, file_size,
    published_date}, ...]. Does not download any file content.
    """
    filings: List[Dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=10) as client:
        for category in _FILING_CATEGORIES:
            response = await client.get(f"{BASE_URL}/{category}/all-documents")
            response.raise_for_status()
            for doc in response.json().get("documents", []):
                filings.append(
                    {
                        "attachment_id": doc["attachmentId"],
                        "file_name": doc["fileName"],
                        "file_size": doc.get("fileSize"),
                        "published_date": doc.get("publishedDate"),
                    }
                )
    return filings


async def find_filing(attachment_id: str) -> Optional[Dict[str, Any]]:
    """Metadata for one filing by attachment_id, or None if not found."""
    for filing in await list_available_filings():
        if filing["attachment_id"] == attachment_id:
            return filing
    return None


async def download_filing(attachment_id: str) -> bytes:
    """
    Raw PDF bytes for a given attachment_id. The `documents/documents/{id}`
    path works regardless of which category the ID actually came from
    (confirmed empirically) -- there's no need to know the source category
    to download it.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(f"{BASE_URL}/documents/documents/{attachment_id}")
        response.raise_for_status()
        return response.content
