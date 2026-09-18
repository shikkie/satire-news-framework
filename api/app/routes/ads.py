"""Public ads API (rotation)."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, request

from app.auth import get_config
from app.db import get_db

bp = Blueprint("ads", __name__, url_prefix="/api/ads")


def _serialize_ad(doc: dict[str, Any]) -> dict[str, Any]:
    media = doc.get("media") or []
    logo = doc.get("logo") or ""
    image = doc.get("image") or doc.get("hero") or ""
    if logo and not str(logo).startswith("http"):
        for m in media:
            if m.get("name") in (logo, "logo") or (m.get("key") or "").endswith("/logo.jpg"):
                logo = m.get("url") or logo
                break
    if image and not str(image).startswith("http"):
        for m in media:
            if m.get("name") in (image, "hero") or "hero" in (m.get("key") or ""):
                image = m.get("url") or image
                break
    # Prefer full URLs for SPA
    if not logo and media:
        for m in media:
            if "logo" in (m.get("name") or "") or "logo" in (m.get("key") or ""):
                logo = m.get("url") or ""
                break
    if not image and media:
        image = media[0].get("url") or ""

    return {
        "slug": doc.get("slug"),
        "name": doc.get("name") or doc.get("title") or doc.get("slug"),
        "tagline": doc.get("tagline") or doc.get("dek") or "",
        "body": doc.get("body") or doc.get("markdown") or "",
        "cta": doc.get("cta") or "",
        "url": doc.get("url") or doc.get("link") or "#",
        "logo": logo,
        "image": image,
        "weight": doc.get("weight", 1),
        "active": doc.get("active", True),
        "media": media,
    }


@bp.get("")
def list_ads():  # type: ignore[no-untyped-def]
    cfg = get_config()
    db = get_db(cfg)
    only_active = request.args.get("all") not in ("1", "true")
    query: dict[str, Any] = {}
    if only_active:
        query["active"] = {"$ne": False}
    docs = list(db.ads.find(query).sort("slug", 1))
    return jsonify({"ads": [_serialize_ad(d) for d in docs]})


@bp.get("/<slug>")
def get_ad(slug: str):  # type: ignore[no-untyped-def]
    cfg = get_config()
    db = get_db(cfg)
    doc = db.ads.find_one({"slug": slug})
    if not doc or doc.get("active") is False:
        return jsonify({"error": "not_found"}), 404
    return jsonify(_serialize_ad(doc))
