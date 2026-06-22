#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_DIR="$ROOT_DIR/apps/api"
WEB_DIR="$ROOT_DIR/apps/web"
CODEX_BIN="/Users/jackz/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin"
CODEX_NODE="/Users/jackz/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin"

if [ -d "$CODEX_BIN" ]; then
  export PATH="$CODEX_BIN:$PATH"
fi
if [ -d "$CODEX_NODE" ]; then
  export PATH="$CODEX_NODE:$PATH"
fi

export API_CORS_ORIGINS="${API_CORS_ORIGINS:-http://localhost:3000,http://127.0.0.1:3000}"
export NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-http://127.0.0.1:8000/api/v1}"
export SITE_HUNTER_SEARCH_PROVIDER="${SITE_HUNTER_SEARCH_PROVIDER:-duckduckgo_html}"

if [ ! -x "$API_DIR/.venv/bin/uvicorn" ]; then
  echo "Missing FastAPI virtualenv at apps/api/.venv."
  echo "Create it first: cd apps/api && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

if ! command -v pnpm >/dev/null 2>&1 && ! command -v npm >/dev/null 2>&1; then
  echo "Missing pnpm/npm. Install Node.js or run inside Codex where bundled pnpm is available."
  exit 1
fi

cleanup() {
  if [ -n "${API_PID:-}" ]; then kill "$API_PID" 2>/dev/null || true; fi
  if [ -n "${WEB_PID:-}" ]; then kill "$WEB_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM

echo "Starting NOVAION local stack"
echo "Backend: http://127.0.0.1:8000"
echo "API docs: http://127.0.0.1:8000/docs"
echo "Frontend: http://localhost:3000/site-hunter"
echo "Frontend API base: $NEXT_PUBLIC_API_BASE_URL"
echo "Search provider: $SITE_HUNTER_SEARCH_PROVIDER"

(
  cd "$API_DIR"
  .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
) &
API_PID=$!

(
  cd "$WEB_DIR"
  if [ -x "./node_modules/.bin/next" ]; then
    ./node_modules/.bin/next dev
  elif command -v pnpm >/dev/null 2>&1; then
    pnpm --config.confirm-modules-purge=false --filter @novaion/web dev
  else
    npm --workspace apps/web run dev
  fi
) &
WEB_PID=$!

wait "$API_PID" "$WEB_PID"
