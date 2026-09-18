"""Public + authenticated article APIs."""

from __future__ import annotations

from flask import Blueprint, Response, current_app, g, jsonify, request, stream_with_context

from app.auth import get_config, require_editor_or_admin
from app.db import get_db, utcnow
from app.services.article_bundle import (
    BundleConflict,
    export_article_bundle,
    import_article_bundle,
)
from app.services.articles import (
    create_article,
    is_placeholder_slug,
    search_articles,
    serialize_article,
    update_article,
    validate_slug,
)
from app.services.generate import generate_configured, start_generate
from app.services.publish import after_publish, publish_due_articles

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
    docs = search_articles(db, q=q, status=status, public_only=False, sort=sort, limit=limit)
    articles = []
    for d in docs:
        gen = d.get("generation") or {}
        if d.get("placeholder") and gen.get("final_slug") and gen.get("status") == "ok":
            continue
        articles.append(serialize_article(d, include_body=False, include_versions=False))
    return jsonify({"articles": articles})


def _queue_generate(db, cfg, doc, prompt: str):  # type: ignore[no-untyped-def]
    slug = doc["slug"]
    gen = doc.get("generation") or {}
    if gen.get("status") == "running":
        return jsonify({"error": "busy", "message": "generate already running"}), 409
    db.articles.update_one(
        {"slug": slug},
        {
            "$set": {
                "creation_prompt": prompt,
                "generation": {
                    "status": "running",
                    "error": "",
                    "logs": ["Queued generate job…"],
                    "events": [
                        {
                            "kind": "status",
                            "text": "Queued ACP generate job…",
                            "name": "",
                            "status": "",
                            "at": utcnow().isoformat().replace("+00:00", "Z"),
                        }
                    ],
                    "started_at": utcnow(),
                    "finished_at": None,
                    "updated_at": utcnow(),
                    "article_url": "",
                    "final_slug": "",
                    "invent_slug": is_placeholder_slug(slug),
                },
            }
        },
    )
    start_generate(current_app._get_current_object(), slug)
    fresh = db.articles.find_one({"slug": slug})
    return jsonify({"ok": True, "article": serialize_article(fresh, include_body=True)}), 202


@bp.post("/generate")
@require_editor_or_admin
def generate_new():  # type: ignore[no-untyped-def]
    """Create a draft (slug optional) and kick off Grok. AI may invent the slug."""
    cfg = get_config()
    db = get_db(cfg)
    data = request.get_json(silent=True) or {}
    prompt = str(data.get("creation_prompt") or data.get("article_def") or "").strip()
    if not prompt:
        return jsonify({"error": "bad_request", "message": "creation_prompt is empty"}), 400
    if not generate_configured(cfg):
        return jsonify(
            {
                "error": "not_configured",
                "message": "Grok binary is not available in this API container (GROK_BIN)",
            }
        ), 503
    payload = dict(data)
    payload["creation_prompt"] = prompt
    payload["status"] = payload.get("status") or "draft"
    if not str(payload.get("slug") or "").strip():
        payload.pop("slug", None)
    try:
        doc = create_article(db, payload, edited_by=g.username or "unknown", cfg=cfg)
    except ValueError as exc:
        return jsonify({"error": "bad_request", "message": str(exc)}), 400
    return _queue_generate(db, cfg, doc, prompt)


@bp.post("/<slug>/generate")
@require_editor_or_admin
def generate(slug: str):  # type: ignore[no-untyped-def]
    """Kick off a Grok CMS generate job, then import files into this draft."""
    cfg = get_config()
    db = get_db(cfg)
    try:
        slug = validate_slug(slug)
    except ValueError:
        return jsonify({"error": "not_found"}), 404
    doc = db.articles.find_one({"slug": slug})
    if not doc:
        return jsonify({"error": "not_found"}), 404
    data = request.get_json(silent=True) or {}
    prompt = str(data.get("creation_prompt") or doc.get("creation_prompt") or "").strip()
    if not prompt:
        return jsonify({"error": "bad_request", "message": "creation_prompt is empty"}), 400
    if not generate_configured(cfg):
        return jsonify(
            {
                "error": "not_configured",
                "message": "Grok binary is not available in this API container (GROK_BIN)",
            }
        ), 503
    return _queue_generate(db, cfg, doc, prompt)


