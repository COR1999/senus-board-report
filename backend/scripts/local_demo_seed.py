"""
Pre-seeds a local demo backend (see local_demo_server.py) with ONE
filing BEFORE Presentation Mode starts, so the dashboard shows real,
complete data (including a real Cost Waterfall -- this filing discloses a
full P&L breakdown) from the very first slide. A presenter should never be
looking at an empty chart or the frontend's static mock-data fallback live
on stage -- both read as broken, not "nothing uploaded yet".

Pre-seeded: Senus_HalfYearResultsDec2025_PR_V19032026 (HY2026, Dec 2025).
Deterministic (text-based) extraction, not Gemini vision -- confirmed
reliable and instant across every run this session, unlike ADF Farm
Solutions (see below). This becomes the dashboard's starting baseline.

The demo's other two filings -- ADF Farm Solutions and the Information
Document -- are deliberately NOT pre-seeded. They're uploaded LIVE, on
stage, by Presentation Mode itself (see
frontend/lib/presentation/steps.ts's `demoUploads`), both at the same
"Extraction & Confidence Pipeline" step: both genuinely report the same
underlying period (FY2025, year ended 30 June 2025), so uploading them
one after another triggers a real, live merge into a single new period --
the audience watches a brand new period, and its own KPIs, appear on the
dashboard in real time, alongside the pre-seeded HY2026 baseline that was
there the whole time.

ADF Farm Solutions runs through Gemini vision (it's a scanned filing with
no text layer), which has been directly observed, in this same project, to
vary call-to-call on this exact file -- succeeding in production, failing
in local testing, and (even when it "succeeds") sometimes not returning a
parseable reporting_period despite the prompt explicitly asking for one in
an exact, regex-matchable phrasing (backend/app/services/gemini_service.py).
That's why it's live-uploaded rather than pre-seeded: if the merge doesn't
land this run, the dashboard was already showing real, complete data the
whole time -- the live moment is additive, never load-bearing.
"""
import sys

import httpx

BACKEND_URL = "http://127.0.0.1:8010"
HY2026_PATH = "tests/fixtures/Senus_HalfYearResultsDec2025_PR_V19032026 FINAL clean.pdf"
HY2026_FILENAME = "Senus_HalfYearResultsDec2025_PR_V19032026 FINAL clean.pdf"


def _upload(client: httpx.Client, path: str, filename: str) -> httpx.Response:
    with open(path, "rb") as f:
        return client.post(
            f"{BACKEND_URL}/api/documents/upload",
            files={"file": (filename, f, "application/pdf")},
            timeout=60,
        )


def seed_hy2026(client: httpx.Client) -> bool:
    print("  Senus HY2026 half-year PR: uploading (deterministic extraction, should be fast)...", flush=True)
    try:
        response = _upload(client, HY2026_PATH, HY2026_FILENAME)
    except httpx.HTTPError as e:
        # Must be caught here rather than left to propagate, or this whole
        # pre-seed step crashes uncaught and run.ps1/run.sh (which don't
        # check this script's exit code) move on to the frontend with
        # nothing seeded and no explanation.
        print(f"  Senus HY2026 half-year PR: failed -- {type(e).__name__}: {e}")
        return False

    if response.status_code != 200:
        detail = response.json().get("detail", response.text)
        print(f"  Senus HY2026 half-year PR: did not land as a usable extraction -- {detail}")
        return False

    tier = response.json().get("financial_metrics", {}).get("extraction_confidence_tier")
    print(f"  Senus HY2026 half-year PR: uploaded, confidence tier = {tier!r}")
    return True


if __name__ == "__main__":
    print("Pre-seeding local demo database...")
    with httpx.Client() as client:
        ok = seed_hy2026(client)
    print("Pre-seed complete." if ok else "Pre-seed finished with a gap -- see above.")
    sys.exit(0 if ok else 1)
