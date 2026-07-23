---
name: satire-business-ad-generator
description: >
  Create satirical sponsored businesses for Agent News ad rotation: name, contact,
  bio, logo/hero images via Grok Imagine, ads/<slug>/business.md layout, verify,
  commit/push. Use when adding ads, sponsors, fake businesses, or ad inventory.
---

# Satire Business Ad Generator

## When to use

Use when the user wants a **new satirical advertiser**, **sponsored business**, **ad rotation entry**, or fake local business for Agent News sidebars/home.

Repo root: `satire-news-framework/`  
Publication: **Agent News** · agentnews.site

Ads are clearly labeled **Sponsored** in the UI. Keep them absurd and deadpan — not real businesses, not real phone numbers that ring real people (use `555` and `.example` domains).

---

## End-to-end workflow

### 1. Pick a unique slug

```bash
ls ads/
mkdir -p ads/<slug>/assets
```

Slug: lowercase, hyphens only (e.g. `splat-and-sizzle-roadkill-bbq`).

### 2. Write `ads/<slug>/business.md`

```yaml
---
name: "Business Display Name"
tagline: "One-line pitch"
phone: "(555) 555-0000"
email: "hello@business.example"
website: "https://business.example"
address: "123 Fake St, City, ST"
hours: "Mon–Sat 9am–6pm"
category: "Dining"   # Dining | Services | Retail | Health | Other
cta: "Call to action button text"
logo: "assets/logo.jpg"
image: "assets/hero.jpg"
weight: 1            # rotation weight (higher = shown more)
active: true
---

Short bio (1–3 paragraphs). Deadpan satire. No “this is fake” disclaimer.
```

| Field | Required | Notes |
|-------|----------|--------|
| `name` | yes | Public business name |
| `tagline` | recommended | Ad headline under the name |
| `phone` | recommended | Prefer `555` exchanges |
| `email` | recommended | Use `@….example` |
| `website` | optional | `https://….example` |
| `address` | recommended | Fictional street |
| `hours` | optional | Human-readable |
| `category` | recommended | Shown on the ad kicker |
| `cta` | recommended | Button label |
| `logo` | recommended | Square-ish mark `assets/logo.jpg` |
| `image` | yes if visual | Wide hero `assets/hero.jpg` |
| `weight` | optional | Number ≥ 1 for rotation |
| `active` | optional | `false` removes from rotation |

### 3. Generate images (Grok Imagine)

Load the **imagine** skill when generating.

Typical set (minimum **hero**; logo strongly preferred):

| Asset | Aspect | Prompt vibe |
|-------|--------|-------------|
| `assets/hero.jpg` | 16:9 | Storefront / product scene, ad photo, **no gore** |
| `assets/logo.jpg` | 1:1 | Simple brand mark / monogram |

Optional extra stills for future use: `assets/interior.jpg`, etc. (rotation card currently uses `image` + `logo`).

```bash
cp /path/from/image_gen.jpg ads/<slug>/assets/hero.jpg
cp /path/from/logo.jpg ads/<slug>/assets/logo.jpg
chmod 644 ads/<slug>/assets/*
```

Session folders are not public — always copy into `ads/<slug>/assets/`.

### 4. Verify

```bash
ls -la ads/<slug>/assets/

# Dev API (./dev.sh)
curl -sS http://127.0.0.1:8787/api/ads | head
curl -sS -o /dev/null -w "%{http_code}\n" \
  http://127.0.0.1:8787/ads-content/<slug>/assets/hero.jpg
```

Expect **200**. Homepage and article pages show the rotating ad automatically.

### 5. Publish

```bash
npm run hooks:install   # once per clone
git add ads/<slug>/
git commit -m "$(cat <<'EOF'
Add satirical sponsor: <slug>

Business card + assets for ad rotation.
EOF
)"
git push -u origin HEAD
```

Pre-commit rebuilds `docs/` when `ads/` is staged (if hooks installed).  
If not: `npm run build && git add docs/`.

Author env fallback (this machine):

```bash
GIT_AUTHOR_NAME="shikkie" GIT_AUTHOR_EMAIL="shikkie@users.noreply.github.com" \
GIT_COMMITTER_NAME="shikkie" GIT_COMMITTER_EMAIL="shikkie@users.noreply.github.com" \
git commit -m "..."
```

---

## How ads appear on the site

| Layer | Behavior |
|-------|----------|
| Source | `ads/<slug>/business.md` + `assets/` |
| Dev API | `GET /api/ads`, media `GET /ads-content/<slug>/…` |
| Static build | `npm run ads:build` → `public/ads-data.json` + `public/ads-content/` |
| UI | `AdRotation` on homepage + article pages (weighted rotation ~10s) |
| Label | Always shows **Sponsored** |

Do **not** invent a parallel CMS or put ads inside `articles/`.

---

## Writing rules

1. Clearly satirical businesses — absurd products/services, deadpan ad voice.  
2. No real private individuals; no real phone numbers that harass people.  
3. Taste: dark humor ok; avoid graphic gore imagery (roadkill BBQ = signage & shack, not carcass piles).  
4. Short bio (≈40–120 words).  
5. Active inventory: keep `active: true` only for ads that should rotate.

---

## Checklist

```text
[ ] Unique slug under ads/
[ ] business.md with name, contact, bio, image/logo paths
[ ] Imagine hero (+ logo); copy into assets/
[ ] curl /api/ads and /ads-content/... → 200
[ ] git add ads/<slug>/ → commit → push (docs via hook)
```

## Reference inventory

| Slug | Business |
|------|----------|
| `splat-and-sizzle-roadkill-bbq` | Roadkill BBQ joint |
| `forever-paws-pet-crematory` | Pet memorial / crematory |

## Anti-patterns

| Don’t | Why |
|-------|-----|
| Paths without files on disk | Broken images |
| Real phone/email of real people | Harm / spam |
| `active: true` with empty name | Ugly empty cards |
| Editing only `docs/` | Overwritten on build |