@bp.get("/<slug>/generate/stream")
@require_editor_or_admin
def generate_stream(slug: str):  # type: ignore[no-untyped-def]
    """NDJSON tail of ACP generate events (studio live view)."""
    cfg = get_config()
    db = get_db(cfg)
    try:
        slug = validate_slug(slug)
    except ValueError:
        return jsonify({"error": "not_found"}), 404
    if not db.articles.find_one({"slug": slug}):
        return jsonify({"error": "not_found"}), 404

    def gen():  # type: ignore[no-untyped-def]
        import json
        import time

        seen = 0
        idle = 0
        while idle < 1200:
            doc = db.articles.find_one({"slug": slug}, {"generation": 1})
            gen_state = (doc or {}).get("generation") or {}
            events = gen_state.get("events") or []
            if not isinstance(events, list):
                events = []
            if len(events) > seen:
                for item in events[seen:]:
                    yield json.dumps({"type": "event", "event": item}) + "\n"
                seen = len(events)
                idle = 0
            status = gen_state.get("status") or ""
            if status in {"ok", "error"} and seen >= len(events):
                yield (
                    json.dumps(
                        {
                            "type": "done",
                            "status": status,
                            "error": gen_state.get("error") or "",
                            "final_slug": gen_state.get("final_slug") or slug,
                        }
                    )
                    + "\n"
                )
                return
            time.sleep(0.4)
            idle += 1

    return Response(
        stream_with_context(gen()),
        mimetype="application/x-ndjson",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@bp.post("/admin/publish-due")
@require_editor_or_admin
def publish_due():  # type: ignore[no-untyped-def]
    """Manually run the scheduled-publish tick (also runs in the background)."""
    cfg = get_config()
    db = get_db(cfg)
    results = publish_due_articles(cfg, db)
    return jsonify({"published": results, "count": len(results)})


@bp.get("/<slug>/export")
@require_editor_or_admin
def export_one(slug: str):  # type: ignore[no-untyped-def]
    """JSON bundle: article fields + base64 assets (portable across instances)."""
    import json

    cfg = get_config()
    db = get_db(cfg)
    try:
        bundle = export_article_bundle(cfg, db, slug)
    except KeyError:
        return jsonify({"error": "not_found"}), 404
    except ValueError as exc:
        msg = str(exc)
        if "slug must" in msg:
            return jsonify({"error": "not_found"}), 404
        return jsonify({"error": "bad_request", "message": msg}), 400
    if request.args.get("download") == "1":
        filename = f"{bundle['article']['slug']}.article.json"
        return Response(
            json.dumps(bundle, separators=(",", ":")),
            mimetype="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-store",
            },
        )
    return jsonify(bundle)


@bp.post("/import")
@require_editor_or_admin
def import_one():  # type: ignore[no-untyped-def]
    """Create (or overwrite) an article from an exported JSON bundle."""
    cfg = get_config()
    db = get_db(cfg)
    data = request.get_json(silent=True) or {}
    overwrite = bool(data.get("overwrite")) or request.args.get("overwrite") == "1"
    as_draft = True
    if "as_draft" in data:
        as_draft = bool(data.get("as_draft"))
    elif request.args.get("as_draft") == "0":
        as_draft = False
    try:
        doc = import_article_bundle(
            cfg,
            db,
            data,
            edited_by=g.username or "unknown",
            overwrite=overwrite,
            as_draft=as_draft,
        )
    except BundleConflict as exc:
        return jsonify(
            {
                "error": "conflict",
                "message": str(exc),
                "slug": exc.slug,
            }
        ), 409
    except ValueError as exc:
        return jsonify({"error": "bad_request", "message": str(exc)}), 400
    except KeyError:
        return jsonify({"error": "not_found"}), 404
    out = serialize_article(doc, include_body=True, include_versions=True)
    return jsonify({"article": out, "cdn": None, "x_post": None}), (200 if overwrite else 201)


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
    # Public: published, or unpublished with ?_agentnewspreview=1
    preview = request.args.get("_agentnewspreview") == "1"
    if doc.get("status") != "published" and not preview:
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
    try:
        doc = create_article(db, data, edited_by=g.username or "unknown", cfg=cfg)
    except ValueError as exc:
        return jsonify({"error": "bad_request", "message": str(exc)}), 400
    out = serialize_article(doc, include_body=True, include_versions=True)
    side = {"cdn": None, "x_post": None}
    if doc.get("status") == "published":
        side = after_publish(cfg, db, doc, newly_published=True)
        out = serialize_article(
            db.articles.find_one({"slug": doc["slug"]}) or doc,
            include_body=True,
            include_versions=True,
        )
    return jsonify({"article": out, **side}), 201


@bp.put("/<slug>")
@bp.patch("/<slug>")
@require_editor_or_admin
def update(slug: str):  # type: ignore[no-untyped-def]
    cfg = get_config()
    db = get_db(cfg)
    data = request.get_json(silent=True) or {}
    prev = db.articles.find_one({"slug": slug})
    try:
        doc = update_article(db, slug, data, edited_by=g.username or "unknown")
    except KeyError:
        return jsonify({"error": "not_found"}), 404
    except ValueError as exc:
        return jsonify({"error": "bad_request", "message": str(exc)}), 400
    side = {"cdn": None, "x_post": None}
    if doc.get("status") == "published":
        was_pub = bool(prev and prev.get("status") == "published")
        side = after_publish(cfg, db, doc, newly_published=not was_pub)
        doc = db.articles.find_one({"slug": slug})
    out = serialize_article(doc, include_body=True, include_versions=True)
    return jsonify({"article": out, **side})


@bp.post("/<slug>/publish")
@require_editor_or_admin
def publish(slug: str):  # type: ignore[no-untyped-def]
    cfg = get_config()
    db = get_db(cfg)
    prev = db.articles.find_one({"slug": slug})
    try:
        doc = update_article(
            db,
            slug,
            {"status": "published", "reason": "publish"},
            edited_by=g.username or "unknown",
        )
    except KeyError:
        return jsonify({"error": "not_found"}), 404
    except ValueError as exc:
        return jsonify({"error": "bad_request", "message": str(exc)}), 400
    was_pub = bool(prev and prev.get("status") == "published")
    side = after_publish(cfg, db, doc, newly_published=not was_pub)
    doc = db.articles.find_one({"slug": slug})
    out = serialize_article(doc, include_body=True, include_versions=True)
    return jsonify({"article": out, **side})
