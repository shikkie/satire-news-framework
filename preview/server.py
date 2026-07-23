#!/usr/bin/env python3
"""Local preview API for satire-news-framework article + ad folders.

Serves:
  GET /api/health
  GET /api/articles
  GET /api/articles/<slug>
  GET /api/ads
  GET /api/ads/<slug>
  GET /content/<slug>/...      → articles/<slug>/
  GET /ads-content/<slug>/...  → ads/<slug>/
"""

from __future__ import annotations

import json
import mimetypes
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "articles"
ADS_DIR = ROOT / "ads"
# 0.0.0.0 = all interfaces (phone / LAN access). Override with API_HOST=127.0.0.1 for local-only.
HOST = os.environ.get("API_HOST", "0.0.0.0")
PORT = int(os.environ.get("API_PORT", "8787"))

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)


def parse_simple_yaml(text: str) -> dict:
    """Tiny YAML subset for article frontmatter (no external deps)."""
    data: dict = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.strip()
        val = val.strip()
        if not key:
            continue
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            items = []
            if inner:
                for part in inner.split(","):
                    items.append(_unquote(part.strip()))
            data[key] = items
            continue
        if val.lower() in ("true", "false"):
            data[key] = val.lower() == "true"
            continue
        data[key] = _unquote(val)
    return data


def _unquote(val: str):
    if (val.startswith('"') and val.endswith('"')) or (
        val.startswith("'") and val.endswith("'")
    ):
        return val[1:-1]
    return val


def parse_article_md(path: Path) -> dict | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    m = FRONTMATTER_RE.match(raw)
    if m:
        meta = parse_simple_yaml(m.group(1))
        body = m.group(2).strip()
    else:
        meta = {}
        body = raw.strip()
        if not meta.get("title"):
            first = body.splitlines()[0].lstrip("# ").strip() if body else path.parent.name
            meta["title"] = first or path.parent.name
    return {"meta": meta, "body": body}


