# Agent News API (Flask)

Application backend for issue #14: MongoDB articles/ads, S3 media (MinIO/Spaces),
session auth, CDN purge/prime hooks, SPA + OG shells.

## Local (without full compose)

```bash
cd api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export MONGO_URI=mongodb://127.0.0.1:27017
export ADMIN_PASSWORD=dev-admin
# optional STATIC_DIR pointing at a Vite build
flask --app wsgi:app run -p 8000
# or: gunicorn -b 0.0.0.0:8000 wsgi:app
```

## Tests / quality

```bash
cd api
source .venv/bin/activate
ruff check app scripts tests
ruff format --check app scripts tests
pytest -q
bandit -c bandit.yaml -r app scripts
```

From repo root: `npm run quality` (eslint + vitest + ruff + pytest + bandit).

## Onboard filesystem content

```bash
# inside compose
docker compose exec api python -m scripts.onboard_content

# dry-run against repo folders
SEED_ARTICLES_DIR=../articles SEED_ADS_DIR=../ads \
  python -m scripts.onboard_content --dry-run
```

## Auth

- `POST /api/auth/login` → `{ session_id, username, role }`
- Send `X-Session-Id: <session_id>` on authenticated routes
- 15-minute **idle** TTL, refreshed on every authenticated request
- Roles: `admin` | `editor`

## Public API (SPA-compatible)

| Method | Path | Notes |
|--------|------|--------|
| GET | `/api/health` | liveness |
| GET | `/api/articles` | published only |
| GET | `/api/articles/<slug>` | published body + media |
| GET | `/api/ads` | active ads |

Authenticated article admin routes live under `/api/articles/admin`, `POST/PUT /api/articles`, publish, versions.

Portable article copy (admin session):

| Method | Path | Notes |
|--------|------|--------|
| GET | `/api/articles/<slug>/export` | JSON bundle: fields + base64 assets. `?download=1` attaches a file |
| POST | `/api/articles/import` | Body is the export JSON, or `{bundle, overwrite, as_draft}`. Default `as_draft=true` |

The bundle `format` is `agentnews.article.v1`. Import does not tweet.

`status=scheduled` plus `scheduled_at` (ISO UTC) queues a go-live. The API poller (or `POST /api/articles/admin/publish-due`) publishes due stories and, if `X_POST_ENABLED` and `post_to_x`, posts to X. `GET /api/settings` returns those feature flags.
