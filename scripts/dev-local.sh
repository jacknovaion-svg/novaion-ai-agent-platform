#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_DIR="$ROOT_DIR/apps/api"
WEB_DIR="$ROOT_DIR/apps/web"
CODEX_BIN="/Users/jackz/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin"
CODEX_NODE="/Users/jackz/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
BACKEND_PORT="${BACKEND_PORT:-8000}"

if [ -d "$CODEX_BIN" ]; then
  export PATH="$CODEX_BIN:$PATH"
fi
if [ -d "$CODEX_NODE" ]; then
  export PATH="$CODEX_NODE:$PATH"
fi

export API_CORS_ORIGINS="${API_CORS_ORIGINS:-http://localhost:3000,http://127.0.0.1:3000}"
export NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-http://127.0.0.1:8000/api/v1}"
export APP_ENV="${APP_ENV:-development}"
export HARDWARE_HUNTER_SCHEDULER_ENABLED="${HARDWARE_HUNTER_SCHEDULER_ENABLED:-false}"
export SITE_HUNTER_SEARCH_PROVIDER="${SITE_HUNTER_SEARCH_PROVIDER:-duckduckgo_html}"
export GEOCODING_PROVIDER="${GEOCODING_PROVIDER:-census}"
export NOMINATIM_USER_AGENT="${NOMINATIM_USER_AGENT:-NOVAIONSiteHunterLocal/1.2}"
export OVERPASS_API_URL="${OVERPASS_API_URL:-https://overpass-api.de/api/interpreter}"
export POWER_ASSET_SEARCH_RADII_MILES="${POWER_ASSET_SEARCH_RADII_MILES:-1,3,5,10}"

if [ ! -x "$API_DIR/.venv/bin/uvicorn" ]; then
  echo "Missing FastAPI virtualenv at apps/api/.venv."
  echo "Create it first: cd apps/api && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

if ! command -v pnpm >/dev/null 2>&1 && ! command -v npm >/dev/null 2>&1; then
  echo "Missing pnpm/npm. Install Node.js or run inside Codex where bundled pnpm is available."
  exit 1
fi

pid_command() {
  local pid="$1"
  ps -p "$pid" -o command= 2>/dev/null || true
}

pid_cwd() {
  local pid="$1"
  lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -n 1 || true
}

port_pids() {
  local port="$1"
  lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null | sort -u || true
}

is_project_process() {
  local pid="$1"
  local cmd
  local cwd
  cmd="$(pid_command "$pid")"
  cwd="$(pid_cwd "$pid")"

  case "$cmd $cwd" in
    *"$ROOT_DIR"*|*"$API_DIR"*|*"$WEB_DIR"*) ;;
    *) return 1 ;;
  esac

  case "$cmd" in
    *uvicorn*app.main:app*|*next*dev*|*node*next*|*next-server*) return 0 ;;
    *) return 1 ;;
  esac
}

stop_project_process() {
  local pid="$1"
  local cmd
  cmd="$(pid_command "$pid")"
  echo "Stopping old NOVAION local process PID $pid"
  echo "  $cmd"
  kill "$pid" 2>/dev/null || true
  for _ in 1 2 3 4 5; do
    if ! kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
    sleep 0.4
  done
  echo "PID $pid did not stop gracefully; forcing stop."
  kill -9 "$pid" 2>/dev/null || true
}

check_port() {
  local port="$1"
  local found=0
  while IFS= read -r pid; do
    [ -n "$pid" ] || continue
    found=1
    if is_project_process "$pid"; then
      stop_project_process "$pid"
    else
      echo "Port $port is used by a non-NOVAION process; not stopping it automatically."
      echo "PID $pid: $(pid_command "$pid")"
      echo "Please stop that process or choose a different port before running this script."
      exit 1
    fi
  done < <(port_pids "$port")

  if [ "$found" -eq 0 ]; then
    return 0
  fi

  if [ -n "$(port_pids "$port")" ]; then
    echo "Port $port is still occupied after cleanup."
    exit 1
  fi
}

wait_for_url() {
  local label="$1"
  local url="$2"
  local attempts="${3:-40}"
  for _ in $(seq 1 "$attempts"); do
    if curl -fsS -m 3 "$url" >/dev/null 2>&1; then
      echo "$label ready: $url"
      return 0
    fi
    sleep 0.5
  done
  echo "$label did not become ready: $url"
  return 1
}

cleanup() {
  if [ -n "${API_PID:-}" ]; then kill "$API_PID" 2>/dev/null || true; fi
  if [ -n "${WEB_PID:-}" ]; then kill "$WEB_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM

echo "Checking local ports..."
check_port 3000
check_port 3001
check_port 8000

echo "Starting NOVAION local stack"
echo "Frontend URL: http://localhost:$FRONTEND_PORT"
echo "Backend URL: http://127.0.0.1:$BACKEND_PORT"
echo "API docs URL: http://127.0.0.1:$BACKEND_PORT/docs"
echo "Dashboard URL: http://localhost:$FRONTEND_PORT/hardware-hunter/dashboard"
echo "Site Hunter: http://localhost:$FRONTEND_PORT/site-hunter"
echo "Frontend API base: $NEXT_PUBLIC_API_BASE_URL"
echo "Hardware scheduler enabled: $HARDWARE_HUNTER_SCHEDULER_ENABLED"
echo "Search provider: $SITE_HUNTER_SEARCH_PROVIDER"
echo "Geocoding provider: $GEOCODING_PROVIDER"
echo "Power asset radii: $POWER_ASSET_SEARCH_RADII_MILES"

(
  cd "$API_DIR"
  .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT"
) &
API_PID=$!

(
  cd "$WEB_DIR"
  if [ -x "./node_modules/.bin/next" ]; then
    ./node_modules/.bin/next dev --port "$FRONTEND_PORT"
  elif command -v pnpm >/dev/null 2>&1; then
    pnpm --config.confirm-modules-purge=false --filter @novaion/web dev -- --port "$FRONTEND_PORT"
  else
    npm --workspace apps/web run dev -- --port "$FRONTEND_PORT"
  fi
) &
WEB_PID=$!

wait_for_url "Backend" "http://127.0.0.1:$BACKEND_PORT/docs" 120 || true
wait_for_url "Frontend" "http://localhost:$FRONTEND_PORT/hardware-hunter/dashboard" 50 || true

if command -v python3 >/dev/null 2>&1; then
  for _ in 1 2 3 4 5 6; do
    if curl -fsS -m 5 "http://127.0.0.1:$BACKEND_PORT/api/v1/hardware-hunter/daily-scan/dashboard" 2>/dev/null \
      | python3 -c 'import json,sys; d=json.load(sys.stdin); s=d.get("scheduler",{}); print("PostgreSQL health:", d.get("database_health", "unknown")); print("Persistence mode:", d.get("persistence_mode", "unknown")); print("Scheduler state:", s.get("status", "unknown"))'; then
      break
    fi
    sleep 2
  done
fi

wait "$API_PID" "$WEB_PID"
