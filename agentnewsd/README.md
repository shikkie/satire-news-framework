# agentnewsd — Agent News article creation API

HTTP service that accepts an article brief, runs `scripts/create-article.sh` headlessly, streams progress to the client, and returns the live article URL when done.

**Audience:** humans testing with Postman/curl, and coding agents wiring clients or changing this service.

| | |
|---|---|
| Default listen | `0.0.0.0:8790` (all interfaces; API key required) |
| Implementation | `agentnewsd/app.py` (Flask) |
| Script invoked | `scripts/create-article.sh --file <tmp>` |
| Auth | Single shared API key (`AGENTNEWSD_API_KEY` in `.env`) |
| Success URL shape | `https://agentnews.site/article/<slug>` |

Related:

- Article pipeline skill: `skill/satire-news-article-generator/SKILL.md`
- Headless CLI wrapper: `scripts/create-article.sh`
- Systemd installer: `scripts/install-agentnewsd.sh`
- Repo guide: `AGENTS.md`

---

## What it does

1. Client `POST`s JSON with `api_key` + `article_def` (same kind of free-text brief you’d pass to `create-article.sh` via stdin or `--file`).
2. Service checks the API key (constant-time compare).
3. **Real run:** writes `article_def` to a private temp file, then runs:
   ```text
   /path/to/scripts/create-article.sh --file /tmp/agentnewsd-brief.XXXXXX.txt
   ```
   with **`shell=False`** and a fixed argv list. User text never appears on the command line (only in the temp file).
4. Streams child stdout/stderr as **NDJSON** lines (`application/x-ndjson`).
5. On finish, parses any `https://agentnews.site/article/<slug>` URLs from the log and returns them in a final `result` object.

**Concurrency:** only one create job at a time. A second request gets **HTTP 409** while busy.

**Timeout:** wall clock for the subprocess, default **3600s** (`AGENTNEWSD_TIMEOUT_SECONDS`).

---

## Endpoints

### `GET /health`

No auth. Liveness / busy probe.

**Example response**

```json
{
  "status": "ok",
  "service": "agentnewsd",
  "busy": false,
  "timeout_seconds": 3600,
  "dry_run_supported": true
}
```

| Field | Meaning |
|-------|---------|
| `busy` | `true` while a create (or dry-run) job holds the lock |
| `dry_run_supported` | Always `true` on current builds — use for client feature detection |

---

### `POST /v1/create-article`

Creates an article (or dry-runs the API path).

**Headers**

| Header | Value |
|--------|--------|
| `Content-Type` | `application/json` (required) |

**Body (JSON)**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `api_key` | string | yes | Must match `AGENTNEWSD_API_KEY` |
| `article_def` | string | yes | Non-empty brief (same content as create-article issue body / CLI brief) |
| `dry_run` | bool or string | no | If truthy (`true`, `1`, `"true"`, `"yes"`, `"on"`), **do not** run Grok/git — simulate NDJSON + fake URL |

**Example body (dry-run — use this first)**

```json
{
  "api_key": "YOUR_KEY_FROM_agentnewsd/.env",
  "article_def": "Local council votes to ban eye contact during coffee orders.",
  "dry_run": true
}
```

**Example body (real create — long-running, costs Grok + commits)**

```json
{
  "api_key": "YOUR_KEY_FROM_agentnewsd/.env",
  "article_def": "Six-week-old orange kitten called 911 because breakfast was late. Officers arrived with wet food. Interview the kitten and the sergeant."
}
```

**Response**

- **Success path:** HTTP **200**, `Content-Type: application/x-ndjson`
- Body is a **stream of JSON objects**, one per line (not a single JSON array).
- Keep the connection open until a final `{"type":"result",...}` line.

**Non-stream error responses** (JSON object, usual REST style):

| Status | When |
|--------|------|
| `400` | Missing/empty `article_def`, invalid JSON object |
| `401` | Missing/wrong `api_key` |
| `409` | Another job is already running |
| `413` | `article_def` larger than `AGENTNEWSD_MAX_ARTICLE_DEF_BYTES` (default 256 KiB) |
| `415` | Not `application/json` |
| `500` | Misconfigured key, missing/non-executable create script (real runs only) |

---

## NDJSON event protocol

Each line is one JSON object. Process lines as they arrive.

### `type: "status"`

Lifecycle phases.

```json
{"type":"status","phase":"starting","message":"...","timeout_seconds":3600}
{"type":"status","phase":"running","message":"create-article.sh started","pid":12345}
{"type":"status","phase":"timeout","message":"job exceeded 3600s; killing process"}
```

Dry-run also sets `"dry_run": true` on status events.

| `phase` | Meaning |
|---------|---------|
| `starting` | Validated / about to start (or dry-run begin) |
| `running` | Subprocess up (or simulation in progress) |
| `timeout` | Wall clock exceeded; process killed |

