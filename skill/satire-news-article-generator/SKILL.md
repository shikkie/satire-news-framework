---
name: satire-news-article-generator
description: >
  Create Agent News (agentnews.site) satirical articles with multiple Grok Imagine
  stills: article.md layout, REAL assets on disk, markdown embeds, local verify,
  commit/push. Always end with the live deep link https://agentnews.site/article/<slug>
  (homepage CDN can lag). For video: NEVER call image_to_video — give the user an
  Imagine prompt; they return the .mp4 to wire into the story. Also processes open
  GitHub issues labeled article-request as work queue.
---

# Satire News Article Generator

## When to use

Use this skill whenever the user wants a **new satirical article**, **one or more images**, **browser page previews**, or to **publish**. For **video**, do **not** generate it in-session — hand the user a ready Imagine prompt and wait for their file.

Repo root:

```text
satire-news-framework/
```

Publication: **Agent News** · **https://agentnews.site**

### Preferred trigger: open GitHub issues (CLI / agent work queue)

The standard way to hand work to the Grok CLI (or any agent following this skill) is via **GitHub Issues**.

1. Look for **open** issues that have the label **`article-request`**.
2. The issue body contains a structured brief (title idea, premise, image guidance, etc.) using the repo’s issue template.
3. When you pick one up:
   - Comment on the issue that you are claiming it (or assign yourself).
   - Follow this skill end-to-end to produce the full article + assets.
   - **Commit + push** with `Closes #N` on its own line in the commit body (links the publish commit to the issue before it is removed):
     - Example: `Closes #12`
   - **After push: close the issue, then delete it** so it cannot be reopened or re-picked from the queue:
     ```bash
     # 1) Close with deep link (if still open)
     gh issue close <N> --comment "Published: https://agentnews.site/article/<slug>"
     # 2) Delete so it leaves the issue list entirely
     gh issue delete <N> --yes
     ```
   - Do **not** leave the issue merely closed — closed items can still clutter the repo and be reopened. **Delete is required** after a successful publish.
   - If delete fails (permissions), leave it closed with the deep-link comment and report the error; do not re-open.
   - Always put the deep link in your **final chat reply** (see **§ Final handoff**) — the issue body will be gone after delete.

**How humans (or upstream agents) file work**

- Use the “Article Request” issue template (`.github/ISSUE_TEMPLATE/article-request.md`).
- Fill in the brief fields (headline idea, slug, premise, image roles, etc.).
- The template automatically applies the `article-request` label.

This keeps a clean, visible queue of pending stories that the CLI can poll or be pointed at.

**Process the whole queue**

```bash
gh issue list --label article-request --state open
# or: gh api "repos/OWNER/REPO/issues?labels=article-request&state=open"
```

Pick the oldest open issue first unless the user says otherwise. One article per issue; one `Closes #N` per commit; then **close + delete** that issue after publish.

### Trigger via script (optional)

From any directory:

```bash
# long free-text brief as one argument
./scripts/create-article.sh "Your article brief here..."

# multi-line / very long
./scripts/create-article.sh --file brief.txt
./scripts/create-article.sh <<'EOF'
multi-line brief...
EOF

# process open GitHub issues labeled article-request (oldest first)
./scripts/create-article.sh --issues
./scripts/create-article.sh --issues --limit 1   # oldest only

# preview composed prompt only
./scripts/create-article.sh --dry-run "brief..."
./scripts/create-article.sh --issues --dry-run
```

The script `cd`s/`--cwd`s to the repo root, wraps **grok** headless (`--prompt-file`, `--always-approve`), and injects instructions to follow this skill. With `--issues`, it lists open issues via `gh`, runs one Grok job per issue (oldest first), and injects `Closes #N` + **close then delete** instructions. Env: `GROK_BIN`, `GROK_MODEL`, `ARTICLE_ISSUE_LABEL` (default `article-request`), `SKIP_YOLO=1`.

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

