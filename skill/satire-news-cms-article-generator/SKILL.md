---
name: satire-news-cms-article-generator
description: >
  Fill an Agent News CMS draft (Mongo + MinIO) by writing articles/<slug>/ on
  disk for the importer. Stills via image_gen/image_edit only. No git, no
  GitHub Pages, no agentnewsd, no issue queue.
---

# CMS article generator (app stack)

Use this skill when a **CMS generate job** asks you to turn a stored
`creation_prompt` into a full draft. The job may pin a slug, or ask you
to invent one.

Runtime is the Docker app (Mongo + MinIO + Flask + admin), not GitHub Pages.

## Hard constraints

- **Slug:** if the job says REQUIRED slug, use that folder name exactly. If it
  asks you to invent one, pick a unique kebab-case slug from the headline
  (`a-z`, `0-9`, hyphens; not starting with `draft-`) and do not collide with
  listed existing slugs.
- Write `articles/<slug>/article.md` and real files under `articles/<slug>/assets/`.
- Stills: `image_gen` / `image_edit` only. **Never** call video tools.
- Copy every still out of `~/.grok/sessions/...` into `assets/` with kebab-case names.
- `hero:` is a still (`assets/hero-….jpg`). Body embeds `![caption](assets/…)`.
- **Do not** git add/commit/push. **Do not** rebuild `docs/`. **Do not** touch GitHub issues.
- **Do not** publish. Leave files on disk; the CMS importer loads Mongo + MinIO and keeps the row a **draft**.
- Outlet: **Agent News**. No “this is satire” kickers in the body.

## Workflow

1. `mkdir -p articles/<slug>/assets`
2. Write `article.md` (frontmatter + ~300–700 word deadpan satire).
3. Generate 3–5 stills (hero, scene, presser/officials, social reaction as they fit).
4. Copy binaries into `assets/`, chmod 644.
5. `ls articles/<slug>/assets/` and confirm every markdown path exists on disk.
6. Stop. Final line of your reply:

```text
CMS_GENERATE_OK slug=<slug> files=articles/<slug>/article.md
```

## Frontmatter

```yaml
---
title: "Punchy satirical headline"
dek: "One-line deck"
author: "Fictional byline"
date: "YYYY-MM-DD"
section: "Local"
hero: "assets/hero-<topic>.jpg"
tags: ["tag1", "tag2"]
---
```

`section` is one of: Local, Politics, Business, Tech, Culture, Opinion, World.

## Images

Load the **imagine** skill for stills. Photojournalism / wire-photo style.

| Role | Filename |
|------|----------|
| Hero / OG | `hero-<topic>.jpg` |
| Scene | `scene-<place>.jpg` |
| Officials | `presser.jpg` or similar |
| Reaction | `social-reaction.jpg` |

## Writing

Deadpan news parody. Fictional private names. Call the outlet Agent News.
Lede → quote → subheads → kicker. No body disclaimers.
