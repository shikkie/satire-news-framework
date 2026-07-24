#!/usr/bin/env bash
#
# dev.sh — local preview process manager for satire-news-framework
#
# Starts:
#   - Python article API  (0.0.0.0:8787 by default — all interfaces)
#   - Vite React frontend (0.0.0.0:5173 by default — all interfaces)
#   - agentnewsd create API (0.0.0.0:8790 by default — all interfaces; API key auth)
#
# Bind preview local-only instead:
#   API_HOST=127.0.0.1 UI_HOST=127.0.0.1 ./dev.sh
#
# Usage:
#   ./dev.sh              # start all (api + frontend + agentnewsd)
#   ./dev.sh start [api|frontend|agentnewsd|all]
#   ./dev.sh stop  [api|frontend|agentnewsd|all]
#   ./dev.sh restart [...]
#   ./dev.sh status
#   ./dev.sh logs [api|frontend|agentnewsd|all]
#   ./dev.sh help
#

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="${REPO_ROOT}/.pids"
LOG_DIR="${REPO_ROOT}/logs"

# 0.0.0.0 = listen on all interfaces (phone / LAN). Use 127.0.0.1 for local-only.
API_HOST="${API_HOST:-0.0.0.0}"
API_PORT="${API_PORT:-8787}"
UI_HOST="${UI_HOST:-0.0.0.0}"
UI_PORT="${UI_PORT:-5173}"
# agentnewsd: 0.0.0.0 so remote clients can reach it (auth is API key). Local-only: AGENTNEWSD_HOST=127.0.0.1
AGENTNEWSD_HOST="${AGENTNEWSD_HOST:-0.0.0.0}"
AGENTNEWSD_PORT="${AGENTNEWSD_PORT:-8790}"

API_PID_FILE="${PID_DIR}/api.pid"
UI_PID_FILE="${PID_DIR}/frontend.pid"
AGENTNEWSD_PID_FILE="${PID_DIR}/agentnewsd.pid"
API_LOG="${LOG_DIR}/api.log"
UI_LOG="${LOG_DIR}/frontend.log"
AGENTNEWSD_LOG="${LOG_DIR}/agentnewsd.log"

AGENTNEWSD_DIR="${REPO_ROOT}/agentnewsd"
AGENTNEWSD_VENV="${AGENTNEWSD_DIR}/.venv"
AGENTNEWSD_APP="${AGENTNEWSD_DIR}/app.py"
AGENTNEWSD_REQ="${AGENTNEWSD_DIR}/requirements.txt"
AGENTNEWSD_ENV="${AGENTNEWSD_DIR}/.env"
AGENTNEWSD_ENV_EXAMPLE="${AGENTNEWSD_DIR}/.env.example"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info()  { echo -e "${CYAN}[INFO]${NC}  $*" >&2; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $*" >&2; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*" >&2; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

ensure_dirs() {
  mkdir -p "$PID_DIR" "$LOG_DIR"
}

is_running() {
  local pid_file="$1"
  [[ -f "$pid_file" ]] || return 1
  local pid
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  [[ -n "${pid:-}" ]] || return 1
  kill -0 "$pid" 2>/dev/null
}

port_in_use() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltn "sport = :${port}" 2>/dev/null | grep -q LISTEN
  else
    # Fallback: try binding is harder; use lsof if present
    if command -v lsof >/dev/null 2>&1; then
      lsof -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1
    else
      return 1
    fi
  fi
}

read_pid() {
  local pid_file="$1"
  [[ -f "$pid_file" ]] && cat "$pid_file" || true
}

# Best-effort LAN IP for phone/browser URLs (0.0.0.0 is not clickable).
lan_ip() {
  local ip=""
  ip="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i = 1; i <= NF; i++) if ($i == "src") { print $(i + 1); exit }}')"
  if [[ -z "${ip}" ]]; then
    ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
  fi
  echo "${ip:-127.0.0.1}"
}

# Host to print in user-facing URLs
display_host() {
  local bind_host="$1"
  if [[ "$bind_host" == "0.0.0.0" || "$bind_host" == "::" || "$bind_host" == "*" ]]; then
    lan_ip
  else
    echo "$bind_host"
  fi
}

