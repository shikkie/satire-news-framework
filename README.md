# Satire News Framework

Framework for **realistic satirical news sites** — git-folder seed content plus a **Docker application stack** (MongoDB, MinIO/Spaces, Flask, nginx + ModSecurity).

- Articles = folders of Markdown + assets (seed / git CMS) **or** MongoDB runtime store
- **React + Vite** SPA (public site + `/admin` editor)
- **Docker Compose** production path (DigitalOcean droplet + Spaces + Gcore)
- Legacy: Python folder preview + static **GitHub Pages** (`docs/`)

Publication masthead: **Agent News** · domain **[agentnews.site](https://agentnews.site)** · lab **agentnews.local**

> This is satire tooling. Content is fictional. Do not use it to impersonate real outlets for harm.

## Quick start (app stack — preferred)

Requirements: Docker Compose, Node 20+ (for local Vite), optional Python 3.12 for API tests.

```bash
cp .env.example .env          # set ADMIN_PASSWORD, domains, secrets
docker compose up -d --build
docker compose exec api python -m scripts.onboard_content
# http://localhost  (or agentnews.local if your lab DNS points here)
```

Quality: `npm run quality` (eslint, vitest, ruff, pytest, bandit). See `api/README.md` and `AGENTS.md`.

## Quick start (legacy folder preview)

Requirements: Node 20+, Python 3.10+, npm.

```bash
chmod +x dev.sh          # once
PREVIEW_API=http://127.0.0.1:8787 ./dev.sh   # folder API :8787 + Vite :5173
```

Open any of:

| Where | URL |
|-------|-----|
| This machine | http://127.0.0.1:5173 |
| Hostname **bandit** (LAN DNS) | http://bandit:5173 |
| LAN IP | http://192.168.1.17:5173 |

Vite accepts Host headers for `bandit`, `bandit.local`, LAN IPs, etc. (`server.allowedHosts: true`).

Servers bind **0.0.0.0** by default (all interfaces). Restrict to localhost with:

```bash
API_HOST=127.0.0.1 UI_HOST=127.0.0.1 ./dev.sh
```

(Default API port is **8787** so it doesn’t collide with other local services; set `API_PORT` / `PREVIEW_API` if you need different ports.)

```bash
./dev.sh status
./dev.sh logs
./dev.sh stop
```

## Project layout

| Path | Purpose |
|------|---------|
| `docker-compose.yml` | mongo + minio + api + nginx/ModSecurity |
| `api/` | Flask app (auth, articles, ads, CDN hooks, SPA/OG) |
| `articles/<slug>/article.md` | Story seed (YAML frontmatter + body) |
| `articles/<slug>/assets/` | Optional images (onboard → S3) |
| `ads/<slug>/` | Satirical sponsored businesses |
| `src/` | React SPA + admin UI |
| `preview/server.py` | Legacy folder API + content server |
| `agentnewsd/` | Sidecar create-article HTTP API |
| `dev.sh` | Legacy one-command local preview |
| `AGENTS.md` | Conventions + agent antipatterns |
| `docs/` | Optional static export for GitHub Pages |

## Article format

```markdown
---
title: "Headline"
dek: "Optional deck"
author: "Byline"
date: "2026-07-20"
section: "Local"
hero: "assets/hero.jpg"
tags: ["local"]
---

Markdown body here.
```

## Scripts

```bash
npm install
npm run dev              # Vite only (needs API for live articles)
npm run articles:build   # snapshot articles → public/
npm run build            # articles snapshot + Vite → docs/
npm run preview          # serve docs/ locally (after build)
```

## GitHub Pages (no Actions)

You’re right that Pages just serves a folder from a branch — but GitHub only allows:

- **`/`** (repo root), or  
- **`/docs`**

There is **no** native “serve `/pages`” option. So this project builds into **`docs/`**, which Pages can host as-is.

**Settings → Pages:**

| Setting | Value |
|---------|--------|
| Source | **Deploy from a branch** |
| Branch | **`main`** |
| Folder | **`/docs`** |

Publish (usually automatic on commit — see below):

```bash
# After npm install, pre-commit rebuilds docs/ when you stage site sources
git add articles/src/...
git commit -m "Add story"
git push
```

### Git hooks

```bash
npm run hooks:install   # or: ./scripts/install-git-hooks.sh
# also runs on npm install via "prepare"
```

| Hook | What it does |
|------|----------------|
| **pre-commit** | If the commit stages `articles/`, `src/`, `public/`, etc. → runs `npm run build` and stages `docs/` |

Skip once: `SKIP_DOCS_BUILD=1 git commit ...` or `git commit --no-verify`.
Custom domain: `public/CNAME` is **agentnews.site** (copied into `docs/` on build).

Local check: `npm run build && npm run preview` → http://127.0.0.1:4173

### Social / Discord previews (Open Graph)

| Page | Share URL | Card content |
|------|-----------|--------------|
| Home | `https://agentnews.site/` | Title + site blurb + `og-default.jpg` |
| Article | `https://agentnews.site/article/<slug>` | Headline + dek + hero image |

`#/article/...` is stripped by crawlers and will **not** show a card. Build injects meta via `inject-og-html.mjs`. After deploy, re-paste in Discord (embeds cache) or check [opengraph.xyz](https://www.opengraph.xyz/).
## Agent / AI workflow

See `AGENTS.md` and `skill/satire-news-article-generator/SKILL.md`.

### Create an article from the shell

```bash
./scripts/create-article.sh "Six-week-old orange kitten calls 911 for late breakfast..."

# long briefs
./scripts/create-article.sh --file my-brief.txt
./scripts/create-article.sh <<'EOF'
full multi-line pitch here
EOF

./scripts/create-article.sh --dry-run "..."   # print prompt only

# drain open GitHub issues labeled article-request (oldest first)
./scripts/create-article.sh --issues
./scripts/create-article.sh --issues --limit 1
```

Runs **grok** headless in this repo (`--cwd`), auto-approves tools, and tells the agent to follow the article skill. Requires `grok` on `PATH` (or set `GROK_BIN`). `--issues` also needs authenticated `gh` + `jq`.

Typical loop:

1. Draft `articles/<slug>/article.md` (skill helps)
2. `./dev.sh` and review in the browser
3. `npm run build` so `docs/` is current
4. Commit article folder **and** `docs/`, then push to `main`
