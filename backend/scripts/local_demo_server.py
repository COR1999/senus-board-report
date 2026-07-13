"""
Local-only demo server launcher for Presentation Mode rehearsals -- never
used for anything but a throwaway local demo database.

Registers the same Postgres-JSONB -> SQLite-JSON compiler shim
backend/tests/conftest.py uses for the test suite. app/main.py's real
startup path has no such shim (it's only ever run against real Postgres in
production, or SQLite via this shim in tests), so a bare
`uvicorn app.main:app` fails to create `historical_insights.insight` (a
JSONB column) against SQLite outside pytest.

DATABASE_URL must already be pointed at a local sqlite file by the caller
(scripts/local-demo/run.ps1 or run.sh) -- refuses to start against
anything else, specifically so this can never be pointed at
backend/.env's production Postgres URL by a copy-paste mistake.
"""
import os
import sys

# Running this file as `python scripts/local_demo_server.py` puts this
# file's own directory (backend/scripts/) at sys.path[0], NOT backend/
# itself -- `import app` (and uvicorn's own "app.main:app" string import
# below) fails with `ModuleNotFoundError: No module named 'app'` without
# this, regardless of the process's current working directory (Python's
# sys.path[0] for a script invocation is about the script's own location,
# not the shell's cwd).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


if __name__ == "__main__":
    database_url = os.environ.get("DATABASE_URL", "")
    if "sqlite" not in database_url:
        print(
            "Refusing to start: DATABASE_URL does not look like a local SQLite URL "
            f"({database_url!r}). This launcher is for local demo rehearsals only -- "
            "it must never run against production Postgres.",
            file=sys.stderr,
        )
        sys.exit(1)

    import uvicorn

    port = int(os.environ.get("LOCAL_DEMO_BACKEND_PORT", "8010"))
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, reload=False)