start_api() {
  if is_running "$API_PID_FILE"; then
    log_ok "API already running (pid $(read_pid "$API_PID_FILE"))"
    return 0
  fi
  if port_in_use "$API_PORT"; then
    log_error "Port ${API_PORT} is already in use (API). Refusing to start."
    return 1
  fi
  log_info "Starting preview API on ${API_HOST}:${API_PORT} (URL http://$(display_host "$API_HOST"):${API_PORT})"
  (
    cd "$REPO_ROOT"
    export API_HOST API_PORT
    # new session so stop can signal the whole group cleanly
    setsid nohup python3 "$REPO_ROOT/preview/server.py" >>"$API_LOG" 2>&1 &
    echo $! >"$API_PID_FILE"
  )
  sleep 0.4
  if is_running "$API_PID_FILE"; then
    log_ok "API started (pid $(read_pid "$API_PID_FILE")) → log ${API_LOG}"
  else
    log_error "API failed to start — see ${API_LOG}"
    return 1
  fi
}

ensure_node_modules() {
  if [[ ! -d "${REPO_ROOT}/node_modules" ]]; then
    log_info "Installing npm dependencies…"
    (cd "$REPO_ROOT" && npm install)
  fi
}

ensure_agentnewsd_env() {
  if [[ -f "$AGENTNEWSD_ENV" ]]; then
    return 0
  fi
  if [[ -f "$AGENTNEWSD_ENV_EXAMPLE" ]]; then
    log_info "Creating ${AGENTNEWSD_ENV} from .env.example"
    cp "$AGENTNEWSD_ENV_EXAMPLE" "$AGENTNEWSD_ENV"
  else
    log_info "Creating ${AGENTNEWSD_ENV}"
    cat >"$AGENTNEWSD_ENV" <<'EOF'
AGENTNEWSD_API_KEY=change-me-to-a-long-random-secret
AGENTNEWSD_HOST=0.0.0.0
AGENTNEWSD_PORT=8790
AGENTNEWSD_TIMEOUT_SECONDS=3600
EOF
  fi
  if grep -qE '^(AGENTNEWSD_API_KEY=change-me|AGENTNEWSD_API_KEY=change-me-to-a-long-random-secret)' "$AGENTNEWSD_ENV" 2>/dev/null; then
    local new_key
    new_key="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
    local tmp
    tmp="$(mktemp)"
    sed "s|^AGENTNEWSD_API_KEY=.*|AGENTNEWSD_API_KEY=${new_key}|" "$AGENTNEWSD_ENV" >"$tmp"
    mv "$tmp" "$AGENTNEWSD_ENV"
    chmod 600 "$AGENTNEWSD_ENV"
    log_ok "Generated AGENTNEWSD_API_KEY in ${AGENTNEWSD_ENV}"
  fi
  chmod 600 "$AGENTNEWSD_ENV" 2>/dev/null || true
}

ensure_agentnewsd_venv() {
  if [[ ! -f "$AGENTNEWSD_APP" ]]; then
    log_error "Missing ${AGENTNEWSD_APP}"
    return 1
  fi
  if [[ ! -x "${AGENTNEWSD_VENV}/bin/python" ]]; then
    log_info "Creating agentnewsd venv at ${AGENTNEWSD_VENV}"
    python3 -m venv "$AGENTNEWSD_VENV"
    "${AGENTNEWSD_VENV}/bin/pip" install --upgrade pip >/dev/null
    "${AGENTNEWSD_VENV}/bin/pip" install -r "$AGENTNEWSD_REQ"
  elif [[ -f "$AGENTNEWSD_REQ" ]]; then
    # Cheap ensure flask present (first start after clone with empty-ish venv)
    if ! "${AGENTNEWSD_VENV}/bin/python" -c "import flask" 2>/dev/null; then
      log_info "Installing agentnewsd Python deps…"
      "${AGENTNEWSD_VENV}/bin/pip" install -r "$AGENTNEWSD_REQ"
    fi
  fi
}

start_agentnewsd() {
  if is_running "$AGENTNEWSD_PID_FILE"; then
    log_ok "agentnewsd already running (pid $(read_pid "$AGENTNEWSD_PID_FILE"))"
    return 0
  fi
  if port_in_use "$AGENTNEWSD_PORT"; then
    log_error "Port ${AGENTNEWSD_PORT} is already in use (agentnewsd). Refusing to start."
    return 1
  fi
  ensure_agentnewsd_env
  ensure_agentnewsd_venv
  log_info "Starting agentnewsd on ${AGENTNEWSD_HOST}:${AGENTNEWSD_PORT} (URL http://$(display_host "$AGENTNEWSD_HOST"):${AGENTNEWSD_PORT})"
  (
    cd "$AGENTNEWSD_DIR"
    # Host/port from dev.sh take precedence over .env (app only fills missing keys)
    export AGENTNEWSD_HOST AGENTNEWSD_PORT
    export AGENTNEWSD_REPO_ROOT="${AGENTNEWSD_REPO_ROOT:-$REPO_ROOT}"
    setsid nohup "${AGENTNEWSD_VENV}/bin/python" "$AGENTNEWSD_APP" >>"$AGENTNEWSD_LOG" 2>&1 &
    echo $! >"$AGENTNEWSD_PID_FILE"
  )
  sleep 0.5
  if is_running "$AGENTNEWSD_PID_FILE"; then
    log_ok "agentnewsd started (pid $(read_pid "$AGENTNEWSD_PID_FILE")) → log ${AGENTNEWSD_LOG}"
  else
    log_error "agentnewsd failed to start — see ${AGENTNEWSD_LOG}"
    return 1
  fi
}