### `type: "log"`

One line of create-article / Grok output (combined stdout+stderr).

```json
{"type":"log","stream":"combined","line":"create-article.sh: repo=/path/to/satire-news-framework"}
```

### `type: "result"` (terminal)

Last event for the request. Stop reading after this.

**Real success**

```json
{
  "type": "result",
  "ok": true,
  "exit_code": 0,
  "article_url": "https://agentnews.site/article/some-slug",
  "urls": ["https://agentnews.site/article/some-slug"],
  "message": "article created"
}
```

**Dry-run success**

```json
{
  "type": "result",
  "ok": true,
  "dry_run": true,
  "exit_code": 0,
  "slug": "a1b2-c3d4-e5f6-7890",
  "article_url": "https://agentnews.site/article/a1b2-c3d4-e5f6-7890",
  "urls": ["https://agentnews.site/article/a1b2-c3d4-e5f6-7890"],
  "message": "dry-run complete (nothing committed or published)"
}
```

| Field | Notes |
|-------|--------|
| `ok` | `true` only if process exit 0 **and** at least one article URL was found (dry-run always fabricates a URL) |
| `article_url` | Prefer this for clients; last discovered deep link |
| `urls` | All unique matches in order of appearance |
| `slug` | Present on dry-run; four hyphenated hex segments |
| `exit_code` | Child process exit code (`0` on dry-run) |
| `error` | Present on failure paths (`timeout`, `internal_error`, …) |
| `dry_run` | `true` only for simulated jobs |

**Failure examples**

```json
{"type":"result","ok":false,"error":"timeout","exit_code":-9,"article_url":null,"urls":[]}
{"type":"result","ok":false,"exit_code":1,"article_url":null,"urls":[],"message":"create-article exited non-zero"}
{"type":"result","ok":false,"error":"internal_error","message":"..."}
```

---

## Security model (agents: do not “improve” this away)

1. **API key** in JSON body compared with `secrets.compare_digest` to `AGENTNEWSD_API_KEY`.
2. **No shell:** `subprocess.Popen([...], shell=False)`. Argv is only the script path, `--file`, and a server-created temp path.
3. **User payload** goes only into the temp file contents, then is deleted in `finally`.
4. **Default bind** `0.0.0.0` (all interfaces) so remote clients can reach it; protect with a strong `AGENTNEWSD_API_KEY` and/or firewall. Local-only: `AGENTNEWSD_HOST=127.0.0.1`.
5. **One job at a time** avoids concurrent `git`/commit races from this API.
6. `.env` is gitignored; never commit real keys.

There is currently **one** shared key (no multi-tenant keys).

---

## Configuration

Copy and edit:

```bash
cp agentnewsd/.env.example agentnewsd/.env
# set AGENTNEWSD_API_KEY to a long random secret
```

| Variable | Default | Purpose |
|----------|---------|---------|
| `AGENTNEWSD_API_KEY` | _(required)_ | Auth for create |
| `AGENTNEWSD_HOST` | `0.0.0.0` | Bind address (`0.0.0.0` = all interfaces) |
| `AGENTNEWSD_PORT` | `8790` | Bind port |
| `AGENTNEWSD_TIMEOUT_SECONDS` | `3600` | Max real-job wall time |
| `AGENTNEWSD_MAX_ARTICLE_DEF_BYTES` | `262144` | Max brief size |
| `AGENTNEWSD_REPO_ROOT` | parent of `agentnewsd/` | cwd for create-article |
| `AGENTNEWSD_CREATE_SCRIPT` | `$REPO/scripts/create-article.sh` | Script path |

`.env` is loaded only for keys **not already** in the process environment (so systemd `Environment=` / `EnvironmentFile=` can override).

Grok-related env (`GROK_BIN`, `GROK_MODEL`, etc.) is inherited by the child and documented in `scripts/create-article.sh`.

---

## Local run

### Via `dev.sh` (recommended for day-to-day)

```bash
./dev.sh                      # preview API + Vite + agentnewsd
./dev.sh start agentnewsd     # agentnewsd only
./dev.sh stop agentnewsd
./dev.sh status
./dev.sh logs agentnewsd      # tail logs/agentnewsd.log
```

`dev.sh` will create `agentnewsd/.venv`, install deps, and ensure `.env` exists (generates a key if still a placeholder). Bind defaults:

| Env | Default |
|-----|---------|
| `AGENTNEWSD_HOST` | `0.0.0.0` |
| `AGENTNEWSD_PORT` | `8790` |

Values exported by `dev.sh` override the same keys in `.env` for that process. Local-only: `AGENTNEWSD_HOST=127.0.0.1 ./dev.sh start agentnewsd`.

### Manual (without dev.sh / systemd)

