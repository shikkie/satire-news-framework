---
name: satire-news-article-generator
description: >
  Create Agent News (agentnews.site) satirical articles with multiple Grok Imagine
  stills: article.md layout, REAL assets on disk, markdown embeds, local verify,
  commit/push. For video: NEVER call image_to_video — give the user an Imagine
  prompt; they return the .mp4 to wire into the story.
---

# Satire News Article Generator

## When to use

Use this skill whenever the user wants a **new satirical article**, **one or more images**, **browser page previews**, or to **publish**. For **video**, do **not** generate it in-session — hand the user a ready Imagine prompt and wait for their file.

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

### 3. Add media (stills in-session; video via user + prompt)

Default to **several** editorial images for an illustrated story (not just a hero).

1. Generate **stills** with `image_gen` / `image_edit` only (load Imagine skill for images).
2. **Do not** call `image_to_video`, `reference_to_video`, or any video tool.
3. If the user wants video (or a clip would help): follow **§ Video (user-provided only)** — give them a copy-paste Imagine prompt + which still to animate; stop and wait for their `.mp4`.
4. **Copy** every binary into `articles/<slug>/assets/` with final kebab-case names.
5. Session dirs (`~/.grok/sessions/.../images/`) are **not** served — always copy.
6. Wire paths: `hero:` (still for OG) + body `![](assets/...)` for images; after user supplies video, `![](assets/<clip>.mp4)`.

### 4. Verify on disk + local preview API

```bash
ls -la articles/<slug>/assets/

# Dev stack (if not already up): ./dev.sh
# Every referenced .jpg/.png/.webp/.mp4/.webm must return 200:
curl -sS -o /dev/null -w "%{http_code}\n" \
  http://127.0.0.1:8787/content/<slug>/assets/<filename>
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

## Critical rule — media must exist on disk

| Required | Forbidden |
|----------|-----------|
| Real files under `articles/<slug>/assets/` | Paths in Markdown with no files |
| `ls` lists every referenced image **and** video | Leaving files only in session folders |
| `curl` → **200** before commit | `manifest.json` or parallel CMS schemas |
| Commit **binaries** with `article.md` | Text-only commit → live 404 media |

---

## Exact folder layout

```text
articles/
└── <slug>/
    ├── article.md
    └── assets/                         # required if any media
        ├── hero-<topic>.jpg            # still for hero + OG (required if illustrated)
        ├── <role>-<topic>.jpg          # additional stills (typical: 2–5)
        ├── <scene>-clip.mp4            # optional inline video(s)
        ├── rendered-article-viewport.jpg   # optional page screenshot
        └── rendered-article-preview.jpg
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
| `hero` | if illustrated | **Still image only** `assets/<file>.jpg` (used for Discord/OG card) |
| `tags` | optional | `[a, b]` |
| `disclaimer` | no | Ignored in UI |

Tiny YAML only (no nested objects).

---

## Media production (Grok Imagine)

Load the **imagine** skill whenever calling image or video tools. Prefer **multiple** assets on illustrated stories.

### When to use what

| Need | Tool | Notes |
|------|------|--------|
| New still | `image_gen` | Photojournalism / wire-photo style; short text only |
| Same subject, new angle | `image_edit` | Pass prior image path for consistency |
| Animate one still | `image_to_video` | `duration` 6 or 10; default 6; `resolution_name` 480p unless asked |
| Multi-still guided clip | `reference_to_video` | 2–7 images + prompt + `aspect_ratio` |
| Social / OG card | Still `hero` | **Never** put `.mp4` in `hero:` — crawlers need an image |

### Multi-image set (typical illustrated article)

Aim for **3–5** stills with distinct roles (skip roles that do not fit the story):

| Role | Filename pattern | Use |
|------|------------------|-----|
| Hero | `hero-<topic>.jpg` | Frontmatter `hero:` + often first body figure |
| Scene / establishment | `scene-<place>.jpg` | Lede support |
| Officials / process | `state-briefing.jpg`, `presser.jpg` | Quotes section |
| Public / social | `social-reaction.jpg` | Reaction beat |
| Document / graphic | `field-card-<topic>.jpg` | Satirical form/UI still |
| Extra B-roll | `<role>-<topic>.jpg` | As needed |

