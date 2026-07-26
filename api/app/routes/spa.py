"""Serve React SPA + OG HTML shells for social bots on /article/<slug>."""

from __future__ import annotations

import html
import re
from pathlib import Path

from flask import Blueprint, Response, request, send_from_directory

from app.auth import get_config
from app.db import get_db
from app.services.articles import serialize_article

bp = Blueprint("spa", __name__)

BOT_UA = re.compile(
    r"(bot|crawl|slurp|spider|facebookexternalhit|Facebot|Twitterbot|LinkedInBot|"
    r"Discordbot|Slackbot|WhatsApp|TelegramBot|SkypeUriPreview|embedly|quora|"
    r"pinterest|redditbot|Applebot|Googlebot|bingbot)",
    re.I,
)


def _static_root() -> Path | None:
    cfg = get_config()
    p = Path(cfg.static_dir)
    return p if p.is_dir() else None


def _is_bot() -> bool:
    ua = request.headers.get("User-Agent") or ""
    return bool(BOT_UA.search(ua))


def _read_index() -> str | None:
    root = _static_root()
    if not root:
        return None
    index = root / "index.html"
    if not index.is_file():
        return None
    return index.read_text(encoding="utf-8")


def _og_shell(article: dict) -> str:
    cfg = get_config()
    title = html.escape(article.get("title") or "Agent News")
    dek = html.escape(article.get("dek") or article.get("title") or "")
    url = html.escape(cfg.article_page_url(article["slug"]))
    image = article.get("hero") or f"{cfg.site_url.rstrip('/')}/og-default.jpg"
    if image and not str(image).startswith("http"):
        image = f"{cfg.site_url.rstrip('/')}/{str(image).lstrip('/')}"
    image = html.escape(str(image))
    site = html.escape(cfg.site_name)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{title} — {site}</title>
  <meta name="description" content="{dek}" />
  <meta property="og:type" content="article" />
  <meta property="og:site_name" content="{site}" />
  <meta property="og:title" content="{title}" />
  <meta property="og:description" content="{dek}" />
  <meta property="og:url" content="{url}" />
  <meta property="og:image" content="{image}" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{title}" />
  <meta name="twitter:description" content="{dek}" />
  <meta name="twitter:image" content="{image}" />
  <link rel="canonical" href="{url}" />
</head>
<body>
  <article>
    <h1>{title}</h1>
    <p>{dek}</p>
    <p><a href="{url}">Read on {site}</a></p>
  </article>
</body>
</html>
"""


@bp.get("/article/<slug>")
@bp.get("/article/<slug>/")
def article_shell(slug: str):  # type: ignore[no-untyped-def]
    if _is_bot():
        cfg = get_config()
        db = get_db(cfg)
        doc = db.articles.find_one({"slug": slug, "status": "published"})
        if doc:
            ser = serialize_article(doc, include_body=False)
            return Response(_og_shell(ser), mimetype="text/html; charset=utf-8")
    # Browsers: SPA index
    body = _read_index()
    if body is None:
        return Response("SPA not built — run frontend build into api/static", status=503)
    return Response(body, mimetype="text/html; charset=utf-8")


@bp.get("/", defaults={"path": ""})
@bp.get("/<path:path>")
def spa_fallback(path: str):  # type: ignore[no-untyped-def]
    # Never shadow /api
    if path.startswith("api/") or path == "api":
        return Response("Not found", status=404)

    root = _static_root()
    if root:
        candidate = root / path
        if path and candidate.is_file():
            return send_from_directory(root, path)

    body = _read_index()
    if body is None:
        return Response(
            "<!doctype html><title>Agent News API</title>"
            "<p>API is up. Build the SPA into <code>api/static</code> or use Vite dev.</p>",
            mimetype="text/html",
        )
    return Response(body, mimetype="text/html; charset=utf-8")