```bash
cd /path/to/satire-news-framework
python3 -m venv agentnewsd/.venv
agentnewsd/.venv/bin/pip install -r agentnewsd/requirements.txt
# ensure agentnewsd/.env has AGENTNEWSD_API_KEY
agentnewsd/.venv/bin/python agentnewsd/app.py
```

Health check:

```bash
curl -sS http://127.0.0.1:8790/health
```

---

## Systemd install

Does **not** hardcode a username or home path — you pass them:

```bash
sudo ./scripts/install-agentnewsd.sh --user SERVICE_USER
# optional: --repo /path/to/repo --bind 127.0.0.1 --port 8790 --no-start
# remove:  sudo ./scripts/install-agentnewsd.sh --user SERVICE_USER --uninstall
```

Unit name: **`agentnewsd`**

```bash
systemctl status agentnewsd
journalctl -u agentnewsd -f
```

The service user must be able to run a full real create end-to-end (repo write, `grok` on `PATH`, git push credentials).

---

## Testing with Postman

### Streaming reality check (read this first)

`POST /v1/create-article` returns **chunked NDJSON** (`Content-Type: application/x-ndjson`): one JSON object per line, written as the job progresses.

| Client | Live line-by-line UI? | Notes |
|--------|----------------------|--------|
| **curl `-N`** | Yes | Best for watching progress (see [curl reference](#curl-reference)) |
| **Postman (HTTP request)** | **No (usually)** | Postman **buffers the full HTTP body** and only paints the Response panel when the connection closes. You still get every NDJSON line — just all at once at the end |
| **Postman WebSocket / SSE tabs** | N/A | agentnewsd does **not** use WebSocket or `text/event-stream`; those Postman modes do not apply |

So: **Postman is fine for dry-run, auth checks, and inspecting the final payload.** It is **not** a live log tail for multi-minute real creates. For live streaming, use curl (or any client that reads the response body incrementally).

There is no special “enable streaming” toggle in Postman that makes classic REST responses flush line-by-line like a terminal. Configure timeouts and view mode as below so long jobs don’t fail and the NDJSON stays readable.

### 1. Start the server

```bash
./dev.sh start agentnewsd
# or full stack: ./dev.sh
# or systemd:    systemctl start agentnewsd
# or manual:     agentnewsd/.venv/bin/python agentnewsd/app.py
```

Confirm:

- **GET** `http://127.0.0.1:8790/health` (or `http://<host>:8790/health` from another machine) → 200, `"busy": false`.

### 2. Postman settings for long / streamed responses

Do this once before a real create:

1. **Request timeout**
   - Desktop: **Settings** (gear) → **General** → **Request timeout in ms**
   - Set to **`0`** (no limit) or at least `AGENTNEWSD_TIMEOUT_SECONDS * 1000` (default job timeout is **3600s** → `3600000`)
   - If timeout is left at the default (~30s), real creates will fail mid-job even though the server is still running
2. **SSL** — irrelevant for plain `http://` local/LAN; leave defaults
3. **Proxy** — if Postman uses a system proxy that buffers, disable proxy for this host or use **Settings → Proxy** so local/LAN traffic is direct
4. **Do not** put the key under **Authorization → Bearer Token** unless you change the server; the key is a JSON field `api_key`

### 3. Create a collection request — health

| Setting | Value |
|---------|--------|
| Method | `GET` |
| URL | `http://127.0.0.1:8790/health` (or LAN IP / hostname) |
| Auth | none |

Send → body should show JSON with `"status":"ok"`.

### 4. Create request — dry-run (recommended first)

| Setting | Value |
|---------|--------|
| Method | `POST` |
| URL | `http://127.0.0.1:8790/v1/create-article` |
| Headers | `Content-Type` = `application/json` |
| Body | **raw** → **JSON** |

Body:

```json
{
  "api_key": "paste-from-agentnewsd/.env",
  "article_def": "Postman dry-run: raccoon mayor bans Tuesdays.",
  "dry_run": true
}
```

**Send** and wait ~1s. Response body should be **multiple lines** of JSON, ending with `"type":"result"` and a fake:

`https://agentnews.site/article/xxxx-xxxx-xxxx-xxxx`

That confirms key, JSON shape, and the full NDJSON transcript without using Grok or git.

### 5. How to read the NDJSON body in Postman

After the request finishes:

1. Open the **Body** tab of the response (not Headers-only).
2. Prefer **Raw** (or **Pretty** only if it still shows line breaks). Avoid treating the whole body as a single JSON object — it is **not** valid as one document; it is **N lines**, each a separate JSON object.
3. Scroll to the **last non-empty line** — that should be `"type":"result"` with `article_url` / `ok`.
4. Optional: copy the body into an editor and split on newlines, or use a small script:

```bash
# if you saved the response body to a file from Postman
grep '"type":"result"' response.ndjson
```

**Postman Console** (`View → Show Postman Console`) shows request metadata and may show response size/status; it still will **not** reliably print each NDJSON line as it arrives for a long-running HTTP stream.

### 6. Optional: collection / environment variables

1. Environment (or collection) variables, e.g.:
   - `agentnewsd_base` = `http://127.0.0.1:8790`
   - `agentnewsd_api_key` = value from `agentnewsd/.env`
   - `article_brief` = your test text
2. URL: `{{agentnewsd_base}}/v1/create-article`
3. Body:

```json
{
  "api_key": "{{agentnewsd_api_key}}",
  "article_def": "{{article_brief}}",
  "dry_run": true
}
```

### 7. Real create from Postman

Same as dry-run but **omit** `dry_run` or set `"dry_run": false`.

| Step | What to expect |
|------|----------------|
| Click **Send** | Progress spinner stays active for a long time (minutes) |
| Response panel | Empty or “loading” until the job finishes (buffered) |
| When done | Full NDJSON transcript appears at once; last line is `result` |
| Timeout error | Raise request timeout (step 2); server may still have finished — check `./dev.sh logs agentnewsd` / `journalctl -u agentnewsd` |

Warnings:

- Invokes full agent pipeline: files under `articles/`, images, commit, push (per create-article skill).
- Homepage CDN can lag; use `article_url` from the final `result` line, not only the homepage.
- A second parallel **Send** while the first job is open should return **409** `{"error":"busy",...}` (normal JSON, not a stream).

### 8. Live streaming instead of Postman

When you need to **watch** logs as they are produced:

```bash
# Load key from .env (example)
set -a && source agentnewsd/.env && set +a

curl -N -sS -X POST "${AGENTNEWSD_BASE:-http://127.0.0.1:8790}/v1/create-article" \
  -H 'Content-Type: application/json' \
  -d "{\"api_key\":\"${AGENTNEWSD_API_KEY}\",\"article_def\":\"Your brief here\",\"dry_run\":true}"
```

`-N` / `--no-buffer` is what makes curl print each NDJSON line immediately. Point the URL at the LAN host when calling from another machine (`http://bandit:8790/...`, etc.).

### 9. Quick negative tests in Postman

| Case | Expect |
|------|--------|
| Wrong `api_key` | `401` `{"error":"unauthorized"}` |
| Empty `article_def` | `400` |
| `Content-Type: text/plain` | `415` |
| Two concurrent real/dry jobs | second → `409` |

---

## curl reference

```bash
# Health
curl -sS http://127.0.0.1:8790/health | jq .

# Dry-run (-N = no buffer so lines print live)
curl -N -sS -X POST 'http://127.0.0.1:8790/v1/create-article' \
  -H 'Content-Type: application/json' \
  -d "{\"api_key\":\"$AGENTNEWSD_API_KEY\",\"article_def\":\"test brief\",\"dry_run\":true}"

# Real create
curl -N -sS -X POST 'http://127.0.0.1:8790/v1/create-article' \
  -H 'Content-Type: application/json' \
  -d "{\"api_key\":\"$AGENTNEWSD_API_KEY\",\"article_def\":\"Your full satire brief here...\"}"
```

---

## `article_def` content (what to put in the body)

Treat it like the GitHub `article-request` issue body or the CLI brief string:

- Story premise, tone, any required characters/places
- Optional section hints (Local, Politics, …)
- Anything the skill needs that isn’t already in `SKILL.md`

You do **not** need to restate the full skill instructions; `create-article.sh` wraps the brief with repo/skill directives before calling Grok.

---

## Implementation map (for coding agents)

| Piece | Location |
|-------|----------|
| Flask app / routes | `agentnewsd/app.py` |
| Dry-run simulator | `_generate_dry_run()` |
| URL scrape from logs | `_extract_urls()` + `ARTICLE_URL_RE` |
| Job lock | `_job_lock` / `_busy` → HTTP 409 |
| Deps | `agentnewsd/requirements.txt` (`flask`) |
| Secrets template | `agentnewsd/.env.example` |
| Unit install | `scripts/install-agentnewsd.sh` → unit `agentnewsd` |

When changing the API:

- Keep NDJSON as newline-delimited objects with a terminal `type: "result"`.
- Keep argv fixed; never interpolate `article_def` into shell or argv beyond the temp file path the server creates.
- Prefer extending the JSON body with optional fields rather than new auth schemes unless documented.
- Update this README when request/response shapes change.

---

## What this service does *not* do

- Multi-key / OAuth / per-user auth
- Job queue or async job IDs (streaming is on the same POST connection)
- WebSockets or SSE (`text/event-stream`) — use NDJSON on the POST response
- Serving the public site (that’s static `docs/` / GitHub Pages)
- Preview API (that’s `preview/server.py` on port 8787 via `./dev.sh`)