start_frontend() {
  if is_running "$UI_PID_FILE"; then
    log_ok "Frontend already running (pid $(read_pid "$UI_PID_FILE"))"
    return 0
  fi
  if port_in_use "$UI_PORT"; then
    log_error "Port ${UI_PORT} is already in use (Vite). Refusing to start."
    return 1
  fi
  ensure_node_modules
  log_info "Starting Vite on ${UI_HOST}:${UI_PORT} (URL http://$(display_host "$UI_HOST"):${UI_PORT})"
  (
    cd "$REPO_ROOT"
    # Proxy still targets loopback API; phone only needs to reach Vite
    export PREVIEW_API="http://127.0.0.1:${API_PORT}"
    setsid nohup npm run dev -- --host "$UI_HOST" --port "$UI_PORT" >>"$UI_LOG" 2>&1 &
    echo $! >"$UI_PID_FILE"
  )
  sleep 0.8
  if is_running "$UI_PID_FILE"; then
    log_ok "Frontend started (pid $(read_pid "$UI_PID_FILE")) → log ${UI_LOG}"
  else
    log_error "Frontend failed to start — see ${UI_LOG}"
    return 1
  fi
}

# Kill a process and its process group / children (npm spawns vite as a child).
kill_tree() {
  local pid="$1"
  local sig="${2:-TERM}"
  # Prefer process group if this pid is a group leader
  kill -"$sig" -- "-${pid}" 2>/dev/null || true
  kill -"$sig" "$pid" 2>/dev/null || true
  # Children (e.g. node vite under npm)
  local kids
  kids="$(ps -o pid= --ppid "$pid" 2>/dev/null | tr -d ' ' || true)"
  local c
  for c in $kids; do
    [[ -n "$c" ]] || continue
    kill_tree "$c" "$sig"
  done
}

stop_one() {
  local name="$1"
  local pid_file="$2"
  if ! is_running "$pid_file"; then
    log_warn "${name} is not running"
    rm -f "$pid_file"
    return 0
  fi
  local pid
  pid="$(read_pid "$pid_file")"
  log_info "Stopping ${name} (pid ${pid})"
  kill_tree "$pid" TERM
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    if ! kill -0 "$pid" 2>/dev/null; then
      break
    fi
    sleep 0.2
  done
  if kill -0 "$pid" 2>/dev/null; then
    log_warn "${name} still alive — sending SIGKILL"
    kill_tree "$pid" KILL
  fi
  rm -f "$pid_file"
  log_ok "${name} stopped"
}

cmd_start() {
  ensure_dirs
  local target="${1:-all}"
  case "$target" in
    api) start_api ;;
    frontend|ui|web) start_frontend ;;
    agentnewsd|agent|create-api)
      start_agentnewsd
      ;;
    all|"")
      start_api
      start_frontend
      start_agentnewsd
      local ui_url="http://$(display_host "$UI_HOST"):${UI_PORT}"
      local api_url="http://$(display_host "$API_HOST"):${API_PORT}/api/articles"
      local agent_url="http://$(display_host "$AGENTNEWSD_HOST"):${AGENTNEWSD_PORT}"
      echo
      log_ok "Dev stack ready (preview + agentnewsd)"
      echo "  This machine:  http://127.0.0.1:${UI_PORT}"
      echo "  Hostname:      http://bandit:${UI_PORT}"
      echo "  Phone / LAN:   ${ui_url}"
      echo "  Preview API:   ${api_url}"
      echo "  agentnewsd:    ${agent_url}/health  (POST ${agent_url}/v1/create-article)"
      echo "  Docs:          agentnewsd/README.md"
      echo "  Stop:          ./dev.sh stop"
      ;;
    *)
      log_error "Unknown target: $target"
      return 1
      ;;
  esac
}