def _primary_sort_ms(meta: dict) -> float:
    """Milliseconds for published ISO or date-only frontmatter (newest first)."""
    pub = str(meta.get("published") or "").strip()
    if pub:
        try:
            # Support trailing Z
            return datetime.fromisoformat(pub.replace("Z", "+00:00")).timestamp() * 1000
        except ValueError:
            pass
    d = str(meta.get("date") or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
        try:
            return (
                datetime(int(d[0:4]), int(d[5:7]), int(d[8:10]), tzinfo=timezone.utc)
                .timestamp()
                * 1000
            )
        except ValueError:
            pass
    return 0.0


def _recency_ms(folder: Path, md: Path) -> float:
    """Git last-commit time on the article folder, else article.md mtime."""
    try:
        out = subprocess.check_output(
            ["git", "log", "-1", "--format=%ct", "--", str(folder)],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if out:
            sec = float(out)
            if sec > 0:
                return sec * 1000
    except (subprocess.CalledProcessError, OSError, ValueError):
        pass
    try:
        return md.stat().st_mtime * 1000
    except OSError:
        return 0.0


def list_articles() -> list[dict]:
    """List articles newest-first: published → date → git/mtime recency."""
    items: list[dict] = []
    if not ARTICLES_DIR.is_dir():
        return items
    for folder in sorted(ARTICLES_DIR.iterdir()):
        if not folder.is_dir() or folder.name.startswith("."):
            continue
        md = folder / "article.md"
        if not md.is_file():
            continue
        parsed = parse_article_md(md)
        if not parsed:
            continue
        meta = parsed["meta"]
        slug = folder.name
        items.append(
            {
                "slug": slug,
                "title": meta.get("title") or slug,
                "dek": meta.get("dek") or "",
                "author": meta.get("author") or "Staff",
                "date": meta.get("date") or "",
                "published": meta.get("published") or "",
                "section": meta.get("section") or "News",
                "hero": meta.get("hero") or "",
                "tags": meta.get("tags") or [],
                "disclaimer": meta.get("disclaimer", True),
                "_sort_primary": _primary_sort_ms(meta),
                "_sort_recency": _recency_ms(folder, md),
            }
        )
    items.sort(
        key=lambda a: (
            -a.get("_sort_primary", 0),
            -a.get("_sort_recency", 0),
            a.get("slug") or "",
        )
    )
    for a in items:
        a.pop("_sort_primary", None)
        a.pop("_sort_recency", None)
    return items


def get_article(slug: str) -> dict | None:
    folder = ARTICLES_DIR / slug
    md = folder / "article.md"
    if not md.is_file():
        return None
    parsed = parse_article_md(md)
    if not parsed:
        return None
    meta = parsed["meta"]
    return {
        "slug": slug,
        "title": meta.get("title") or slug,
        "dek": meta.get("dek") or "",
        "author": meta.get("author") or "Staff",
        "date": meta.get("date") or "",
        "published": meta.get("published") or "",
        "section": meta.get("section") or "News",
        "hero": meta.get("hero") or "",
        "tags": meta.get("tags") or [],
        "disclaimer": meta.get("disclaimer", True),
        "body": parsed["body"],
    }


def safe_under(root: Path, slug: str, rel: str) -> Path | None:
    if ".." in slug or ".." in rel or rel.startswith("/"):
        return None
    base = (root / slug).resolve()
    target = (base / rel).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        return None
    if not target.is_file():
        return None
    return target


def safe_content_path(slug: str, rel: str) -> Path | None:
    return safe_under(ARTICLES_DIR, slug, rel)


def safe_ad_path(slug: str, rel: str) -> Path | None:
    return safe_under(ADS_DIR, slug, rel)


def list_ads() -> list[dict]:
    items: list[dict] = []
    if not ADS_DIR.is_dir():
        return items
    for folder in sorted(ADS_DIR.iterdir()):
        if not folder.is_dir() or folder.name.startswith("."):
            continue
        md = folder / "business.md"
        if not md.is_file():
            continue
        parsed = parse_article_md(md)
        if not parsed:
            continue
        meta = parsed["meta"]
        if meta.get("active") is False:
            continue
        weight = meta.get("weight", 1)
        try:
            weight = float(weight)
        except (TypeError, ValueError):
            weight = 1
        items.append(
            {
                "slug": folder.name,
                "name": meta.get("name") or folder.name,
                "tagline": meta.get("tagline") or "",
                "phone": meta.get("phone") or "",
                "email": meta.get("email") or "",
                "website": meta.get("website") or "",
                "address": meta.get("address") or "",
                "hours": meta.get("hours") or "",
                "category": meta.get("category") or "Sponsored",
                "cta": meta.get("cta") or "Learn more",
                "logo": meta.get("logo") or "",
                "image": meta.get("image") or meta.get("hero") or "",
                "weight": weight if weight > 0 else 1,
                "active": True,
                "bio": parsed["body"],
            }
        )
    return items


def get_ad(slug: str) -> dict | None:
    for ad in list_ads():
        if ad["slug"] == slug:
            return ad
    return None


class Handler(BaseHTTPRequestHandler):
    server_version = "SatirePreview/0.1"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(
            f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {self.address_string()} {fmt % args}\n"
        )

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code: int, payload) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _bytes(self, code: int, data: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path == "/api/health":
            self._json(
                200,
                {
                    "ok": True,
                    "articles_dir": str(ARTICLES_DIR),
                    "ads_dir": str(ADS_DIR),
                    "count": len(list_articles()),
                    "ads": len(list_ads()),
                },
            )
            return

        if path == "/api/articles":
            self._json(200, {"articles": list_articles()})
            return

        m = re.fullmatch(r"/api/articles/([^/]+)", path)
        if m:
            article = get_article(m.group(1))
            if not article:
                self._json(404, {"error": "article not found"})
                return
            self._json(200, article)
            return

        if path == "/api/ads":
            self._json(200, {"ads": list_ads()})
            return

        m = re.fullmatch(r"/api/ads/([^/]+)", path)
        if m:
            ad = get_ad(m.group(1))
            if not ad:
                self._json(404, {"error": "ad not found"})
                return
            self._json(200, ad)
            return

        m = re.fullmatch(r"/content/([^/]+)/(.*)", path)
        if m:
            file_path = safe_content_path(m.group(1), m.group(2))
            if not file_path:
                self._json(404, {"error": "file not found"})
                return
            ctype = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
            self._bytes(200, file_path.read_bytes(), ctype)
            return

        m = re.fullmatch(r"/ads-content/([^/]+)/(.*)", path)
        if m:
            file_path = safe_ad_path(m.group(1), m.group(2))
            if not file_path:
                self._json(404, {"error": "file not found"})
                return
            ctype = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
            self._bytes(200, file_path.read_bytes(), ctype)
            return

        self._json(404, {"error": "not found", "path": path})


def main() -> int:
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    ADS_DIR.mkdir(parents=True, exist_ok=True)
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Preview API listening on http://{HOST}:{PORT}", flush=True)
    print(f"Articles root: {ARTICLES_DIR}", flush=True)
    print(f"Ads root: {ADS_DIR}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down preview server.", flush=True)
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
