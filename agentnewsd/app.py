#!/usr/bin/env python3
"""agentnewsd — HTTP API that triggers scripts/create-article.sh.

POST /v1/create-article
  JSON body: {"api_key": "...", "article_def": "...", "dry_run": false}
  Response: application/x-ndjson stream (one JSON object per line)

  dry_run=true: same auth/validation and NDJSON shape, but does not call
  create-article.sh / Grok / git. Emits simulated progress and a fake
  article_url (https://agentnews.site/article/<slug>).

GET /health
  No auth. {"status":"ok","busy":bool}
"""

from __future__ import annotations

import json
import os
import re
import secrets
import selectors
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from flask import Flask, Response, jsonify, request, stream_with_context

# ---------------------------------------------------------------------------
# Paths & config
# ---------------------------------------------------------------------------

APP_DIR = Path(__file__).resolve().parent
DEFAULT_REPO_ROOT = APP_DIR.parent


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader (KEY=VALUE). Does not override existing env."""
    if not path.is_file():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = val


_load_dotenv(APP_DIR / ".env")

REPO_ROOT = Path(os.environ.get("AGENTNEWSD_REPO_ROOT", str(DEFAULT_REPO_ROOT))).resolve()
CREATE_ARTICLE_SCRIPT = Path(
    os.environ.get(
        "AGENTNEWSD_CREATE_SCRIPT",
        str(REPO_ROOT / "scripts" / "create-article.sh"),
    )
).resolve()

API_KEY = os.environ.get("AGENTNEWSD_API_KEY", "").strip()
# 0.0.0.0 = all interfaces (remote clients). Override with AGENTNEWSD_HOST=127.0.0.1 for local-only.
HOST = os.environ.get("AGENTNEWSD_HOST", "0.0.0.0")
PORT = int(os.environ.get("AGENTNEWSD_PORT", "8790"))
# create-article can run a long Grok job (write, images, commit, push)
TIMEOUT_SECONDS = int(os.environ.get("AGENTNEWSD_TIMEOUT_SECONDS", "3600"))
MAX_ARTICLE_DEF_BYTES = int(os.environ.get("AGENTNEWSD_MAX_ARTICLE_DEF_BYTES", str(256 * 1024)))

ARTICLE_URL_RE = re.compile(
    r"https://agentnews\.site/article/[a-z0-9](?:[a-z0-9-]*[a-z0-9])?",
    re.IGNORECASE,
)

app = Flask(__name__)

# Only one create-article job at a time (git/commit safety).
_job_lock = threading.Lock()
_busy = False
_busy_lock = threading.Lock()


def _set_busy(value: bool) -> None:
    global _busy
    with _busy_lock:
        _busy = value


def _is_busy() -> bool:
    with _busy_lock:
        return _busy


def _ndjson(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n"


def _redact_sensitive_paths(text: str) -> str:
    """Strip home-dir / absolute-repo paths from client-facing log lines.

    Prevents leaking OS usernames via /home/<user>/... (or /Users/<user>/...).
    """
    if not text:
        return text
    out = text
    repo = str(REPO_ROOT)
    if repo:
        out = out.replace(repo, "<repo>")
    # Any remaining absolute home paths (child tools may print them)
    out = re.sub(r"(?i)/home/[^/\s\"']+", "/home/<user>", out)
    out = re.sub(r"(?i)/Users/[^/\s\"']+", "/Users/<user>", out)
    # Common temp brief path is fine; redaction above already covers home-based temps
    return out


def _check_api_key(provided: str | None) -> bool:
    if not API_KEY:
        return False
    if not provided:
        return False
    return secrets.compare_digest(provided, API_KEY)


def _extract_urls(text: str) -> list[str]:
    found = ARTICLE_URL_RE.findall(text)
    # Preserve order, unique
    seen: set[str] = set()
    out: list[str] = []
    for u in found:
        # normalize host case
        norm = re.sub(
            r"^https://agentnews\.site",
            "https://agentnews.site",
            u,
            count=1,
            flags=re.IGNORECASE,
        )
        if norm not in seen:
            seen.add(norm)
            out.append(norm)
    return out


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return False


def _fake_article_slug() -> str:
    """Four hyphenated segments, e.g. a1b2-c3d4-e5f6-7890."""
    return "-".join(secrets.token_hex(2) for _ in range(4))


def _fake_article_url(slug: str | None = None) -> str:
    return f"https://agentnews.site/article/{slug or _fake_article_slug()}"


def _generate_dry_run(article_def: str):
    """Simulate create-article progress without subprocess / Grok / git."""
    slug = _fake_article_slug()
    article_url = _fake_article_url(slug)
    brief_chars = len(article_def)
    preview = article_def.replace("\n", " ").strip()
    if len(preview) > 80:
        preview = preview[:77] + "..."

    steps = [
        (
            "status",
            {
                "type": "status",
                "phase": "starting",
                "dry_run": True,
                "message": "dry-run: validating request (no create-article.sh)",
            },
        ),
        (
            "sleep",
            0.15,
        ),
        (
            "status",
            {
                "type": "status",
                "phase": "running",
                "dry_run": True,
                "message": "dry-run: simulating article pipeline",
            },
        ),
        (
            "log",
            f"dry-run: brief_chars={brief_chars} preview={preview!r}",
        ),
        ("sleep", 0.2),
        ("log", "dry-run: would write articles/<slug>/article.md + assets/"),
        ("sleep", 0.15),
        ("log", "dry-run: would run image_gen / image_edit (skipped)"),
        ("sleep", 0.15),
        ("log", "dry-run: would git add, commit, push (skipped)"),
        ("sleep", 0.15),
        ("log", f"dry-run: Live links including {article_url}"),
        (
            "result",
            {
                "type": "result",
                "ok": True,
                "dry_run": True,
                "exit_code": 0,
                "slug": slug,
                "article_url": article_url,
                "urls": [article_url],
                "message": "dry-run complete (nothing committed or published)",
            },
        ),
    ]

    try:
        for step in steps:
            kind = step[0]
            if kind == "sleep":
                time.sleep(float(step[1]))
            elif kind == "status":
                yield _ndjson(step[1])
            elif kind == "log":
                yield _ndjson({"type": "log", "stream": "combined", "line": step[1]})
            elif kind == "result":
                yield _ndjson(step[1])
    finally:
        _set_busy(False)
        try:
            _job_lock.release()
        except RuntimeError:
            pass


@app.get("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "service": "agentnewsd",
            "busy": _is_busy(),
            "timeout_seconds": TIMEOUT_SECONDS,
            "dry_run_supported": True,
        }
    )


@app.post("/v1/create-article")
def create_article():
    if not API_KEY:
        return jsonify({"error": "server misconfigured: AGENTNEWSD_API_KEY not set"}), 500

    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415

    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "invalid JSON object body"}), 400

    api_key = body.get("api_key")
    if not isinstance(api_key, str) or not _check_api_key(api_key):
        return jsonify({"error": "unauthorized"}), 401

    dry_run = _truthy(body.get("dry_run", False))

    article_def = body.get("article_def")
    if not isinstance(article_def, str):
        return jsonify({"error": "article_def must be a string"}), 400

    article_def = article_def.strip()
    if not article_def:
        return jsonify({"error": "article_def is empty"}), 400

    def_bytes = len(article_def.encode("utf-8"))
    if def_bytes > MAX_ARTICLE_DEF_BYTES:
        return jsonify(
            {
                "error": "article_def too large",
                "max_bytes": MAX_ARTICLE_DEF_BYTES,
                "got_bytes": def_bytes,
            }
        ), 413

    if not dry_run:
        if not CREATE_ARTICLE_SCRIPT.is_file():
            return jsonify(
                {"error": f"create-article script not found: {CREATE_ARTICLE_SCRIPT}"}
            ), 500

        if not os.access(CREATE_ARTICLE_SCRIPT, os.X_OK):
            return jsonify(
                {
                    "error": f"create-article script not executable: {CREATE_ARTICLE_SCRIPT}"
                }
            ), 500

    # Non-blocking try: reject concurrent jobs
    if not _job_lock.acquire(blocking=False):
        return jsonify({"error": "busy", "message": "another article job is running"}), 409

    _set_busy(True)

    if dry_run:
        return Response(
            stream_with_context(_generate_dry_run(article_def)),
            mimetype="application/x-ndjson",
            headers={
                "Cache-Control": "no-cache, no-store",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    def generate():
        tmp_path: str | None = None
        proc: subprocess.Popen[str] | None = None
        combined_log: list[str] = []
        try:
            # Write brief to a private temp file; never put user text on argv.
            fd, tmp_path = tempfile.mkstemp(
                prefix="agentnewsd-brief.",
                suffix=".txt",
                dir=tempfile.gettempdir(),
                text=True,
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(article_def)
                    if not article_def.endswith("\n"):
                        f.write("\n")
            except Exception:
                os.close(fd)
                raise

            yield _ndjson(
                {
                    "type": "status",
                    "phase": "starting",
                    "message": "wrote brief to temp file; starting create-article.sh",
                    "timeout_seconds": TIMEOUT_SECONDS,
                }
            )

            # Fixed argv only — path is ours (mkstemp), not client-controlled shell.
            cmd = [str(CREATE_ARTICLE_SCRIPT), "--file", tmp_path]
            env = os.environ.copy()
            # Line-buffer friendliness for nested Python tools when supported
            env.setdefault("PYTHONUNBUFFERED", "1")

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                cwd=str(REPO_ROOT),
                env=env,
                shell=False,
            )

            yield _ndjson(
                {
                    "type": "status",
                    "phase": "running",
                    "message": "create-article.sh started",
                    "pid": proc.pid,
                }
            )

            assert proc.stdout is not None
            sel = selectors.DefaultSelector()
            sel.register(proc.stdout, selectors.EVENT_READ)
            deadline = time.monotonic() + TIMEOUT_SECONDS
            timed_out = False

            def _emit_log_line(line: str) -> str:
                # Keep raw text for URL extraction; redact only client-facing line.
                combined_log.append(line)
                return _ndjson(
                    {
                        "type": "log",
                        "stream": "combined",
                        "line": _redact_sensitive_paths(line.rstrip("\n")),
                    }
                )

            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    break

                if proc.poll() is not None:
                    # Process exited — drain remaining stdout
                    rest = proc.stdout.read()
                    if rest:
                        for line in rest.splitlines(keepends=True):
                            yield _emit_log_line(line)
                    break

                events = sel.select(timeout=min(1.0, remaining))
                for key, _ in events:
                    line = key.fileobj.readline()
                    if line == "":
                        # EOF; loop will exit via poll() on next iteration
                        continue
                    yield _emit_log_line(line)

            if timed_out:
                yield _ndjson(
                    {
                        "type": "status",
                        "phase": "timeout",
                        "message": f"job exceeded {TIMEOUT_SECONDS}s; killing process",
                    }
                )
                proc.kill()
                try:
                    proc.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    pass
                # Best-effort drain after kill
                try:
                    rest = proc.stdout.read()
                    if rest:
                        for line in rest.splitlines(keepends=True):
                            yield _emit_log_line(line)
                except Exception:
                    pass
                full_text = "".join(combined_log)
                urls = _extract_urls(full_text)
                yield _ndjson(
                    {
                        "type": "result",
                        "ok": False,
                        "error": "timeout",
                        "exit_code": proc.returncode,
                        "article_url": urls[-1] if urls else None,
                        "urls": urls,
                    }
                )
                return

            exit_code = proc.wait()
            full_text = "".join(combined_log)
            urls = _extract_urls(full_text)
            article_url = urls[-1] if urls else None
            ok = exit_code == 0 and article_url is not None

            yield _ndjson(
                {
                    "type": "result",
                    "ok": ok,
                    "exit_code": exit_code,
                    "article_url": article_url,
                    "urls": urls,
                    "message": (
                        "article created"
                        if ok
                        else (
                            "create-article exited non-zero"
                            if exit_code != 0
                            else "create-article finished but no article URL found in output"
                        )
                    ),
                }
            )
        except Exception as exc:
            if proc is not None and proc.poll() is None:
                try:
                    proc.kill()
                except Exception:
                    pass
            yield _ndjson(
                {
                    "type": "result",
                    "ok": False,
                    "error": "internal_error",
                    "message": str(exc),
                }
            )
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            _set_busy(False)
            try:
                _job_lock.release()
            except RuntimeError:
                pass

    return Response(
        stream_with_context(generate()),
        mimetype="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache, no-store",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


def main() -> None:
    if not API_KEY:
        print(
            "agentnewsd: warning: AGENTNEWSD_API_KEY is not set; all create requests will fail",
            file=sys.stderr,
        )
    print(
        f"agentnewsd: listening on http://{HOST}:{PORT}  repo={REPO_ROOT}",
        file=sys.stderr,
    )
    # threaded=True so /health works while a long job streams
    app.run(host=HOST, port=PORT, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
