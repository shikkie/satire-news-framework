#!/usr/bin/env bash
#
# install-agentnewsd.sh — create venv + systemd unit for the article API
#
# Does not hardcode any personal username or home path. You pass the service
# user and (optionally) the repo root.
#
# Usage (as root, or with sudo):
#   sudo ./scripts/install-agentnewsd.sh --user SERVICE_USER
#   sudo ./scripts/install-agentnewsd.sh --user SERVICE_USER --repo /path/to/satire-news-framework
#   sudo ./scripts/install-agentnewsd.sh --user SERVICE_USER --port 8790 --bind 0.0.0.0
#   sudo ./scripts/install-agentnewsd.sh --user SERVICE_USER --no-start
#   sudo ./scripts/install-agentnewsd.sh --user SERVICE_USER --uninstall
#
# After install:
#   systemctl status agentnewsd
#   journalctl -u agentnewsd -f
#   curl -sS http://127.0.0.1:8790/health
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_REPO="$(cd "${SCRIPT_DIR}/.." && pwd)"

SERVICE_NAME="agentnewsd"
UNIT_PATH="/etc/systemd/system/${SERVICE_NAME}.service"

SERVICE_USER=""
REPO_ROOT=""
BIND_HOST=""
BIND_PORT=""
DO_START=1
UNINSTALL=0
PYTHON_BIN="${PYTHON_BIN:-python3}"

usage() {
  sed -n '2,/^set -euo pipefail$/p' "$0" | sed '$d' | sed 's/^# \?//'
  exit 0
}

die() {
  echo "install-agentnewsd.sh: $*" >&2
  exit 1
}