Generate **in parallel** when subjects are independent; use `image_edit` when the same character/object must match across frames.

### Video (optional, when motion helps)

1. Create a strong still first (`image_gen` or `image_edit`).
2. Call `image_to_video` with that image + a short present-tense motion prompt (one clear camera move or subject motion).
3. Copy the returned `.mp4` into `assets/` as `kebab-case-clip.mp4` (or `.webm`).
4. Embed in the body with the **same markdown image syntax** (the SPA renders `.mp4`/`.webm` as `<video controls>`):

```markdown
![Tankers roll past cooling towers at dusk.](assets/campus-tankers-clip.mp4)
```

**Video limits / taste:** prefer one short clip mid-article, not a wall of autoplay. Keep content non-graphic. Prefer 16:9 source stills for clips. OG/Twitter still use `hero` JPG.

### Copy out of session storage (required)

```bash
# Images (example paths — use the tool’s returned path)
cp /path/from/image_gen.jpg articles/<slug>/assets/hero-<topic>.jpg

# Video
cp /path/from/image_to_video.mp4 articles/<slug>/assets/<scene>-clip.mp4

chmod 644 articles/<slug>/assets/*
```

Never leave final paths as `1.jpg` / `5.mp4` from the tool dump names.

---

## Image & video path rules (Markdown)

**Hero (still only):**

```yaml
hero: "assets/hero-example.jpg"
```

**Body — images and videos use the same syntax:**

```markdown
![Hero caption.](assets/hero-example.jpg)

![Officials at the briefing.](assets/state-briefing.jpg)

![Crowd reaction outside city hall.](assets/social-reaction.jpg)

![Slow push over the cooling towers.](assets/cooling-towers-clip.mp4)
```

Also accepted: `/content/<slug>/assets/file.jpg` (SPA rewrites slug if needed).

| Type | Extensions | Renderer |
|------|------------|----------|
| Image | `.jpg` `.jpeg` `.png` `.webp` `.gif` | `<img>` |
| Video | `.mp4` `.webm` `.ogg` `.mov` | `<video controls playsinline>` |

Naming: kebab-case. Prefer `.jpg` for stills, `.mp4` for video.

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
[ ] Plan media: multi stills (roles) ± video if motion helps
[ ] Grok Imagine: image_gen / image_edit (+ image_to_video as needed)
[ ] Copy ALL binaries into assets/ with final names (not session paths only)
[ ] hero: is a STILL image; body ![](assets/...) for each image and .mp4
[ ] Alt/captions match THIS story
[ ] ls assets/ + curl every referenced file → 200
[ ] Optional: rendered-article-viewport.jpg + preview.jpg
[ ] No satire kickers; no manifest.json
[ ] Hooks installed or manual npm run build + git add docs/
[ ] git add articles/<slug>/ (binaries included)
[ ] git commit + git push origin main
[ ] Confirm docs/ updated for Pages
```

### Minimum

```text
articles/<slug>/article.md
```

### Illustrated (multi-image)

```text
articles/<slug>/article.md
articles/<slug>/assets/hero-<topic>.jpg
articles/<slug>/assets/state-briefing.jpg
articles/<slug>/assets/social-reaction.jpg
```

### With video

```text
articles/<slug>/article.md
articles/<slug>/assets/hero-<topic>.jpg      # still for OG
articles/<slug>/assets/<other>.jpg
articles/<slug>/assets/<scene>-clip.mp4      # body embed
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
| Markdown media paths with no files on disk | 404 |
| Leave media only under `~/.grok/sessions/...` | Not served |
| `hero: assets/foo.mp4` | OG/Discord need a still image |
| One lonely stock-ish image when the story has 3+ beats | Prefer multi-role stills |
| Invent `manifest.json` | Framework ignores it |
| Commit `article.md` without asset binaries | Live 404 |
| Forget `docs/` when hooks missing | Pages stays stale |
| End article with “this is satire” lectures | Redundant with site banner |
| Hand-edit `docs/content/` as the source of truth | Overwritten by `npm run build` — edit `articles/` only |
| Autoplay-heavy or graphic violence video | Keep clips short, controls on, tasteful |
