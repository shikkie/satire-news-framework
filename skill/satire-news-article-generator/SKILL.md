---
name: satire-news-article-generator
description: >
  Create complete satirical news articles for Agent News (agentnews.site): folder
  layout, article.md frontmatter, REAL image files under assets/, image path rules,
  verification, and git commit/push. Use when drafting, illustrating, or publishing.
---

# Satire News Article Generator

## When to use

Use this skill whenever the user wants a **new satirical article**, images for a story, or to **publish** a story so it appears on the live site / local preview.

Repo root:

```text
satire-news-framework/
```

Publication: **Agent News** · **https://agentnews.site**

---

## Critical rule — images must exist on disk

**Broken images always mean missing files or wrong paths.** Writing Markdown that *names* an image is not enough.

| Required | Forbidden |
|----------|-----------|
| Real binary files under `articles/<slug>/assets/` | Referencing `assets/foo.jpg` when the file was never written |
| `ls articles/<slug>/assets/` shows every file you mention | Placeholder paths, remote URLs you did not download |
| `hero:` filename matches a file on disk | Inventing `manifest.json` or a parallel CMS schema |
| Generate/copy images **before** or **immediately after** writing paths | Ending the task with 404 image URLs |

### Mandatory verify (do not skip)

```bash
# From repo root — every path in article.md must exist:
ls -la articles/<slug>/assets/

# Local preview API (dev stack: ./dev.sh)
curl -sS -o /dev/null -w "%{http_code}\n" \
  http://127.0.0.1:8787/content/<slug>/assets/<filename>.jpg
# Expect 200 for each image. 404 = you are not done.
```

If any image is **404**, create or copy the file, then re-check. **Do not commit a story with broken assets.**

---

## Exact folder layout (required)

```text
articles/
└── <slug>/
    ├── article.md              # REQUIRED — only this filename is scanned
    └── assets/                 # REQUIRED if any images
        ├── hero-<topic>.jpg    # matches frontmatter hero:
        ├── social-reaction.jpg
        └── <role>-<topic>.jpg
```

### Slug rules

| Rule | Detail |
|------|--------|
| Source of truth | **Folder name** = URL slug |
| Characters | lowercase `a-z`, digits `0-9`, hyphens `-` only |
| No | spaces, underscores, camelCase, dots, emoji |
| Uniqueness | must not collide with existing `articles/*/` |

**Good:** `jimothy-maga-raccoon-scandal`  
**Bad:** `Jimothy_Scandal`, `37374-beloved-raccoon-...` (random numeric prefixes)

### Do not create

- `articles/manifest.json` — **not used** by this framework
- `articles/<slug>/index.md` or `post.md` — only **`article.md`**
- Images under `public/`, `src/`, or session folders without copying into `articles/<slug>/assets/`
- Duplicate parallel slug folders for the same story

---

## `article.md` frontmatter (exact schema)

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
| `author` | yes | Fictional byline; outlet is **Agent News** |
| `date` | yes | ISO `YYYY-MM-DD` (homepage sorts newest first) |
| `section` | yes | `Local` \| `Politics` \| `Business` \| `Tech` \| `Culture` \| `Opinion` \| `World` |
| `hero` | if hero image | **`assets/<filename>` only** — relative to the article folder, not `/content/...` |
| `tags` | optional | YAML list `[a, b]` |
| `disclaimer` | no | Optional / ignored in UI. Site-wide banner is the only satire notice. |

Tiny YAML only: keys, quoted strings, booleans, `[lists]`. No nested objects.

---

## Image path rules (get this right)

### 1. Hero (frontmatter)

```yaml
hero: "assets/hero-jimothy-maga.jpg"
```

The app serves this as:

```text
/content/<slug>/assets/hero-jimothy-maga.jpg
```

### 2. Inline body images — preferred form

**Prefer short relative paths** (the SPA rewrites them using the article slug):

```markdown
![Caption under the image.](assets/hero-jimothy-maga.jpg)
![Activists react.](assets/social-reaction.jpg)
```

Also accepted (rewritten to the article’s real slug if mistyped):

```markdown
![Caption.](/content/<slug>/assets/hero-jimothy-maga.jpg)
```

### 3. Asset naming

```text
assets/hero-<topic>.jpg
assets/social-reaction.jpg
assets/state-briefing.jpg
assets/<role>-<topic>.jpg
```

- kebab-case, no spaces  
- Prefer `.jpg` / `.jpeg` / `.png` / `.webp`  
- Never `image1.jpg` or session dump names like `5.jpg` in the final path  

### 4. Generating images (workflow)

1. `mkdir -p articles/<slug>/assets`
2. Generate with image tools (photojournalism / editorial; avoid long in-image text)
3. **Copy** outputs into `articles/<slug>/assets/` with final names:
   ```bash
   cp /path/to/generated.jpg articles/<slug>/assets/hero-<topic>.jpg
   chmod 644 articles/<slug>/assets/*
   ```
