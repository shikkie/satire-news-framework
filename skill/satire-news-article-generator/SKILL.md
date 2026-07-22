---
name: satire-news-article-generator
description: >
  Create complete satirical news articles for satire-news-framework: folder layout,
  article.md frontmatter, assets naming, inline image URLs, git commit/push to go live.
  Use when drafting, illustrating, or publishing Municipal Ledger stories.
---

# Satire News Article Generator

## When to use

Use this skill whenever the user wants a **new satirical article**, images for a story, or to **publish** a story so it appears on the live site / local preview.

Repo root (always work relative to this):

```text
satire-news-framework/
```

Canonical site name in UI: **The Municipal Ledger**.

---

## Exact folder layout (required)

Every story is **one directory** under `articles/`. Nothing else is the CMS.

```text
articles/
└── <slug>/
    ├── article.md          # REQUIRED — frontmatter + body
    └── assets/             # REQUIRED if any images (create even for one file)
        ├── hero-<topic>.jpg
        ├── <descriptive-name>.jpg
        └── ...
```

### Slug rules

| Rule | Detail |
|------|--------|
| Source of truth | **Folder name** = URL slug |
| Characters | lowercase `a-z`, digits `0-9`, hyphens `-` only |
| No | spaces, underscores, camelCase, dots, emoji |
| Length | prefer 3–8 words, stable forever (do not rename after publish) |
| Uniqueness | must not collide with existing `articles/*/` folders |

**Good:** `california-trans-buck-harvest`  
**Bad:** `California_Trans_Buck`, `article1`, `new-post.md`

### File names

| File | Path | Notes |
|------|------|--------|
| Story | `articles/<slug>/article.md` | Only this filename is scanned by the preview API |
| Assets | `articles/<slug>/assets/<file>` | Never put images next to `article.md` without `assets/` |
| Hero field | relative to article folder | e.g. `assets/hero-doe.jpg` (not absolute) |

**Asset naming conventions:**

```text
assets/hero-<short-topic>.jpg     # main hero (frontmatter hero:)
assets/state-briefing.jpg         # officials / press
assets/social-reaction.jpg        # crowd / social vibe
assets/field-card-<topic>.jpg     # documents / graphics
assets/<role>-<topic>.jpg         # kebab-case, descriptive
```

- Prefer **`.jpg`** (or `.jpeg` / `.png` / `.webp`).
- kebab-case only; no spaces.
- Do not use `image1.jpg` — name by role.

---

## `article.md` frontmatter (exact schema)

```yaml
---
title: "Punchy satirical headline"
dek: "One-line deck that sharpens the joke"
author: "Fictional byline"
date: "YYYY-MM-DD"
section: "Politics"
hero: "assets/hero-<topic>.jpg"
tags: ["tag1", "tag2"]
disclaimer: true
---
```

| Field | Required | Values / rules |
|-------|----------|----------------|
| `title` | yes | Quoted string; headline case |
| `dek` | recommended | Subhead; one sentence |
| `author` | yes | Fictional byline (e.g. Sam Ortega, Morgan Quill) |
| `date` | yes | ISO `YYYY-MM-DD` (sorts newest first on homepage) |
| `section` | yes | One of: `Local` \| `Politics` \| `Business` \| `Tech` \| `Culture` \| `Opinion` \| `World` |
| `hero` | if hero image | Path **relative to article folder**: `assets/<file>` |
| `tags` | optional | YAML list of lowercase strings |
| `disclaimer` | yes | `true` unless user explicitly says otherwise |

**Do not** put comments inside the YAML block. Keep frontmatter simple (the parser is a tiny YAML subset: keys, quoted strings, booleans, `[list, items]`).

---

## Body Markdown rules

### Structure

1. Lede (who / what / where / when) — deadpan news voice  
2. Supporting graf + pull quote (`> …`)  
3. Inline images with captions (see below)  
4. Subheads `###` for “what it means”, reactions, fine print  
5. Kicker  
6. Optional italic satire reminder at the end  

### Length

~300–700 words unless user asks otherwise.

### Writing rules

1. **Clearly satirical** — absurd premise, deadpan delivery; not a real-news hoax meant to deceive offline.
2. Prefer **fictional names** for officials, influencers, orgs. No real private individuals as defamation targets.
3. Leave `disclaimer: true`.
4. Do not invent binary image files in prose — **generate or copy real files** into `assets/`.

---

## Images — exact URL conventions

### Hero (top of article)

Frontmatter only:

```yaml
hero: "assets/hero-doe.jpg"
```

The app resolves this to:

```text
/content/<slug>/assets/hero-doe.jpg
```

### Inline images in the body (required pattern)

Use an **absolute content path** so local preview and static builds resolve correctly:

```markdown
![Caption text shown under the image.](/content/<slug>/assets/<filename>.jpg)
```

**Example** (slug = `california-trans-buck-harvest`):

```markdown
![A doe in California oak woodland.](/content/california-trans-buck-harvest/assets/hero-doe.jpg)
```

| Do | Don’t |
|----|--------|
| `/content/<slug>/assets/foo.jpg` | `assets/foo.jpg` alone in body (breaks on some routes) |
| `/content/<slug>/assets/foo.jpg` | `./assets/foo.jpg` |
| Real files on disk under `articles/<slug>/assets/` | Placeholder URLs or missing files |
| Descriptive `alt` text (becomes figcaption) | Empty alt for meaningful photos |

