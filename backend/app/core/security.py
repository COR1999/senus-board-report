"""
Shared-secret gate for mutating endpoints (upload, delete, regenerate, etc).

This is a single-owner demo/portfolio deployment, not a multi-tenant product
(see README "This is a single-user tool" note) -- so a full login/session
system would be disproportionate. This dependency exists so that once the
live site starts getting portfolio/interview traffic, an anonymous visitor
who finds the API directly (e.g. by guessing routes, since /docs is disabled
outside development -- see main.py) can't delete or overwrite the demo data.
The frontend's own admin UI is separately hidden from public traffic via
NEXT_PUBLIC_ENABLE_ADMIN_ACTIONS; this header check is the server-side
enforcement that holds even if that frontend gate is bypassed.
"""
from fastapi import Header, HTTPException

from app.core.config import get_settings


async def require_admin(x_admin_key: str | None = Header(default=None, alias="X-Admin-Key")) -> None:
    settings = get_settings()

    # Matches the existing dev-bypass convention in Settings.allowed_origins
    # (CORS "*" in development) -- local development never needs the key set.
    if settings.ENVIRONMENT.strip().lower() == "development":
        return

    # Fail closed: an unset key in production must mean "unreachable",
    # never "unprotected".
    if not settings.ADMIN_API_KEY or x_admin_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Missing or invalid admin key")