cmd_stop() {
  local target="${1:-all}"
  case "$target" in
    api) stop_one "API" "$API_PID_FILE" ;;
    frontend|ui|web) stop_one "Frontend" "$UI_PID_FILE" ;;
    agentnewsd|agent|create-api) stop_one "agentnewsd" "$AGENTNEWSD_PID_FILE" ;;
    all|"")
      stop_one "Frontend" "$UI_PID_FILE"
      stop_one "API" "$API_PID_FILE"
      stop_one "agentnewsd" "$AGENTNEWSD_PID_FILE"
      ;;
    *)
      log_error "Unknown target: $target"
      return 1
      ;;
  esac
}

cmd_status() {
  ensure_dirs
  local ui_disp api_disp agent_disp
  ui_disp="$(display_host "$UI_HOST")"
  api_disp="$(display_host "$API_HOST")"
  agent_disp="$(display_host "$AGENTNEWSD_HOST")"
  echo "satire-news-framework dev status"
  echo "--------------------------------"
  if is_running "$API_PID_FILE"; then
    echo -e "API:        ${GREEN}running${NC}  pid $(read_pid "$API_PID_FILE")  bind ${API_HOST}:${API_PORT}  → http://${api_disp}:${API_PORT}"
  else
    echo -e "API:        ${YELLOW}stopped${NC}"
  fi
  if is_running "$UI_PID_FILE"; then
    echo -e "Frontend:   ${GREEN}running${NC}  pid $(read_pid "$UI_PID_FILE")  bind ${UI_HOST}:${UI_PORT}  → http://${ui_disp}:${UI_PORT}"
  else
    echo -e "Frontend:   ${YELLOW}stopped${NC}"
  fi
  if is_running "$AGENTNEWSD_PID_FILE"; then
    echo -e "agentnewsd: ${GREEN}running${NC}  pid $(read_pid "$AGENTNEWSD_PID_FILE")  bind ${AGENTNEWSD_HOST}:${AGENTNEWSD_PORT}  → http://${agent_disp}:${AGENTNEWSD_PORT}"
  else
    echo -e "agentnewsd: ${YELLOW}stopped${NC}"
  fi
}

cmd_logs() {
  ensure_dirs
  local target="${1:-all}"
  case "$target" in
    api)
      tail -n 80 -f "$API_LOG"
      ;;
    frontend|ui|web)
      tail -n 80 -f "$UI_LOG"
      ;;
    agentnewsd|agent|create-api)
      tail -n 80 -f "$AGENTNEWSD_LOG"
      ;;
    all|"")
      touch "$API_LOG" "$UI_LOG" "$AGENTNEWSD_LOG"
      tail -n 40 -f "$API_LOG" "$UI_LOG" "$AGENTNEWSD_LOG"
      ;;
    *)
      log_error "Unknown target: $target"
      return 1
      ;;
  esac
}

cmd_help() {
  cat <<EOF
dev.sh — satire-news-framework local preview + agentnewsd

Commands:
  ./dev.sh                 Start API + Vite + agentnewsd
  ./dev.sh start [target]  target: all | api | frontend | agentnewsd
  ./dev.sh stop  [target]
  ./dev.sh restart [target]
  ./dev.sh status
  ./dev.sh logs [target]
  ./dev.sh help

Ports / bind (override with env):
  API_HOST=${API_HOST}             API_PORT=${API_PORT}
  UI_HOST=${UI_HOST}               UI_PORT=${UI_PORT}
  AGENTNEWSD_HOST=${AGENTNEWSD_HOST}   AGENTNEWSD_PORT=${AGENTNEWSD_PORT}

  Default bind is 0.0.0.0 (all interfaces) for preview + agentnewsd.
  Local-only: API_HOST=127.0.0.1 UI_HOST=127.0.0.1 AGENTNEWSD_HOST=127.0.0.1 ./dev.sh

URLs after start:
  http://127.0.0.1:${UI_PORT}
  http://$(display_host "$UI_HOST"):${UI_PORT}   # phone / LAN
  http://$(display_host "$AGENTNEWSD_HOST"):${AGENTNEWSD_PORT}/health   # agentnewsd
  Docs: agentnewsd/README.md
EOF
}

main() {
  local cmd="${1:-start}"
  shift || true
  case "$cmd" in
    start) cmd_start "${1:-all}" ;;
    stop) cmd_stop "${1:-all}" ;;
    restart)
      cmd_stop "${1:-all}"
      cmd_start "${1:-all}"
      ;;
    status|ps) cmd_status ;;
    logs|log) cmd_logs "${1:-all}" ;;
    help|-h|--help) cmd_help ;;
    *)
      log_error "Unknown command: $cmd"
      cmd_help
      return 1
      ;;
  esac
}

main "$@"
