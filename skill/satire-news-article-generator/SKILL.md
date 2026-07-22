---
name: satire-news-article-generator
description: Draft self-contained satirical news articles as Markdown folders for the satire-news-framework (frontmatter, body, optional assets notes).
---

# Satire News Article Generator

## When to use

Use this skill when the user wants a new satirical article, a batch of headlines, or to reshape copy into the framework’s article-folder format.

## Output location

Create (or update):

```
articles/<slug>/article.md
articles/<slug>/assets/     # optional; leave empty or note required images
```

`slug`: lowercase, hyphenated, URL-safe, stable.

## Frontmatter template

```yaml
---
title: "Punchy satirical headline"
dek: "One-line deck that sharpens the joke"
author: "Fictional byline"
date: "YYYY-MM-DD"
section: "Local"   # Local | Politics | Business | Tech | Culture | Opinion | World
hero: ""           # e.g. assets/hero.jpg if provided
tags: ["tag1", "tag2"]
disclaimer: true
---
```

## Writing rules

1. **Clearly satirical** — absurd premise, deadpan delivery, not a real news hoax.
2. **No real private individuals** as defamation targets; public figures only with care; prefer fictional names.
3. **News voice** — inverted pyramid parody, short grafs, one good pull-quote.
4. **Length** — ~300–700 words unless asked otherwise.
5. **Structure** — lede → quote → “what it means” bullets or grafs → kicker.
6. **Disclaimer** — leave `disclaimer: true` unless the user explicitly wants it off.
7. **Assets** — if a hero image is needed, set `hero` and describe the image for the user (do not invent binary files). Prefer generating via image tools only when requested.

## After writing

- Confirm the file path.
- Remind the user to refresh the preview (`./dev.sh` → http://127.0.0.1:5173; API on :8787).
- Offer a second section variant or social blurb if useful.

## Example slug ideas

- `city-council-bans-gravity`
- `startup-pivots-to-vibes`
- `weather-apologizes`