4. Set `hero:` and body `![...](assets/...)` to those **exact** filenames
5. Run the **Mandatory verify** curls above
6. Only then commit

Session folders (e.g. `~/.grok/sessions/.../images/`) are **not** public. Always copy into the article `assets/` tree.

### 5. Alt text / captions

Alt text becomes the figcaption. Write a caption for **this** story (do not paste captions from another article).

---

## How the site discovers articles

| Layer | Behavior |
|-------|----------|
| Preview API | Scans `articles/*/article.md` only (`preview/server.py`, port **8787**) |
| List | `GET /api/articles` |
| One story | `GET /api/articles/<slug>` |
| Assets | `GET /content/<slug>/…` → files under `articles/<slug>/` |
| Frontend | Vite **5173**, proxies `/api` + `/content` |
| Article URL | `/#/article/<slug>` |

```text
http://bandit:5173/#/article/<slug>
http://127.0.0.1:5173/#/article/<slug>
```

Start: `./dev.sh` from repo root.

---

## Agent checklist (every story)

```text
[ ] List existing articles/ — pick a unique kebab-case slug
[ ] mkdir -p articles/<slug>/assets
[ ] Write articles/<slug>/article.md (frontmatter + body)
[ ] Generate/copy REAL image files into assets/ (if illustrated)
[ ] hero: "assets/..." matches an on-disk file
[ ] Body images use ![caption](assets/filename.jpg)
[ ] Alt captions match this story
[ ] ls articles/<slug>/assets/ lists every referenced file
[ ] curl each /content/<slug>/assets/... → HTTP 200
[ ] Refer to outlet as Agent News; do NOT add “this is satire” kickers (site banner covers it)
[ ] Do NOT create articles/manifest.json
[ ] If user wants live: git add articles/<slug>/ && commit && push
```

### Minimum

```text
articles/<slug>/article.md
```

### Illustrated (typical)

```text
articles/<slug>/article.md
articles/<slug>/assets/hero-<topic>.jpg
articles/<slug>/assets/social-reaction.jpg
articles/<slug>/assets/<other>.jpg
```

---

## Publish to GitHub

Git is the CMS. Pushing `articles/<slug>/` (including **binary assets**) is required for live images.

```bash
git status
git add articles/<slug>/
# include skill/app fixes only if intentional

git commit -m "$(cat <<'EOF'
Add satirical article: <slug>

Illustrated story with assets under articles/<slug>/assets/.
EOF
)"

git push -u origin HEAD
```

If commit fails on missing author, set for that command only (do not change global git config unless asked):

```bash
GIT_AUTHOR_NAME="shikkie" \
GIT_AUTHOR_EMAIL="shikkie@users.noreply.github.com" \
GIT_COMMITTER_NAME="shikkie" \
GIT_COMMITTER_EMAIL="shikkie@users.noreply.github.com" \
git commit -m "..."
```

Remote: `https://github.com/shikkie/satire-news-framework.git` · branch **`main`**.

**Static GitHub Pages build** (when publishing live site files):

```bash
npm run build          # writes docs/
git add docs/ articles/<slug>/
git commit -m "..."
git push
```

Pages serves **`main` /docs** — no GitHub Action required.

### Do not commit

`node_modules/`, `dist/`, `.pids/`, `logs/`, `.env`

---

## Writing rules

1. Clearly satirical in **voice** — deadpan news parody; not a real-world hoax for harm  
2. Fictional names for officials / activists; no private-person defamation  
3. Call the outlet **Agent News** (agentnews.site)  
4. ~300–700 words unless asked  
5. Structure: lede → quote → subheads → kicker  
6. **No on-page satire lectures** — do not end with “this is satire,” “not real news,” or Agent News disclaimers. The site already shows one clear banner.  

---

## Reference examples

| Slug | Pattern |
|------|---------|
| `california-trans-buck-harvest` | Full illustrated story + assets on disk |
| `jimothy-maga-raccoon-scandal` | Illustrated; body uses `assets/...` relative paths |
| `city-council-bans-gravity` | Text-only (no assets/) |

---

## Anti-patterns (root causes of broken images)

| Don’t | Why it breaks |
|-------|----------------|
| Reference images never written to disk | 404 |
| Leave files only in `~/.grok/sessions/.../images/` | Not served |
| Use `images/hero.jpg` or `thumbnail` fields from a fake manifest | Wrong schema |
| Create `articles/manifest.json` | Framework ignores it |
| Wrong slug in `/content/other-slug/assets/...` | 404 (SPA now rewrites slug, but file must still exist) |
| Commit `article.md` without `git add` of `assets/*` binaries | Live site 404 |
| Copy-paste captions from another story | Wrong alt text |