need_root() {
  [[ "$(id -u)" -eq 0 ]] || die "run as root (e.g. sudo $0 ...)"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage ;;
    -u|--user)
      [[ $# -ge 2 ]] || die "--user needs a value"
      SERVICE_USER="$2"
      shift 2
      ;;
    -r|--repo)
      [[ $# -ge 2 ]] || die "--repo needs a path"
      REPO_ROOT="$2"
      shift 2
      ;;
    -b|--bind)
      [[ $# -ge 2 ]] || die "--bind needs a host"
      BIND_HOST="$2"
      shift 2
      ;;
    -p|--port)
      [[ $# -ge 2 ]] || die "--port needs a number"
      BIND_PORT="$2"
      shift 2
      ;;
    --python)
      [[ $# -ge 2 ]] || die "--python needs a binary"
      PYTHON_BIN="$2"
      shift 2
      ;;
    --no-start) DO_START=0; shift ;;
    --uninstall) UNINSTALL=1; shift ;;
    *) die "unknown option: $1 (try --help)" ;;
  esac
done

need_root

if [[ "$UNINSTALL" -eq 1 ]]; then
  systemctl stop "${SERVICE_NAME}" 2>/dev/null || true
  systemctl disable "${SERVICE_NAME}" 2>/dev/null || true
  rm -f "${UNIT_PATH}"
  systemctl daemon-reload
  echo "install-agentnewsd.sh: removed ${UNIT_PATH}"
  echo "install-agentnewsd.sh: venv and .env were left in place (delete manually if desired)"
  exit 0
fi

[[ -n "$SERVICE_USER" ]] || die "required: --user SERVICE_USER (system account that owns the repo / runs grok)"

if ! id -u "$SERVICE_USER" >/dev/null 2>&1; then
  die "user does not exist: ${SERVICE_USER}"
fi

if [[ -z "$REPO_ROOT" ]]; then
  REPO_ROOT="$DEFAULT_REPO"
fi
REPO_ROOT="$(cd "$REPO_ROOT" && pwd)" || die "repo path not found: ${REPO_ROOT}"

APP_DIR="${REPO_ROOT}/agentnewsd"
ENV_FILE="${APP_DIR}/.env"
ENV_EXAMPLE="${APP_DIR}/.env.example"
VENV_DIR="${APP_DIR}/.venv"
REQ_FILE="${APP_DIR}/requirements.txt"
APP_PY="${APP_DIR}/app.py"
CREATE_SCRIPT="${REPO_ROOT}/scripts/create-article.sh"

[[ -f "$APP_PY" ]] || die "missing ${APP_PY}"
[[ -f "$REQ_FILE" ]] || die "missing ${REQ_FILE}"
[[ -f "$CREATE_SCRIPT" ]] || die "missing ${CREATE_SCRIPT}"
[[ -x "$CREATE_SCRIPT" ]] || chmod +x "$CREATE_SCRIPT"

# Ensure .env exists (generate key if missing)
if [[ ! -f "$ENV_FILE" ]]; then
  if [[ -f "$ENV_EXAMPLE" ]]; then
    cp "$ENV_EXAMPLE" "$ENV_FILE"
  else
    cat >"$ENV_FILE" <<'EOF'
AGENTNEWSD_API_KEY=change-me
AGENTNEWSD_HOST=0.0.0.0
AGENTNEWSD_PORT=8790
AGENTNEWSD_TIMEOUT_SECONDS=3600
EOF
  fi
  # Replace placeholder key with a random secret when still default-ish
  if grep -qE '^(AGENTNEWSD_API_KEY=change-me|AGENTNEWSD_API_KEY=change-me-to-a-long-random-secret)' "$ENV_FILE"; then
    NEW_KEY="$(${PYTHON_BIN} -c 'import secrets; print(secrets.token_hex(32))')"
    # portable in-place: rewrite file
    TMP_ENV="$(mktemp)"
    sed "s|^AGENTNEWSD_API_KEY=.*|AGENTNEWSD_API_KEY=${NEW_KEY}|" "$ENV_FILE" >"$TMP_ENV"
    mv "$TMP_ENV" "$ENV_FILE"
    echo "install-agentnewsd.sh: generated AGENTNEWSD_API_KEY in ${ENV_FILE}"
  fi
  chown "${SERVICE_USER}:${SERVICE_USER}" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
fi

# Optional CLI overrides into .env (only if flags passed)
ensure_env_trailing_newline() {
  # Appending without a final newline glues keys (breaks systemd EnvironmentFile + int()).
  [[ -f "$ENV_FILE" ]] || return 0
  [[ -s "$ENV_FILE" ]] || return 0
  local last
  last="$(tail -c 1 "$ENV_FILE" || true)"
  if [[ "$last" != $'\n' ]]; then
    printf '\n' >>"$ENV_FILE"
  fi
}

set_env_kv() {
  local key="$1" val="$2"
  ensure_env_trailing_newline
  if grep -q "^${key}=" "$ENV_FILE"; then
    TMP_ENV="$(mktemp)"
    sed "s|^${key}=.*|${key}=${val}|" "$ENV_FILE" >"$TMP_ENV"
    # sed rewrite can drop final newline depending on input; keep file well-formed
    if [[ -s "$TMP_ENV" ]] && [[ "$(tail -c 1 "$TMP_ENV")" != $'\n' ]]; then
      printf '\n' >>"$TMP_ENV"
    fi
    mv "$TMP_ENV" "$ENV_FILE"
  else
    printf '%s=%s\n' "$key" "$val" >>"$ENV_FILE"
  fi
}

[[ -n "$BIND_HOST" ]] && set_env_kv AGENTNEWSD_HOST "$BIND_HOST"
[[ -n "$BIND_PORT" ]] && set_env_kv AGENTNEWSD_PORT "$BIND_PORT"
set_env_kv AGENTNEWSD_REPO_ROOT "$REPO_ROOT"
set_env_kv AGENTNEWSD_CREATE_SCRIPT "$CREATE_SCRIPT"

chown "${SERVICE_USER}:${SERVICE_USER}" "$ENV_FILE"
chmod 600 "$ENV_FILE"

# Resolve bind from .env for unit description / summary
RESOLVED_HOST="$(grep -E '^AGENTNEWSD_HOST=' "$ENV_FILE" | head -1 | cut -d= -f2-)"
RESOLVED_PORT="$(grep -E '^AGENTNEWSD_PORT=' "$ENV_FILE" | head -1 | cut -d= -f2-)"
RESOLVED_HOST="${RESOLVED_HOST:-0.0.0.0}"
RESOLVED_PORT="${RESOLVED_PORT:-8790}"

# Run a command as the service user (no personal paths; portable helpers)
as_user() {
  if command -v runuser >/dev/null 2>&1; then
    runuser -u "$SERVICE_USER" -- "$@"
  else
    # sudo keeps a minimal env; HOME is set by the unit at runtime
    sudo -u "$SERVICE_USER" -- "$@"
  fi
}

# venv + deps as the service user
echo "install-agentnewsd.sh: creating venv at ${VENV_DIR}"
as_user "$PYTHON_BIN" -m venv "$VENV_DIR"
as_user "${VENV_DIR}/bin/pip" install --upgrade pip
as_user "${VENV_DIR}/bin/pip" install -r "$REQ_FILE"

VENV_PYTHON="${VENV_DIR}/bin/python"
[[ -x "$VENV_PYTHON" ]] || die "venv python missing: ${VENV_PYTHON}"

# HOME for the service user (grok / git often need it)
SERVICE_HOME="$(getent passwd "$SERVICE_USER" | cut -d: -f6)"
[[ -n "$SERVICE_HOME" ]] || die "could not resolve home for ${SERVICE_USER}"

# Write unit — no personal names baked into the script; only runtime args.
cat >"${UNIT_PATH}" <<EOF
[Unit]
Description=Agent News article creation API (agentnewsd)
Documentation=file://${REPO_ROOT}/agentnewsd/app.py
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_USER}
WorkingDirectory=${APP_DIR}
Environment=HOME=${SERVICE_HOME}
Environment=PATH=${VENV_DIR}/bin:/usr/local/bin:/usr/bin:/bin
EnvironmentFile=-${ENV_FILE}
ExecStart=${VENV_PYTHON} ${APP_PY}
Restart=on-failure
RestartSec=5
# Long Grok jobs: give the service room; request timeout is enforced in-app
TimeoutStartSec=30
TimeoutStopSec=60
# Hardening (keep write access for repo work done by create-article.sh)
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

chmod 644 "${UNIT_PATH}"
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.service"

if [[ "$DO_START" -eq 1 ]]; then
  systemctl restart "${SERVICE_NAME}.service"
  sleep 1
  systemctl --no-pager --full status "${SERVICE_NAME}.service" || true
fi

cat <<EOF

install-agentnewsd.sh: installed ${SERVICE_NAME}

  Unit:     ${UNIT_PATH}
  User:     ${SERVICE_USER}
  Repo:     ${REPO_ROOT}
  App:      ${APP_DIR}
  Env:      ${ENV_FILE}
  Listen:   http://${RESOLVED_HOST}:${RESOLVED_PORT}
  Health:   curl -sS http://${RESOLVED_HOST}:${RESOLVED_PORT}/health

  Logs:     journalctl -u ${SERVICE_NAME} -f
  Restart:  systemctl restart ${SERVICE_NAME}
  Stop:     systemctl stop ${SERVICE_NAME}
  Remove:   sudo $0 --user ${SERVICE_USER} --uninstall

Ensure the service user can run create-article.sh end-to-end (grok on PATH,
git push credentials, repo write access). API key lives only in ${ENV_FILE}.

Example create (replace KEY and brief):

  # Dry-run (no Grok / git / commit — fake article_url):
  curl -N -sS -X POST "http://${RESOLVED_HOST}:${RESOLVED_PORT}/v1/create-article" \\
    -H 'Content-Type: application/json' \\
    -d '{"api_key":"YOUR_KEY","article_def":"test brief","dry_run":true}'

  # Real create:
  curl -N -sS -X POST "http://${RESOLVED_HOST}:${RESOLVED_PORT}/v1/create-article" \\
    -H 'Content-Type: application/json' \\
    -d '{"api_key":"YOUR_KEY","article_def":"Orange kitten calls 911 for late breakfast..."}'

EOF
