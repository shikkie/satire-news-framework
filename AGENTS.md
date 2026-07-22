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
│       ├── article.md        # YAML frontmatter + Markdown body
│       └── assets/           # images, optional
├── src/                      # React SPA
├── public/
└── skill/
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
date: "2026-07-20"          # ISO date preferred
section: "Local"             # Local | Politics | Business | Tech | Culture | Opinion | World
hero: "assets/hero.jpg"      # optional, relative to article folder
tags: ["local", "example"]
disclaimer: true             # show satire disclaimer (default true)
---

Markdown body with **bold**, lists, blockquotes, etc.
```

Slug = folder name (URL-safe, lowercase, hyphens).

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

## Build / deploy (GitHub Pages)

```bash
npm run build         # writes dist/ (SPA + snapshot of articles)
# Deploy dist/ to GitHub Pages (Actions or gh-pages branch)
```

`vite` prebuilds article JSON into the static bundle so Pages needs no backend.

## Conventions for agents

- Prefer editing article folders over inventing a CMS
- **New stories:** follow `skill/satire-news-article-generator/SKILL.md` exactly (slug, `article.md` only, real files under `assets/`, `hero: assets/…`, body `![](assets/…)`, curl `/content/<slug>/assets/…` → 200, git push binaries)
- Keep the SPA dependency-light (React + markdown renderer only)
- Do not commit secrets; no API keys required for core preview
- When adding sample/demo content, keep it clearly satirical and non-defamatory
- Match existing component style; no new UI libraries unless asked
- Update this file when architecture changes

## Non-goals (for now)

- User accounts, comments, ads, analytics backends
- Real-time CMS or admin UI
- Multi-tenant multi-site theming engine (single site config is fine)
