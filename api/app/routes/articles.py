"""Public + authenticated article APIs."""

from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from app.auth import get_config, require_editor_or_admin
from app.db import get_db
from app.services.articles import (
    create_article,
    search_articles,
    serialize_article,
    update_article,
    validate_slug,
)
from app.services.cdn import CdnService

bp = Blueprint("articles", __name__, url_prefix="/api/articles")


@bp.get("")
def list_public():  # type: ignore[no-untyped-def]
    """Public homepage list — published only."""
    cfg = get_config()
    db = get_db(cfg)
    q = request.args.get("q")
    sort = request.args.get("sort") or "published_at"
    limit = min(int(request.args.get("limit") or 100), 500)
    docs = search_articles(db, q=q, public_only=True, sort=sort, limit=limit)
    articles = [serialize_article(d, include_body=False) for d in docs]
    return jsonify({"articles": articles})


@bp.get("/admin")
@require_editor_or_admin
def list_admin():  # type: ignore[no-untyped-def]
    cfg = get_config()
    db = get_db(cfg)
    q = request.args.get("q")
    status = request.args.get("status")
    sort = request.args.get("sort") or "updated_at"
    limit = min(int(request.args.get("limit") or 200), 500)
    docs = search_articles(
        db, q=q, status=status, public_only=False, sort=sort, limit=limit
    )
    articles = [
        serialize_article(d, include_body=False, include_versions=False) for d in docs
    ]
    return jsonify({"articles": articles})


@bp.get("/<slug>")
def get_one(slug: str):  # type: ignore[no-untyped-def]
    cfg = get_config()
    db = get_db(cfg)
    try:
        slug = validate_slug(slug)
    except ValueError:
        return jsonify({"error": "not_found"}), 404
    doc = db.articles.find_one({"slug": slug})
    if not doc:
        return jsonify({"error": "not_found"}), 404
    # Public: only published
    if doc.get("status") != "published":
        # Editors may fetch drafts with session
        from app.auth import load_session

        sess = load_session()
        if not sess:
            return jsonify({"error": "not_found"}), 404
    return jsonify(serialize_article(doc, include_body=True, include_versions=False))


@bp.get("/<slug>/versions")
@require_editor_or_admin
def versions(slug: str):  # type: ignore[no-untyped-def]
    cfg = get_config()
    db = get_db(cfg)
    doc = db.articles.find_one({"slug": slug})
    if not doc:
        return jsonify({"error": "not_found"}), 404
    ser = serialize_article(doc, include_body=True, include_versions=True)
    return jsonify({"slug": slug, "versions": ser.get("versions") or []})


@bp.post("")
@require_editor_or_admin
def create():  # type: ignore[no-untyped-def]
    cfg = get_config()
    db = get_db(cfg)
    data = request.get_json(silent=True) or {}
    if not data.get("slug"):
        return jsonify({"error": "bad_request", "message": "slug required"}), 400
    try:
        doc = create_article(db, data, edited_by=g.username or "unknown", cfg=cfg)
    except ValueError as exc:
        return jsonify({"error": "bad_request", "message": str(exc)}), 400
    out = serialize_article(doc, include_body=True, include_versions=True)
    cdn_result = None
    if doc.get("status") == "published":
        cdn_result = _publish_cdn(cfg, doc)
    return jsonify({"article": out, "cdn": cdn_result}), 201


@bp.put("/<slug>")
@bp.patch("/<slug>")
@require_editor_or_admin
def update(slug: str):  # type: ignore[no-untyped-def]
    cfg = get_config()
    db = get_db(cfg)
    data = request.get_json(silent=True) or {}
    try:
        doc = update_article(db, slug, data, edited_by=g.username or "unknown")
    except KeyError:
        return jsonify({"error": "not_found"}), 404
    except ValueError as exc:
        return jsonify({"error": "bad_request", "message": str(exc)}), 400
    out = serialize_article(doc, include_body=True, include_versions=True)
    cdn_result = None
    if doc.get("status") == "published":
        cdn_result = _publish_cdn(cfg, doc)
    return jsonify({"article": out, "cdn": cdn_result})


@bp.post("/<slug>/publish")
@require_editor_or_admin
def publish(slug: str):  # type: ignore[no-untyped-def]
    cfg = get_config()
    db = get_db(cfg)
    try:
        doc = update_article(
            db,
            slug,
            {"status": "published", "reason": "publish"},
            edited_by=g.username or "unknown",
        )
    except KeyError:
        return jsonify({"error": "not_found"}), 404
    out = serialize_article(doc, include_body=True, include_versions=True)
    cdn_result = _publish_cdn(cfg, doc)
    return jsonify({"article": out, "cdn": cdn_result})


def _publish_cdn(cfg, doc):  # type: ignore[no-untyped-def]
    media = doc.get("media") or []
    media_urls = [m.get("url") for m in media if m.get("url")]
    ser = serialize_article(doc, include_body=False)
    og = ser.get("hero") if str(ser.get("hero") or "").startswith("http") else None
    if not og and media_urls:
        og = media_urls[0]
    return CdnService(cfg).after_article_publish(
        slug=doc["slug"],
        article_url=cfg.article_page_url(doc["slug"]),
        og_image_url=og,
        media_urls=media_urls,
    )
