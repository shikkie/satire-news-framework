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
| `docs/` | **Production static site** for GitHub Pages (`main` + `/docs`) |

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

## Agent / AI workflow

See `AGENTS.md` and `skill/satire-news-article-generator/SKILL.md`.

Typical loop:

1. Draft `articles/<slug>/article.md` (skill helps)
2. `./dev.sh` and review in the browser
3. `npm run build` so `docs/` is current
4. Commit article folder **and** `docs/`, then push to `main`
