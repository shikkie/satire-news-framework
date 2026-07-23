---
name: satire-news-article-generator
description: >
  Create complete Agent News (agentnews.site) satirical articles: folder layout,
  article.md, REAL assets on disk, local verify, optional browser previews, then
  commit/push so pre-commit rebuilds docs/ for GitHub Pages. Use when drafting,
  illustrating, or publishing stories.
---

# Satire News Article Generator

## When to use

Use this skill whenever the user wants a **new satirical article**, images for a story, **browser page previews**, or to **publish** so it appears on local preview and (after push) GitHub Pages.

Repo root:

```text
satire-news-framework/
```

Publication: **Agent News** · **https://agentnews.site**

---

## End-to-end workflow (do in order)

### 1. Create the story folder

```bash
# List existing slugs first
ls articles/

mkdir -p articles/<slug>/assets
```

Slug = folder name: lowercase, hyphens only, unique, stable forever.

### 2. Write `articles/<slug>/article.md`

Frontmatter + body (schema below). Outlet name: **Agent News**.  
**Do not** add “this is satire” kickers — the site has one top banner.

### 3. Add real image files (if illustrated)

1. Generate with image tools (photojournalism / editorial; avoid long in-image text).
2. **Copy** into `articles/<slug>/assets/` with final kebab-case names.
3. Session dirs (`~/.grok/sessions/.../images/`) are **not** served — always copy.
4. Wire paths: `hero: "assets/..."` and body `![](assets/...)`.

### 4. Verify on disk + local preview API

```bash
ls -la articles/<slug>/assets/

# Dev stack (if not already up): ./dev.sh
curl -sS -o /dev/null -w "%{http_code}\n" \
  http://127.0.0.1:8787/content/<slug>/assets/<filename>.jpg
# Expect 200 for every image referenced in article.md
```

Also: `curl -sS http://127.0.0.1:8787/api/articles/<slug>` should return title + body.

Preview / share URLs (**path routes**, not hash — required for Discord/social OG):

```text
http://127.0.0.1:5173/article/<slug>
http://bandit:5173/article/<slug>
https://agentnews.site/article/<slug>
```

Legacy `#/article/<slug>` links redirect to the path form.

### 5. Optional — browser page screenshots

When the user asks for a “preview,” “render,” or “what it looks like”:

```bash
# Requires: ./dev.sh running, playwright installed (devDependency)
# Write into articles/<slug>/assets/:
#   rendered-article-viewport.jpg  (first screen)
#   rendered-article-preview.jpg   (full page)
```

Use Playwright against `http://127.0.0.1:5173/article/<slug>`, convert PNG→JPG, commit with the story if useful. See existing articles for naming.

### 6. Publish (git) — live GitHub Pages via `docs/`

Git is the CMS. **Binary assets must be committed.**

```bash
# Ensure hooks (once per clone; also runs on npm install)
npm run hooks:install   # sets core.hooksPath=.githooks

git status
git add articles/<slug>/
# include skill/app fixes only if intentional

git commit -m "$(cat <<'EOF'
Add satirical article: <slug>

Story + assets under articles/<slug>/ (docs/ rebuilt by pre-commit when hooks are on).
EOF
)"

git push -u origin HEAD
```

#### What pre-commit does (if hooks installed)

| Condition | Action |
|-----------|--------|
| Staged paths match `articles/`, `src/`, `public/`, `index.html`, `package.json`, `vite.config.*`, or `scripts/build-articles*` | Runs `npm run build` → writes **`docs/`** → `git add docs/` into the **same** commit |
| Hooks missing / `node_modules` missing | Commit may fail or skip rebuild — fix and retry |

**Skip rebuild once:** `SKIP_DOCS_BUILD=1 git commit ...` or `git commit --no-verify`

#### If hooks are not installed

Manually:

```bash
npm run build          # → docs/
git add articles/<slug>/ docs/
git commit -m "..."
git push
```

#### Git author fallback (this machine often has no global identity)

Do **not** change global git config unless asked. For one commit only:

```bash
GIT_AUTHOR_NAME="shikkie" \
GIT_AUTHOR_EMAIL="shikkie@users.noreply.github.com" \
GIT_COMMITTER_NAME="shikkie" \
GIT_COMMITTER_EMAIL="shikkie@users.noreply.github.com" \
git commit -m "..."
```

Remote: `https://github.com/shikkie/satire-news-framework.git` · branch **`main`**.

#### How the live site updates (no GitHub Actions)

| Step | What happens |
|------|----------------|
| Push to `main` | Includes `articles/<slug>/` + rebuilt `docs/` |
| GitHub Pages | **Settings → Deploy from a branch → `main` → `/docs`** serves latest committed `docs/` |
| Custom domain | `docs/CNAME` / `public/CNAME` = **agentnews.site** |

---

## Critical rule — images must exist on disk

| Required | Forbidden |
|----------|-----------|
| Real files under `articles/<slug>/assets/` | Paths in Markdown with no files |
| `ls` lists every referenced file | Leaving files only in session image folders |
| `curl` → **200** before commit | `manifest.json` or parallel CMS schemas |
| Commit **binaries** with `article.md` | Committing text only → live 404 images |

---

## Exact folder layout

```text
articles/
└── <slug>/
    ├── article.md
    └── assets/                    # required if any images
        ├── hero-<topic>.jpg
        ├── <role>-<topic>.jpg
        ├── rendered-article-viewport.jpg   # optional
        └── rendered-article-preview.jpg  # optional
```

