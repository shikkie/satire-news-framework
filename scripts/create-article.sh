#!/usr/bin/env bash
#
# create-article.sh — trigger Agent News article creation via Grok CLI (headless)
#
# Always runs in the satire-news-framework repo root so AGENTS.md + skills load.
# Long prompts are fine: use args, stdin, or --file.
#
# Usage:
#   ./scripts/create-article.sh "Six week old orange kitten called 911..."
#   ./scripts/create-article.sh --file prompt.txt
#   echo "long brief..." | ./scripts/create-article.sh
#   ./scripts/create-article.sh - <<'EOF'
#   multi-line brief here
#   EOF
#
# Options:
#   -f, --file PATH     Read the full brief from a file
#   -                   Read brief from stdin (also works with no args + pipe/heredoc)
#   -m, --model NAME    Grok model (default: grok-build or $GROK_MODEL)
#   -n, --dry-run       Print the composed prompt; do not invoke grok
#   -k, --keep-prompt   Keep the temp prompt file path on stderr after run
#   -h, --help          Show help
#
# Env:
#   GROK_BIN            Path to grok (default: grok on PATH)
#   GROK_MODEL          Default model
#   GROK_ARTICLE_EXTRA  Extra text appended to the system brief (optional)
#   SKIP_YOLO=1         Do not pass --always-approve / bypassPermissions
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
GROK_BIN="${GROK_BIN:-grok}"
MODEL="${GROK_MODEL:-grok-build}"
DRY_RUN=0
KEEP_PROMPT=0
PROMPT_FILE=""
YOLO=1

usage() {
  sed -n '2,35p' "$0" | sed 's/^# \?//'
  exit 0
}

die() {
  echo "create-article.sh: $*" >&2
  exit 1
}

# --- args -------------------------------------------------------------------
POSITIONAL=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage ;;
    -n|--dry-run) DRY_RUN=1; shift ;;
    -k|--keep-prompt) KEEP_PROMPT=1; shift ;;
    -m|--model)
      [[ $# -ge 2 ]] || die "--model needs a value"
      MODEL="$2"
      shift 2
      ;;
    -f|--file)
      [[ $# -ge 2 ]] || die "--file needs a path"
      PROMPT_FILE="$2"
      shift 2
      ;;
    --) shift; POSITIONAL+=("$@"); break ;;
    -*)
      die "unknown option: $1 (try --help)"
      ;;
    *)
      POSITIONAL+=("$1")
      shift
      ;;
  esac
done
set -- "${POSITIONAL[@]+"${POSITIONAL[@]}"}"

# --- resolve user brief -----------------------------------------------------
USER_BRIEF=""
if [[ -n "$PROMPT_FILE" ]]; then
  [[ -f "$PROMPT_FILE" ]] || die "file not found: $PROMPT_FILE"
  USER_BRIEF="$(cat -- "$PROMPT_FILE")"
elif [[ $# -eq 1 && "$1" == "-" ]]; then
  # Explicit stdin marker: create-article.sh - <<'EOF' ...
  USER_BRIEF="$(cat)"
elif [[ $# -gt 0 ]]; then
  # Join all remaining args with spaces (one long string or many words)
  USER_BRIEF="$*"
elif [[ ! -t 0 ]]; then
  # stdin (pipe or heredoc) when no args
  USER_BRIEF="$(cat)"
else
  die "no brief provided. Pass a string, --file PATH, or pipe/heredoc on stdin.
Example:
  $0 \"Orange kitten calls 911 because breakfast was late...\""
fi

# Trim leading/trailing whitespace (keep internal newlines)
USER_BRIEF="$(printf '%s' "$USER_BRIEF" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
[[ -n "$USER_BRIEF" ]] || die "brief is empty"

command -v "$GROK_BIN" >/dev/null 2>&1 || die "grok not found (GROK_BIN=$GROK_BIN). Install or set GROK_BIN."

# --- compose full headless prompt -------------------------------------------
# Written to a temp file so long briefs never hit ARG_MAX.
COMPOSED="$(mktemp "${TMPDIR:-/tmp}/agent-news-article.XXXXXX")"
cleanup() {
  if [[ "$KEEP_PROMPT" -eq 1 ]]; then
    echo "create-article.sh: prompt file kept: $COMPOSED" >&2
  else
    rm -f "$COMPOSED"
  fi
}
trap cleanup EXIT

cat >"$COMPOSED" <<EOF
You are working in the Agent News satire-news-framework repository.

Follow skill/satire-news-article-generator/SKILL.md exactly end-to-end:
- Create articles/<slug>/article.md + real assets under assets/
- Use image_gen / image_edit for stills only — NEVER call image_to_video or other video tools
- If video is needed, give the user a copy-paste Grok Imagine prompt and wait (do not attempt video gen)
- hero: must be a still image; body uses ![caption](assets/...)
- Verify files with ls + curl /content/<slug>/assets/... → 200 when dev server is up
- Outlet name: Agent News; slogan context: all the news that's fit to tokenize
- No "this is satire" kickers in the article body
- When done, if the user wants it live: git add articles/<slug>/, commit, push (pre-commit rebuilds docs/)
- Use GIT_AUTHOR/COMMITTER env shikkie@users.noreply.github.com if commit identity is missing (do not change global git config)

USER BRIEF (create this article):
────────────────────────────────
${USER_BRIEF}
────────────────────────────────
${GROK_ARTICLE_EXTRA:-}
EOF

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "create-article.sh: dry-run (cwd=${REPO_ROOT}, model=${MODEL})" >&2
  echo "create-article.sh: composed prompt → $COMPOSED" >&2
  cat "$COMPOSED"
  KEEP_PROMPT=1
  exit 0
fi

echo "create-article.sh: repo=${REPO_ROOT}" >&2
echo "create-article.sh: model=${MODEL}" >&2
echo "create-article.sh: brief_chars=${#USER_BRIEF}" >&2

GROK_ARGS=(
  --cwd "$REPO_ROOT"
  --model "$MODEL"
  --prompt-file "$COMPOSED"
  --no-auto-update
)

if [[ "$YOLO" -eq 1 && "${SKIP_YOLO:-0}" != "1" ]]; then
  # Headless article jobs need to write files and commit without prompts
  GROK_ARGS+=(--always-approve --permission-mode bypassPermissions)
fi

# Prefer non-interactive single-shot. --prompt-file alone is headless per docs.
exec "$GROK_BIN" "${GROK_ARGS[@]}"
