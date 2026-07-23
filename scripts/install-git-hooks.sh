#!/usr/bin/env bash
# Point this clone at .githooks/ (committed) instead of .git/hooks/
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

chmod +x "$ROOT/.githooks/"* 2>/dev/null || true
chmod +x "$ROOT/scripts/install-git-hooks.sh"

# Local config only (never --global)
git config core.hooksPath .githooks

echo "Git hooks installed: core.hooksPath=.githooks"
echo "  pre-commit → npm run build + git add docs/ when site sources are staged"
echo "  Skip once:  SKIP_DOCS_BUILD=1 git commit ..."
echo "  Or:         git commit --no-verify"