# If this story came from a GitHub issue, put Closes #N in the commit body
# (associates the publish commit; you will still close + delete after push).
git commit -m "$(cat <<'EOF'
Add satirical article: <slug>

Story + assets under articles/<slug>/ (docs/ rebuilt by pre-commit when hooks are on).

Closes #<issue-number>
EOF
)"

git push -u origin HEAD
```

After push (issue-sourced work) — **close then delete** (required):

```bash
gh issue close <N> --comment "Published: https://agentnews.site/article/<slug>"
gh issue delete <N> --yes
```

Queue only lists **open** issues, but **delete** removes the ticket entirely so it cannot be reopened or re-labeled into the queue. Put the deep link in the final chat reply; the issue will no longer exist to hold it.

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
| CDN | Fastly edge often caches ~**10 minutes** — **homepage feed can lag**; deep article URLs usually work sooner |

There is **no** user-facing CDN purge. Prefer deep links over “check the homepage.”

### 7. Final handoff (required — every story)

When work is done (after push, or after local-only verify if the user asked not to publish), **end your last reply** with the direct deep links. Do **not** only say “live on the homepage” or make the user hunt for the slug.

**Required block (use real values):**

```text
## Live links
- Article (deep link): https://agentnews.site/article/<slug>
- Local preview: http://127.0.0.1:5173/article/<slug>
- Slug: <slug>
```

If the story is not pushed yet, still give the deep-link **shape** and mark it as “after Pages deploy”:

```text
## Links (after push + Pages deploy)
- Article (deep link): https://agentnews.site/article/<slug>
```

**Why:** GitHub Pages’ CDN can leave `articles-data.json` / the homepage stale for up to ~10 minutes after deploy. The path `/article/<slug>/` (and its OG HTML under `docs/article/<slug>/`) is the reliable way to open the new story without waiting for the homepage feed to refresh.

**Also verify once after push (best effort):**

```bash
curl -sS -o /dev/null -w "%{http_code}\n" \
  https://agentnews.site/article/<slug>/
```

Report the status code next to the deep link when you have it (200 = good; 404 = Pages not deployed yet — deep link still the URL to retry).

Multiple stories in one run: list **one deep link per slug**.

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
published: "YYYY-MM-DDTHH:MM:SSZ"   # optional; precise homepage order
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
| `date` | yes | ISO `YYYY-MM-DD` (display + sort) |
| `published` | optional | Full ISO datetime; preferred for homepage order when several stories share a calendar day |
| `section` | yes | `Local` \| `Politics` \| `Business` \| `Tech` \| `Culture` \| `Opinion` \| `World` |
| `hero` | if illustrated | **Still image only** `assets/<file>.jpg` (used for Discord/OG card) |
| `tags` | optional | `[a, b]` |
| `disclaimer` | no | Ignored in UI |

**Homepage order:** `published` → `date` → git commit time on the article folder (else `article.md` mtime). Prefer setting `published` when shipping multiple same-day queue stories.

Tiny YAML only (no nested objects).

---

## Media production (Grok Imagine)

Load the **imagine** skill for **still** image tools only. Prefer **multiple** stills on illustrated stories.

### When to use what

| Need | Action | Notes |
|------|--------|--------|
| New still | `image_gen` | Photojournalism / wire-photo style; short text only |
| Same subject, new angle | `image_edit` | Pass prior image path for consistency |
| Social / OG card | Still `hero` | **Never** put `.mp4` in `hero:` |
| **Video / clip** | **Do not call video tools** | Give user an Imagine prompt; they return the file |

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

### Video (user-provided only — never generate in-agent)

**Forbidden:** `image_to_video`, `reference_to_video`, `video_gen`, or any attempt to animate in this session.

When the user asks for video (or a clip would help):

1. Generate (or pick) a strong **still** first and save it under `assets/` (e.g. `interview-still.jpg`).
2. Reply with a **ready-to-paste Imagine prompt** and clear handoff instructions — do **not** call video tools.
3. Wait for the user to return a `.mp4` (path or file).
4. Copy it to `articles/<slug>/assets/<scene>-clip.mp4`, embed, verify, then commit if publishing.

**Prompt template to give the user** (fill in specifics):

```text
Use Grok Imagine image-to-video on this still:
  <absolute path or describe which asset, e.g. articles/<slug>/assets/interview-still.jpg>

