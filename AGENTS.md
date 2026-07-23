# Satire News Framework — Agent Guide

## What this is

A self-contained framework for **realistic satirical / fake-news websites**.

**Publication:** **Agent News** · **https://agentnews.site**

- Each article lives in its own folder: Markdown body + frontmatter + optional assets
- A **React (Vite) SPA** renders the site (homepage, article pages, responsive layout, social-friendly meta)
- A **local Python preview server** exposes article APIs and assets during development
- Intended deploy target: **agentnews.site** (static build / GitHub Pages or similar)

This is satire tooling. Do not use it to impersonate real outlets for fraud, harassment, or disinformation campaigns.

## Product goals

1. Articles look and feel like a modern news site (masthead, sections, byline, hero, body typography)
2. Zero CMS — git + folders are the CMS
3. One-command local preview: `./dev.sh`
4. AI-assisted article generation via `skill/satire-news-article-generator/`
5. Social embeds (Open Graph / Twitter cards) work well for share previews

## Layout

```
.
├── AGENTS.md                 # this file
├── README.md
├── package.json              # Vite + React
├── vite.config.js
├── index.html
├── dev.sh                    # start/stop preview (Vite + Python)
├── preview/
│   └── server.py             # article API + asset server (port 8765)
├── articles/                 # one folder per story
│   └── <slug>/
│       ├── article.md
│       └── assets/
├── ads/                      # satirical sponsored businesses (ad rotation)
│   └── <slug>/
│       ├── business.md
│       └── assets/
├── src/                      # React SPA
├── public/                   # static files → copied into docs/ on build
├── docs/                     # production site (commit after npm run build)
└── skill/
    ├── satire-news-article-generator/
    └── satire-business-ad-generator/
    └── satire-news-article-generator/
        └── SKILL.md
```

## Article format

Each `articles/<slug>/article.md` uses YAML frontmatter:

```yaml
---
title: "Headline goes here"
dek: "Optional subhead / deck"
author: "Byline name"
date: "2026-07-20"          # ISO date preferred (display + sort)
published: "2026-07-20T18:30:00Z"  # optional ISO datetime for precise homepage order
section: "Local"             # Local | Politics | Business | Tech | Culture | Opinion | World
hero: "assets/hero.jpg"      # optional, relative to article folder
tags: ["local", "example"]
---

Markdown body with **bold**, lists, blockquotes, etc.
```

Slug = folder name (URL-safe, lowercase, hyphens).

**Homepage sort (newest first):** optional `published` (ISO datetime) → frontmatter `date` → git last-commit time on `articles/<slug>/` (else `article.md` mtime). Same calendar day no longer relies on slug order. Shared by `scripts/build-articles.mjs` and `preview/server.py`.

Site chrome shows **one** satire notice (top banner). Do not repeat disclaimers in article bodies or per-story UI chips.

**Share URLs** use path routes: `https://agentnews.site/article/<slug>` (not `#/article/...`). Build injects Open Graph HTML under `docs/article/<slug>/` for Discord/social cards.

## Dev workflow

```bash
./dev.sh              # start Python API (8787) + Vite (5173)
./dev.sh status
./dev.sh logs
./dev.sh stop
```

- Frontend binds **0.0.0.0:5173** (all interfaces)
- Phone / LAN URLs: `http://bandit:5173`, `http://bandit.local:5173`, or `http://<lan-ip>:5173`
- Vite `server.allowedHosts: true` so Host `bandit` is accepted (not blocked)
- API binds **0.0.0.0:8787** — Vite proxies `/api` and `/content` to `127.0.0.1:8787`
- Local-only: `API_HOST=127.0.0.1 UI_HOST=127.0.0.1 ./dev.sh`

Note: default API port is **8787** (8765 is often taken by other projects on this machine).

## Build / deploy (GitHub Pages — no Actions)

GitHub Pages branch deploy only supports **`/`** or **`/docs`** (not a custom `pages/` folder).

```bash
npm run build         # articles snapshot + Vite → docs/
npm run preview       # serve docs/ locally
git add docs/ && commit && push
```

| Path | Role |
|------|------|
| `docs/` | Production static site (**commit this** after build) |
| `public/` | Source static files copied into `docs/` (favicon, CNAME, `.nojekyll`) |

**Settings → Pages → Deploy from a branch → `main` / `/docs`.**  
`vite` snapshots articles into the static bundle so Pages needs no Python API.

### Pre-commit hook (auto-build `docs/`)

Committed hooks live in **`.githooks/`**. After clone (or `npm install`), hooks are installed via `core.hooksPath=.githooks`.

| Event | Behavior |
|-------|----------|
| `pre-commit` | If staged files touch `articles/`, `src/`, `public/`, etc. → `npm run build` → `git add docs/` |
| Skip | `SKIP_DOCS_BUILD=1 git commit ...` or `git commit --no-verify` |
| Manual install | `npm run hooks:install` or `./scripts/install-git-hooks.sh` |

## Conventions for agents

- Prefer editing article folders over inventing a CMS
- **New stories:** follow `skill/satire-news-article-generator/SKILL.md` exactly (stills via `image_gen`/`image_edit` only; **never** call video tools — for video give the user an Imagine prompt and wait for their `.mp4`; `hero:` still only; curl → 200; pre-commit rebuilds `docs/`)
- **Scripted article jobs:** `./scripts/create-article.sh "brief..."` (or `--file` / stdin) runs headless `grok` with `--cwd` set to this repo; `./scripts/create-article.sh --issues` drains open GitHub issues labeled `article-request` (oldest first; optional `--limit N`)
- **New ads / fake businesses:** follow `skill/satire-business-ad-generator/SKILL.md` (`ads/<slug>/business.md` + assets; rotation on home + articles)
- Keep the SPA dependency-light (React + markdown renderer only)
- Do not commit secrets; no API keys required for core preview
- When adding sample/demo content, keep it clearly satirical and non-defamatory
- Match existing component style; no new UI libraries unless asked
- Update this file when architecture changes

## Non-goals (for now)

- User accounts, comments, ads, analytics backends
- Real-time CMS or admin UI
- Multi-tenant multi-site theming engine (single site config is fine)