### Slug rules

| Rule | Detail |
|------|--------|
| Characters | `a-z`, `0-9`, hyphens only |
| No | spaces, underscores, camelCase, numeric prefixes like `37374-...` |
| Uniqueness | must not collide with `articles/*/` |

### Do not create

- `articles/manifest.json`
- `article.md` anywhere except `articles/<slug>/article.md`
- Images under `public/`, `src/`, or `docs/content/` by hand (build copies into `docs/`)

---

## `article.md` frontmatter

```yaml
---
title: "Punchy satirical headline"
dek: "One-line deck that sharpens the joke"
author: "Fictional byline"
date: "YYYY-MM-DD"
section: "Local"
hero: "assets/hero-<topic>.jpg"
tags: ["tag1", "tag2"]
---
```

| Field | Required | Rules |
|-------|----------|--------|
| `title` | yes | Quoted string |
| `dek` | recommended | One sentence |
| `author` | yes | Fictional; outlet is **Agent News** |
| `date` | yes | ISO `YYYY-MM-DD` (homepage sorts newest first) |
| `section` | yes | `Local` \| `Politics` \| `Business` \| `Tech` \| `Culture` \| `Opinion` \| `World` |
| `hero` | if hero image | `assets/<file>` relative to article folder |
| `tags` | optional | `[a, b]` |
| `disclaimer` | no | Ignored in UI |

Tiny YAML only (no nested objects).

---

## Image path rules

**Hero:**

```yaml
hero: "assets/hero-example.jpg"
```

**Body (preferred):**

```markdown
![Caption for this story.](assets/hero-example.jpg)
```

Also accepted: `/content/<slug>/assets/file.jpg` (SPA rewrites slug if needed).

Naming: kebab-case; `hero-<topic>.jpg`, `social-reaction.jpg`, `state-briefing.jpg`, etc.  
Prefer `.jpg` / `.png` / `.webp`. Never leave files as `5.jpg` from the generator.

---

## How the site discovers articles

| Layer | Behavior |
|-------|----------|
| Local API | `preview/server.py` scans `articles/*/article.md` (port **8787**) |
| List / one | `GET /api/articles`, `GET /api/articles/<slug>` |
| Assets | `GET /content/<slug>/…` → `articles/<slug>/` |
| Dev UI | Vite **5173**, proxies `/api` + `/content` |
| Article URL | `/article/<slug>` (static HTML + OG tags for social) |
| Production | Static snapshot in **`docs/`** (no Python on Pages) |
| Social preview | Build injects `docs/article/<slug>/index.html` with `og:title`, `og:description`, `og:image` |

```bash
./dev.sh status    # API + Vite
./dev.sh           # start if needed
```

---

## Agent checklist (every story)

```text
[ ] ls articles/ — unique kebab-case slug
[ ] mkdir -p articles/<slug>/assets
[ ] Write articles/<slug>/article.md (frontmatter + body)
[ ] Generate/copy REAL images into assets/ (if illustrated)
[ ] hero: + body ![](assets/...) match on-disk filenames
[ ] Alt captions match THIS story
[ ] ls assets/ + curl each /content/<slug>/assets/... → 200
[ ] Optional: rendered-article-viewport.jpg + preview.jpg if user wants screenshots
[ ] No satire kickers; no manifest.json
[ ] npm run hooks:install if pre-commit not active (or npm run build + git add docs/)
[ ] git add articles/<slug>/  (+ docs/ if no hook)
[ ] git commit (pre-commit rebuilds docs/ when hooks work)
[ ] git push origin main
[ ] Confirm commit includes docs/ if publishing for Pages
```

### Minimum

```text
articles/<slug>/article.md
```

### Illustrated

```text
articles/<slug>/article.md
articles/<slug>/assets/hero-<topic>.jpg
articles/<slug>/assets/<other>.jpg
```

### After commit (what should be in git)

```text
articles/<slug>/**          # source of truth
docs/**                     # static site for Pages (from build / pre-commit)
```

Do **not** commit: `node_modules/`, `dist/`, `pages/`, `.pids/`, `logs/`, `.env`, `public/content/`, `public/articles-data.json` (regenerated by build).

---

## Writing rules

1. Deadpan news parody voice — clearly satirical, not a real-world hoax for harm  
2. Fictional names for private individuals; care with real orgs  
3. Call the outlet **Agent News**  
4. ~300–700 words unless asked  
5. Structure: lede → quote → subheads → kicker  
6. **No** body disclaimers (“this is satire”) — site banner only  

---

## Reference examples

| Spec | Pattern |
|------|---------|
| `california-trans-buck-harvest` | Full illustrated + page screenshots |
| `jimothy-maga-raccoon-scandal` | Illustrated; relative `assets/` paths |
| `data-centers-buy-bottled-water` | Business satire + previews |
| `barista-butcher-teytey-arrested` | Longform crime pastiche + assets |
| `city-council-bans-gravity` | Text-only (no `assets/`) |

---

## Anti-patterns

| Don’t | Why |
|-------|-----|
| Markdown image paths with no files on disk | 404 |
| Leave images only under `~/.grok/sessions/...` | Not served |
| Invent `manifest.json` | Framework ignores it |
| Commit `article.md` without asset binaries | Live 404 |
| Forget `docs/` when hooks missing | Pages stays stale |
| End article with “this is satire” lectures | Redundant with site banner |
| Hand-edit `docs/content/` as the source of truth | Overwritten by `npm run build` — edit `articles/` only |