Relative `assets/…` in body is auto-rewritten by the SPA when possible, but **always write the `/content/<slug>/assets/…` form** so other tools and static snapshots stay correct.

### Generating images

When the user wants images (or the story needs them):

1. Create `articles/<slug>/assets/` first.
2. Generate with image tools (photojournalism / editorial style; avoid unreadable long text in-image).
3. Save/copy into `articles/<slug>/assets/` with the names used in frontmatter and Markdown.
4. Set `hero:` and add 1–4 inline figures.

Typical set: **hero**, **official/state**, **document/graphic**, **public/social reaction**.

---

## How the site discovers articles

| Layer | Behavior |
|-------|----------|
| Local preview API | Scans `articles/*/article.md` (`preview/server.py`, port **8787**) |
| List endpoint | `GET /api/articles` |
| One story | `GET /api/articles/<slug>` |
| Assets | `GET /content/<slug>/…` → files under `articles/<slug>/` |
| Frontend | Vite **5173**, proxies `/api` and `/content` |
| Homepage order | By `date` descending |
| Article URL (hash router) | `/#/article/<slug>` |

**Full local preview URLs:**

```text
http://127.0.0.1:5173/#/article/<slug>
http://bandit:5173/#/article/<slug>
http://192.168.1.17:5173/#/article/<slug>
```

Start stack: `./dev.sh` from repo root.

---

## Agent checklist (do every time)

```text
[ ] Pick unique slug (list articles/ first)
[ ] mkdir -p articles/<slug>/assets
[ ] Write articles/<slug>/article.md with full frontmatter
[ ] Put image files only under articles/<slug>/assets/
[ ] hero: "assets/<file>" matches a real file
[ ] Inline images use /content/<slug>/assets/<file>
[ ] disclaimer: true
[ ] Preview: curl /api/articles/<slug> and open /#/article/<slug>
[ ] If user wants live/GitHub: commit + push (see below)
```

### Minimum file set

```text
articles/<slug>/article.md
```

### Typical illustrated set

```text
articles/<slug>/article.md
articles/<slug>/assets/hero-<topic>.jpg
articles/<slug>/assets/state-briefing.jpg
articles/<slug>/assets/social-reaction.jpg
articles/<slug>/assets/field-card-<topic>.jpg
```

---

## Publish to GitHub (make it “live” in the repo)

Git **is** the CMS. Pushing `articles/<slug>/` is enough for any clone or CI that builds the site.

### When user says commit / push / publish / go live

From **repo root** (`satire-news-framework/`):

```bash
# 1. See what will ship
git status
git diff --stat

# 2. Stage only this story (and any skill/app fixes if intentional)
git add articles/<slug>/
# optional related fixes:
# git add skill/satire-news-article-generator/SKILL.md src/ ...

# 3. Commit (use HEREDOC; never secrets)
git commit -m "$(cat <<'EOF'
Add satirical article: <slug>

<One sentence on the premise and that assets live under articles/<slug>/assets.>
EOF
)"

# 4. Push main
git push -u origin HEAD
```

If `git commit` fails on missing author identity, set for that command only (do **not** rewrite global git config unless the user asks):

```bash
GIT_AUTHOR_NAME="shikkie" \
GIT_AUTHOR_EMAIL="shikkie@users.noreply.github.com" \
GIT_COMMITTER_NAME="shikkie" \
GIT_COMMITTER_EMAIL="shikkie@users.noreply.github.com" \
git commit -m "..."
```

Remote expected: `https://github.com/shikkie/satire-news-framework.git` branch **`main`**.

### Static GitHub Pages build (when deploying the SPA)

After articles are on `main`, a production build snapshots Markdown + copies assets:

```bash
npm run articles:build   # → public/articles-data.json + public/content/<slug>/...
npm run build            # → dist/
```

Agents writing a story do **not** need to run the Pages build unless the user asks to deploy; **pushing `articles/<slug>/` is the primary publish step**.

### Do not commit

- `node_modules/`, `dist/`, `.pids/`, `logs/`, `.dev/`, `.env`

---

## After writing (tell the user)

1. Path: `articles/<slug>/article.md`  
2. Preview: `http://bandit:5173/#/article/<slug>` (or localhost)  
3. If pushed: commit SHA / that `origin/main` has the folder  
4. Offer a second headline or social blurb if useful  

---

## Reference examples in this repo

| Slug | Notes |
|------|--------|
| `city-council-bans-gravity` | Text-only sample |
| `startup-pivots-to-vibes` | Text-only sample |
| `weather-apologizes` | Text-only sample |
| `california-trans-buck-harvest` | Full illustrated pattern (hero + inline `/content/...` images) |

Copy the **california-trans-buck-harvest** layout when shipping images.

---

## Anti-patterns

| Don’t | Do instead |
|-------|------------|
| Put `article.md` at repo root | `articles/<slug>/article.md` |
| Name the markdown file something other than `article.md` | Always `article.md` |
| Store images in `public/` or `src/` for a story | `articles/<slug>/assets/` |
| Use uppercase slugs | kebab-case lowercase |
| Link images as `https://…` placeholders | Real local files + `/content/...` paths |
| Edit SPA components for each story | Only add an article folder |
| Skip disclaimer | `disclaimer: true` |
| Commit secrets or API keys | Never required for articles |
