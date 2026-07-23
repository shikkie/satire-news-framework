# Satire News Framework

Self-contained framework for **realistic satirical news sites**.

- Articles = folders of Markdown + assets (git is the CMS)
- **React + Vite** SPA (responsive, social-friendly layout)
- **Python preview server** for local article API / assets
- Deployable as static files to **GitHub Pages**

Publication masthead: **Agent News** · domain **[agentnews.site](https://agentnews.site)**

> This is satire tooling. Content is fictional. Do not use it to impersonate real outlets for harm.

## Quick start (preview)

Requirements: Node 20+, Python 3.10+, npm.

```bash
chmod +x dev.sh          # once
./dev.sh                 # starts API :8787 + Vite :5173
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
| `articles/<slug>/article.md` | Story (YAML frontmatter + body) |
| `articles/<slug>/assets/` | Optional images |
| `preview/server.py` | Local API + content server |
| `src/` | React SPA |
| `skill/satire-news-article-generator/` | Agent skill for drafting articles |
| `dev.sh` | One-command local preview |
| `AGENTS.md` | Conventions for AI/agents |
| `pages/` | **Production build output** (gitignored; deployed to GitHub Pages) |
| `.github/workflows/deploy-pages.yml` | Builds `pages/` and publishes to GitHub Pages |

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
disclaimer: true
---

Markdown body here.
```

## Scripts

```bash
npm install
npm run dev              # Vite only (needs API for live articles)
npm run articles:build   # snapshot articles → public/ (then copied into pages/ on build)
npm run build            # articles snapshot + Vite → pages/
npm run preview          # serve pages/ locally (after build)
```

## GitHub Pages (from `pages/`)

GitHub’s branch UI only offers `/` or `/docs`. This repo deploys the **`pages/`** build folder via **GitHub Actions** instead.

1. **Settings → Pages → Build and deployment → Source: GitHub Actions**
2. Push to `main` (or run the **Deploy GitHub Pages** workflow manually)
3. Workflow runs `npm run build` → uploads **`pages/`** → deploys

Custom domain: `public/CNAME` is set to **agentnews.site** (copied into `pages/` on build). Point DNS:

| Type | Name | Value |
|------|------|--------|
| A / ALIAS | `@` | GitHub Pages IPs (or your host docs) |
| CNAME | `www` | `<user>.github.io` |

Also enable **Enforce HTTPS** once DNS propagates.

Local production check:

```bash
npm run build
npm run preview    # http://127.0.0.1:4173
```

## Agent / AI workflow

See `AGENTS.md` and `skill/satire-news-article-generator/SKILL.md`.

Typical loop:

1. Draft `articles/<slug>/article.md` (skill helps)
2. `./dev.sh` and review in the browser
3. Commit + push article folder to `main`
4. Actions rebuilds `pages/` and updates agentnews.site