Motion prompt (paste as-is or tweak):
  <one short present-tense beat: subject motion + optional slow camera push-in; 1–2 sentences>

Settings: 6s (or 10s), 480p unless you want 720p, match the still’s aspect (prefer 16:9).

When done, save/export the .mp4 and put it here (or tell the agent the path):
  articles/<slug>/assets/<scene>-clip.mp4
```

**Example filled prompt:**

```text
Image-to-video source:
  articles/orange-kitten-calls-911-hungry/assets/kitten-interview-still.jpg

Motion:
  adorable orange kitten faces the camera and softly blinks, tiny head tilt as if
  answering a question, gentle camera push-in, warm morning light

6 seconds, 480p. Save as:
  articles/orange-kitten-calls-911-hungry/assets/kitten-interview-clip.mp4
```

After the user drops the file:

```markdown
![Cheddar’s interview — soft blinks, hard allegations.](assets/kitten-interview-clip.mp4)
```

The SPA renders `.mp4`/`.webm` as `<video controls>`. Prefer one short clip mid-article. Never mention tool failures or “video unavailable” in the article body.

### Copy out of session storage (required for stills)

```bash
cp /path/from/image_gen.jpg articles/<slug>/assets/hero-<topic>.jpg
chmod 644 articles/<slug>/assets/*
```

For user-supplied video:

```bash
cp /path/user/gave.mp4 articles/<slug>/assets/<scene>-clip.mp4
chmod 644 articles/<slug>/assets/<scene>-clip.mp4
```

Never leave final paths as `1.jpg` / tool dump names.

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
[ ] Plan media: multi stills (roles)
[ ] Grok Imagine stills only: image_gen / image_edit — NEVER image_to_video
[ ] If user wants video: give Imagine prompt + still path; wait for their .mp4
[ ] Copy ALL binaries into assets/ with final names
[ ] hero: is a STILL; body ![](assets/...) for images; .mp4 only after user file exists
[ ] Alt/captions match THIS story; no “video unavailable” mishap text
[ ] ls assets/ + curl every referenced file → 200
[ ] Optional: rendered-article-viewport.jpg + preview.jpg
[ ] No satire kickers; no manifest.json
[ ] Hooks installed or manual npm run build + git add docs/
[ ] git add articles/<slug>/ (binaries included)
[ ] git commit with Closes #N in body (when from an issue) + git push origin main
[ ] Confirm docs/ updated for Pages
[ ] If from a GitHub issue: gh issue close <N> (deep-link comment) then gh issue delete <N> --yes
[ ] FINAL REPLY: paste https://agentnews.site/article/<slug> (deep link) — not just “check homepage”
[ ] Optional: curl live deep link → report 200/404
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
| `orange-kitten-calls-911-hungry` | Multi-still local satire; interview as still + transcript |
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
| Calling `image_to_video` / video tools in this agent | Broken on ZDR — user runs Imagine; agent only prompts |
| “Video generation unavailable” in article copy | Never; use still + clean prose until user supplies .mp4 |
| Autoplay-heavy or graphic violence video | Keep clips short, controls on, tasteful |
| Finish without pasting `https://agentnews.site/article/<slug>` | User needs the deep link while homepage CDN lags |
| Tell user only to “refresh the homepage” | Feed JSON can stay stale ~10 min; deep path is the fix |
| Leave article-request issues merely closed after publish | Close **then delete** (`gh issue delete N --yes`) so they cannot re-enter the queue |
