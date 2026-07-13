#!/usr/bin/env bash
# One-command launcher for a fully local, isolated Presentation Mode
# rehearsal -- fresh local SQLite database, local backend, local frontend.
#
# Never touches backend/.env, frontend/.env.local, or the real production
# Railway/Vercel deployment. DATABASE_URL and NEXT_PUBLIC_API_URL are
# overridden only as process-level environment variables for the two
# processes this script starts. See frontend/docs/ai-usage/feature-demo.md.
#
# Usage: scripts/local-demo/run.sh [--skip-seed]

set -euo pipefail

SKIP_SEED=false
if [[ "${1:-}" == "--skip-seed" ]]; then
  SKIP_SEED=true
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"
FRONTEND_DIR="$REPO_ROOT/frontend"
BACKEND_PORT=8010
FRONTEND_PORT=3000
BACKEND_URL="http://127.0.0.1:$BACKEND_PORT"
FRONTEND_URL="http://localhost:$FRONTEND_PORT"
LOCAL_DB_PATH="$BACKEND_DIR/local_demo.db"

echo ""
echo "=== Senus Board -- Local Demo Launcher ==="
echo "Fully isolated from production: fresh local SQLite DB, local backend, local frontend."
echo "backend/.env and frontend/.env.local are never read or written by this script."
echo ""

if [[ -f "$LOCAL_DB_PATH" ]]; then
  echo "Removing previous local_demo.db for a clean run..."
  rm -f "$LOCAL_DB_PATH"
fi

echo "Starting local backend on $BACKEND_URL ..."
(
  cd "$BACKEND_DIR"
  DATABASE_URL="sqlite+aiosqlite:///./local_demo.db" \
  LOCAL_DEMO_BACKEND_PORT="$BACKEND_PORT" \
  python scripts/local_demo_server.py &
  echo $! > /tmp/senus-local-demo-backend.pid
)

for _ in $(seq 1 60); do
  if curl -sf "$BACKEND_URL/docs" > /dev/null 2>&1; then
    break
  fi
  sleep 0.5
done
if ! curl -sf "$BACKEND_URL/docs" > /dev/null 2>&1; then
  echo "Backend did not respond within 30s -- check its output for errors." >&2
  exit 1
fi
echo "Backend is up."

if [[ "$SKIP_SEED" == "false" ]]; then
  echo ""
  echo "Pre-seeding the HY2026 half-year PR (Presentation Mode uploads and merges the other two filings live)..."
  (cd "$BACKEND_DIR" && python scripts/local_demo_seed.py)
fi

echo ""
echo "Starting local frontend on $FRONTEND_URL ..."
(
  cd "$FRONTEND_DIR"
  NEXT_PUBLIC_API_URL="$BACKEND_URL" npm run dev &
  echo $! > /tmp/senus-local-demo-frontend.pid
)

for _ in $(seq 1 120); do
  if curl -sf "$FRONTEND_URL" > /dev/null 2>&1; then
    break
  fi
  sleep 0.5
done
if ! curl -sf "$FRONTEND_URL" > /dev/null 2>&1; then
  echo "Frontend did not respond within 60s -- check its output for errors." >&2
  exit 1
fi
echo "Frontend is up."

echo ""
echo "=== Ready ==="
echo "Open $FRONTEND_URL and click Present."
echo "Backend PID $(cat /tmp/senus-local-demo-backend.pid 2>/dev/null), frontend PID $(cat /tmp/senus-local-demo-frontend.pid 2>/dev/null) -- kill either to stop it."
echo "Nothing here touched backend/.env, frontend/.env.local, or production. Delete backend/local_demo.db afterward if you want to fully reset."
echo ""
