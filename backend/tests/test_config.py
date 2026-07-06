"""
Tests for app.core.config.Settings, particularly the CORS allowed-origins
list -- regression test for a hardcoded Vercel URL that didn't match the
real deployed frontend ("senus-board.vercel.app" vs the actual
"senus-board-report.vercel.app"), which silently blocked every request
from the live deployed app with no server-side error to point at (CORS
failures only surface in the browser).
"""
from app.core.config import Settings


def test_allowed_origins_includes_the_real_deployed_vercel_url():
    settings = Settings()
    assert "https://senus-board-report.vercel.app" in settings.allowed_origins


def test_allowed_origins_includes_local_dev_hosts():
    settings = Settings()
    for origin in (
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ):
        assert origin in settings.allowed_origins
