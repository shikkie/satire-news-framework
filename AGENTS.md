# Satire News Framework — Agent Guide

## What this is

A framework for **realistic satirical / fake-news websites**, evolving from git-folder CMS toward a **Dockerized application** (issue #14).

**Publication:** **Agent News** · **https://agentnews.site** (prod) · **http://agentnews.local** (lab)

- **Legacy path:** each article is a folder (`articles/<slug>/`) + static `docs/` GitHub Pages
- **App path (primary for production droplet):** Docker Compose → nginx (ModSecurity CRS) → Flask API + SPA → MongoDB + MinIO/Spaces
- **agentnewsd** remains a **sidecar** for AI create-article jobs (not folded into the main API yet)

This is satire tooling. Do not use it to impersonate real outlets for fraud, harassment, or disinformation campaigns.

## Product goals

1. Articles look and feel like a modern news site (masthead, sections, byline, hero, body typography)
2. Git + folders remain the authoring seed; **MongoDB is the runtime store** for the app stack
3. One-command local app stack: `docker compose up --build`
4. AI-assisted article generation via `skill/satire-news-article-generator/` + `agentnewsd`
5. Social embeds work via OG shells (Flask bot detection) + CDN prime after publish
6. Configurable domain: change `.env` domain + credentials to go local → live

## App stack (issue #14)

### Compose services

| Service | Role |
|---------|------|
| `mongo` | Articles, ads, users, sessions |
| `minio` | Local S3 (prod: DigitalOcean Spaces + Spaces CDN) |
| `minio-init` | Create public-read bucket |
| `api` | Flask/gunicorn — REST, auth, SPA static, OG shells |
| `nginx` | `owasp/modsecurity-crs:nginx-alpine` reverse proxy |

### Domains

| Env | Main site | Media |
|-----|-----------|-------|
| Lab | `agentnews.local` | `assets.agentnews.local` |
| Prod | `agentnews.site` | `assets.agentnews.site` |

Prod edge: **Gcore** for HTML/JS/CSS/API origin; **Spaces CDN** for media (no second CDN in front of Spaces).

### S3 key layout

```
article/<slug>/<filename>
ad/<slug>/<filename>
```

Public-read objects with long Cache-Control. Mongo `media[]` stores full public URLs + `name` for markdown hydration.

### Article document (core)

- `slug`, `title`, `dek`, `author`, `section`, `tags`, `hero` (media name)
- `markdown` (body string)
- `media`: `[{ type, name, url, key, filename }]`
- `agent_source` (default `"grok"`)
- `status`: `draft` | `published` | `scheduled`
- `published_at`, `created_at`, `updated_at`
- `versions[]`: prior snapshots for git-like diff (`version`, `markdown`, `title`, `edited_by`, `edited_at`, `reason`)

### Auth

- Username/password → `session_id`
- Header: **`X-Session-Id`** on every authenticated `/api` call
- Sessions in Mongo; **15-minute idle TTL** reset on use
- Roles: `admin` (users/settings/sessions), `editor` (articles only)

### API cache / CDN

- All `/api/*` responses: `Cache-Control: no-store`
- Publish/create/update of published articles → Gcore purge (stub/log if credentials unset) + HTTP prime of article URL + OG image (+ media URLs)

### Admin UI

- `/admin/login`, `/admin` list, `/admin/articles/:slug` editor (markdown + live preview + version diff)
- `/admin/sessions` (admin role)

### Onboard migration

```bash
docker compose exec api python -m scripts.onboard_content
# or --dry-run with SEED_ARTICLES_DIR / SEED_ADS_DIR
```

Walks `articles/` + `ads/`, uploads assets to S3, upserts Mongo docs with initial version entry.

### Quality gates

```bash
npm run quality   # eslint + vitest + ruff + pytest + bandit
```

| Tool | Scope |
|------|--------|
| eslint | `src/` |
| vitest | `src/**/*.test.js` |
| ruff | `api/app`, `api/scripts`, `api/tests` |
| pytest | `api/tests` (mongomock) |
| bandit | `api/app`, `api/scripts` |

## Layout

```
.
├── AGENTS.md
├── docker-compose.yml        # app stack
├── .env.example
├── docker/nginx/             # ModSecurity nginx templates
├── api/                      # Flask app (issue #14)
│   ├── app/
│   ├── scripts/onboard_content.py
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── package.json              # Vite + React + eslint/vitest
├── vite.config.js
├── dev.sh                    # legacy: Vite + folder preview + agentnewsd
├── preview/server.py         # legacy folder API :8787
├── agentnewsd/               # sidecar create-article HTTP API
├── articles/                 # seed / git authoring
├── ads/
├── src/                      # React SPA (+ admin)
├── public/
├── docs/                     # optional static export (GitHub Pages)
└── skill/
```

## Article format (filesystem seed)

Each `articles/<slug>/article.md` uses YAML frontmatter:

```yaml
---
title: "Headline goes here"
dek: "Optional subhead / deck"
author: "Byline name"
date: "2026-07-20"
published: "2026-07-20T18:30:00Z"
section: "Local"
hero: "assets/hero.jpg"      # onboard maps to media name "hero"
tags: ["local", "example"]
---

Markdown body. Prefer image refs that match media **names** (`hero`, `scene-one`)
so the SPA can hydrate full CDN URLs from `media[]`.
```

Slug = folder name (URL-safe, lowercase, hyphens).

Site chrome shows **one** satire notice (top banner). Do not repeat disclaimers in article bodies.

**Share URLs:** `https://agentnews.site/article/<slug>`. App stack serves OG shells for bots from Flask; static `docs/article/<slug>/` remains for Pages export.

## Dev workflow

### App stack (preferred for API/admin work)

```bash
cp .env.example .env   # set ADMIN_PASSWORD, domains
docker compose up -d --build
docker compose exec api python -m scripts.onboard_content
# site: http://localhost  (or agentnews.local if DNS points here)
# minio console: http://localhost:9001
```

Vite against local API:

```bash
# terminal: API on :8000 (compose or gunicorn)
PREVIEW_API=http://127.0.0.1:8000 npm run dev
```

### Legacy folder preview

```bash
PREVIEW_API=http://127.0.0.1:8787 ./dev.sh
```

- **agentnewsd** remains separate (`./dev.sh start agentnewsd`, port 8790)

## Build / deploy

### Production (DigitalOcean droplet)

1. Clone repo, copy `.env.example` → `.env`
2. Set `SITE_DOMAIN`, `ASSETS_DOMAIN`, Spaces keys, `MEDIA_PUBLIC_BASE_URL`, Gcore token/resource id, strong `SECRET_KEY` + `ADMIN_PASSWORD`
3. `docker compose up -d --build`
4. `docker compose exec api python -m scripts.onboard_content`
5. Point DNS + Gcore origin at the droplet; Spaces CDN host as `assets.*`

### GitHub Pages (legacy static)

```bash
npm run build         # → docs/
git add docs/ && commit && push
```

Pre-commit may rebuild `docs/` when content/src changes (`SKIP_DOCS_BUILD=1` to skip).

## Conventions for agents

- Prefer `articles/` + onboard for bulk seed; runtime edits go through admin API/UI
- **New stories (git path):** follow `skill/satire-news-article-generator/SKILL.md`
- **agentnewsd:** still the HTTP trigger for create-article jobs — do not break it while extending `api/`
- Do not commit secrets (`.env`); use `.env.example` only
- Match existing SPA style; admin UI is plain CSS in `index.css` (no new UI kits unless asked)
- Run `npm run quality` before claiming API/frontend work complete
- Update this file when architecture changes
- Append durable lessons under **Agent antipatterns** below when you hit a non-obvious failure mode

## Non-goals (current)

- Redis (sessions are Mongo)
- Folding agentnewsd into main API (sidecar for now)
- Multi-tenant multi-site engine
- Comments / real ad network / analytics backends

---

## Agent antipatterns (self-learning)

Record mistakes so future agents avoid them. Add dated bullets when something bites you.

### Architecture / product

- **Do not assume GitHub Pages is still the only deploy path.** Prod is compose on a droplet + Spaces + Gcore; `docs/` is a legacy/static export.
- **Do not put a second CDN in front of Spaces** unless product explicitly asks — media CDN is Spaces CDN only.
- **Do not fold agentnewsd into `api/` casually** — it is a long-running job sidecar with different auth (API key) and timeouts.
- **Do not serve authenticated `/api/*` with cacheable headers.** Always `Cache-Control: no-store`.

### Auth / sessions

- **Idle TTL tests must create the session inside the frozen clock.** Logging in before `freeze_time` makes `last_seen_at` real-now and immediately expires under a frozen timestamp.
- **Session id is a header (`X-Session-Id`), not a cookie** for v1 — do not half-implement cookie sessions without updating the SPA and nginx.
- **Editors must not reach `/api/users` or session listing** — enforce roles in decorators, not only in the UI.

### Media / markdown

- **Markdown should resolve via `media[].name`**, not hard-coded `/content/...` paths, once onboarded. Keep `/content/` only as legacy fallback for folder preview.
- **Hero field may be a media name or absolute URL** after serialization — UI should handle both (`heroMediaUrl` / `resolveMediaUrl`).
- **S3 object keys:** `article/<slug>/<filename>` — do not invent alternate layouts without a migration.

### Docker / nginx / security

- **MinIO healthchecks:** do not assume `mc` exists inside the MinIO server image; use HTTP health endpoints or a separate `mc` init container.
- **ModSecurity CRS will false-positive on large markdown JSON** — keep narrow exclusions (body size for `/api/`), never disable CRS globally for convenience.
- **Bootstrap admin with default password is a footgun** — log loudly; require `ADMIN_PASSWORD` change for prod writeups.

### CDN

- **Missing Gcore credentials must stub/log, not fail publish** in local/dev. Fail-closed only if product later requires it.
- **Prime both the article HTML URL and the OG image URL** after publish — Discord/etc. need the image warm, not only the page.

### Tooling

- **Ruff `S105`/`S106` on test passwords and config defaults** — ignore in tests/config, do not “fix” by removing necessary fixtures.
- **Flask route order:** register static paths like `/api/articles/admin` before `/api/articles/<slug>` or `admin` is captured as a slug.
- **Vite proxy default for app work is `:8000`** (Flask). Folder preview still needs `PREVIEW_API=http://127.0.0.1:8787`.

### Process

- **Issue numbers:** confirm with `gh issue list` — “issue 15” may not exist; this work is **#14**.
- **Ask remaining product forks up front** (deploy primary, ads scope, agentnewsd, CDN stub, admin scope) before multi-day rewrites.
- **Quality bar for app PRs:** eslint + vitest + ruff + pytest + bandit (`npm run quality`), not only a manual click-test.
