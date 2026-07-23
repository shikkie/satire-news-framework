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
#   ./scripts/create-article.sh --issues              # process GitHub article-request queue
#   ./scripts/create-article.sh --issues --limit 1     # oldest open issue only
#
# Options:
#   -f, --file PATH     Read the full brief from a file
#   -                   Read brief from stdin (also works with no args + pipe/heredoc)
#   -i, --issues        Process open GitHub issues labeled article-request (oldest first)
#   -l, --limit N       With --issues: process at most N issues (default: all)
#   -m, --model NAME    Grok model (omit for CLI default; if set, use grok-4.5)
#   -n, --dry-run       Print the composed prompt; do not invoke grok
#   -k, --keep-prompt   Keep the temp prompt file path on stderr after run
#   -h, --help          Show help
#
# Env:
#   GROK_BIN            Path to grok (default: grok on PATH)
#   GROK_MODEL          Optional model override (only passed if set; prefer grok-4.5)
#   GROK_ARTICLE_EXTRA  Extra text appended to the system brief (optional)
#   ARTICLE_ISSUE_LABEL GitHub label for the queue (default: article-request)
#   SKIP_YOLO=1         Do not pass --always-approve / bypassPermissions
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
GROK_BIN="${GROK_BIN:-grok}"
# Prefer the CLI default model; only pass --model when GROK_MODEL or -m is set.
MODEL="${GROK_MODEL:-}"
DRY_RUN=0
KEEP_PROMPT=0
PROMPT_FILE=""
YOLO=1
ISSUES=0
LIMIT=""
ISSUE_LABEL="${ARTICLE_ISSUE_LABEL:-article-request}"

usage() {
  # Print the leading comment block (usage/docs), stop before code.
  sed -n '2,/^set -euo pipefail$/p' "$0" | sed '$d' | sed 's/^# \?//'
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
    -i|--issues) ISSUES=1; shift ;;
    -l|--limit)
      [[ $# -ge 2 ]] || die "--limit needs a value"
      [[ "$2" =~ ^[1-9][0-9]*$ ]] || die "--limit must be a positive integer"
      LIMIT="$2"
      shift 2
      ;;
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
    -)
      # stdin marker (not an option flag)
      POSITIONAL+=("$1")
      shift
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

if [[ "$ISSUES" -eq 1 && ( -n "$PROMPT_FILE" || $# -gt 0 ) ]]; then
  die "--issues cannot be combined with a free-text brief or --file"
fi
if [[ -n "$LIMIT" && "$ISSUES" -ne 1 ]]; then
  die "--limit only applies with --issues"
fi

# --- resolve user brief (single-shot modes) ---------------------------------
USER_BRIEF=""
if [[ "$ISSUES" -eq 1 ]]; then
  : # filled per issue below
elif [[ -n "$PROMPT_FILE" ]]; then
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
  die "no brief provided. Pass a string, --file PATH, --issues, or pipe/heredoc on stdin.
Example:
  $0 \"Orange kitten calls 911 because breakfast was late...\"
  $0 --issues"
fi

if [[ "$ISSUES" -ne 1 ]]; then
  # Trim leading/trailing whitespace (keep internal newlines)
  USER_BRIEF="$(printf '%s' "$USER_BRIEF" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
  [[ -n "$USER_BRIEF" ]] || die "brief is empty"
fi

command -v "$GROK_BIN" >/dev/null 2>&1 || die "grok not found (GROK_BIN=$GROK_BIN). Install or set GROK_BIN."

# --- prompt helpers ---------------------------------------------------------
compose_prompt() {
  local user_brief="$1"
  local issue_extra="${2:-}"
  cat <<EOF
You are working in the Agent News satire-news-framework repository.

Follow skill/satire-news-article-generator/SKILL.md exactly end-to-end:
- Create articles/<slug>/article.md + real assets under assets/
- Use image_gen / image_edit for stills only — NEVER call image_to_video or other video tools
- If video is needed, give the user a copy-paste Grok Imagine prompt and wait (do not attempt video gen)
- hero: must be a still image; body uses ![caption](assets/...)
- Verify files with ls + curl /content/<slug>/assets/... → 200 when dev server is up
- Outlet name: Agent News; slogan context: all the news that's fit to tokenize
- No "this is satire" kickers in the article body
- When done: git add articles/<slug>/, commit, push (pre-commit rebuilds docs/)
- Use GIT_AUTHOR/COMMITTER env shikkie@users.noreply.github.com if commit identity is missing (do not change global git config)
${issue_extra}
USER BRIEF (create this article):
────────────────────────────────
${user_brief}
────────────────────────────────
${GROK_ARTICLE_EXTRA:-}
EOF
}

run_grok() {
  local user_brief="$1"
  local issue_extra="${2:-}"
  local label="${3:-}"

  local COMPOSED
  COMPOSED="$(mktemp "${TMPDIR:-/tmp}/agent-news-article.XXXXXX")"
  compose_prompt "$user_brief" "$issue_extra" >"$COMPOSED"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "create-article.sh: dry-run (cwd=${REPO_ROOT}, model=${MODEL:-<cli default>}${label:+, ${label}})" >&2
    echo "create-article.sh: composed prompt → $COMPOSED" >&2
    cat "$COMPOSED"
    if [[ "$KEEP_PROMPT" -eq 1 ]]; then
      echo "create-article.sh: prompt file kept: $COMPOSED" >&2
    else
      rm -f "$COMPOSED"
    fi
    return 0
  fi

  echo "create-article.sh: repo=${REPO_ROOT}" >&2
  echo "create-article.sh: model=${MODEL:-<cli default>}" >&2
  [[ -n "$label" ]] && echo "create-article.sh: ${label}" >&2
  echo "create-article.sh: brief_chars=${#user_brief}" >&2

  local GROK_ARGS=(
    --cwd "$REPO_ROOT"
    --prompt-file "$COMPOSED"
    --no-auto-update
  )
  # Only pin a model when explicitly requested (GROK_MODEL / -m). Prefer grok-4.5 if you must.
  if [[ -n "$MODEL" ]]; then
    GROK_ARGS+=(--model "$MODEL")
  fi

  if [[ "$YOLO" -eq 1 && "${SKIP_YOLO:-0}" != "1" ]]; then
    # Headless article jobs need to write files and commit without prompts
    GROK_ARGS+=(--always-approve --permission-mode bypassPermissions)
  fi

  local status=0
  "$GROK_BIN" "${GROK_ARGS[@]}" || status=$?

  if [[ "$KEEP_PROMPT" -eq 1 ]]; then
    echo "create-article.sh: prompt file kept: $COMPOSED" >&2
  else
    rm -f "$COMPOSED"
  fi

  return "$status"
}

# --- issues queue mode ------------------------------------------------------
if [[ "$ISSUES" -eq 1 ]]; then
  command -v gh >/dev/null 2>&1 || die "gh not found (required for --issues). Install GitHub CLI and auth."

  # Resolve issues from this repo (works from any cwd; gh uses git remote).
  cd "$REPO_ROOT"

  # Oldest open first; fields needed for the agent brief.
  # shellcheck disable=SC2016
  ISSUE_JSON="$(
    gh issue list \
      --label "$ISSUE_LABEL" \
      --state open \
      --limit 100 \
      --json number,title,body,url,createdAt \
      --jq 'sort_by(.createdAt)'
  )" || die "failed to list open issues (label=${ISSUE_LABEL})"

  ISSUE_COUNT="$(printf '%s' "$ISSUE_JSON" | jq 'length')"
  if [[ "$ISSUE_COUNT" -eq 0 ]]; then
    echo "create-article.sh: no open issues with label '${ISSUE_LABEL}'" >&2
    exit 0
  fi

  if [[ -n "$LIMIT" && "$ISSUE_COUNT" -gt "$LIMIT" ]]; then
    ISSUE_JSON="$(printf '%s' "$ISSUE_JSON" | jq --argjson n "$LIMIT" '.[0:$n]')"
    ISSUE_COUNT="$LIMIT"
  fi

  echo "create-article.sh: processing ${ISSUE_COUNT} open issue(s) labeled '${ISSUE_LABEL}' (oldest first)" >&2

  FAIL=0
  DONE=0
  while IFS= read -r row; do
    num="$(printf '%s' "$row" | jq -r '.number')"
    title="$(printf '%s' "$row" | jq -r '.title')"
    url="$(printf '%s' "$row" | jq -r '.url')"
    body="$(printf '%s' "$row" | jq -r '.body // ""')"

    brief="$(cat <<EOF
GitHub issue #${num}: ${title}
URL: ${url}

${body}
EOF
)"

    issue_extra="$(cat <<EOF

GITHUB ISSUE QUEUE ITEM:
- This brief comes from open issue #${num} (label: ${ISSUE_LABEL}).
- Comment that you are claiming the issue (or assign yourself) before substantial work.
- One article for this issue only; do not pick other issues in this run.
- After publish: put \`Closes #${num}\` on its own line in the commit message body so GitHub auto-closes the issue on main.
- After push: confirm the issue is closed; if not, close it with a comment linking https://agentnews.site/article/<slug>
- Prefer setting frontmatter published for homepage order when shipping same-day queue stories.

EOF
)"

    echo "create-article.sh: ── issue #${num}: ${title}" >&2
    if run_grok "$brief" "$issue_extra" "issue=#${num}"; then
      DONE=$((DONE + 1))
      echo "create-article.sh: issue #${num} finished ok" >&2
    else
      FAIL=$((FAIL + 1))
      echo "create-article.sh: issue #${num} failed (exit non-zero); continuing queue" >&2
    fi
  done < <(printf '%s' "$ISSUE_JSON" | jq -c '.[]')

  echo "create-article.sh: queue done — ok=${DONE} failed=${FAIL} total=${ISSUE_COUNT}" >&2
  [[ "$FAIL" -eq 0 ]] || exit 1
  exit 0
fi

# --- single brief mode ------------------------------------------------------
run_grok "$USER_BRIEF" ""
exit $?
