"""Portable article JSON bundles (definition + base64 assets) for instance-to-instance copy."""

from __future__ import annotations

import base64
import logging
import mimetypes
import re
import urllib.request
from pathlib import Path
from typing import Any

from pymongo.database import Database

from app.config import Config
from app.db import utcnow
from app.services.articles import (
    create_article,
    serialize_article,
    update_article,
    validate_slug,
)
from app.services.media_store import MediaStore

log = logging.getLogger(__name__)

BUNDLE_FORMAT = "agentnews.article.v1"
MAX_ASSETS = 40
MAX_ASSET_BYTES = 15 * 1024 * 1024
MAX_ASSETS_TOTAL_BYTES = 28 * 1024 * 1024
_MIME_RE = re.compile(
    r"^[a-zA-Z0-9][a-zA-Z0-9!#$&^_.+-]{0,80}/[a-zA-Z0-9][a-zA-Z0-9!#$&^_.+-]{0,80}$"
)


class BundleConflict(Exception):
    def __init__(self, slug: str) -> None:
        super().__init__(f"slug already exists: {slug}")
        self.slug = slug


def _safe_filename(raw: str, fallback: str = "asset.bin") -> str:
    name = Path(str(raw or "").replace("\\", "/")).name.strip()
    if not name or name in {".", ".."}:
        name = fallback
    return name[:180]


def _guess_mime(filename: str, declared: str = "") -> str:
    declared = (declared or "").strip()
    if declared and _MIME_RE.match(declared):
        return declared
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"


def _asset_kind(filename: str, declared: str = "") -> str:
    kind = (declared or "").strip().lower()
    if kind in {"image", "video"}:
        return kind
    ext = Path(filename).suffix.lower()
    if ext in {".mp4", ".webm", ".mov", ".ogg"}:
        return "video"
    return "image"


def _hero_ref(doc: dict[str, Any]) -> str:
    hero = str(doc.get("hero") or "").strip()
    if not hero:
        return ""
    if hero.startswith("http://") or hero.startswith("https://"):
        for item in doc.get("media") or []:
            if item.get("url") == hero:
                return str(item.get("filename") or item.get("name") or "")
        return ""
    return hero


def _decode_b64(raw: str, filename: str) -> bytes:
    text = (raw or "").strip()
    if not text:
        raise ValueError(f"asset {filename} has empty data")
    if text.startswith("data:") and "," in text:
        text = text.split(",", 1)[1]
    try:
        blob = base64.b64decode(text, validate=False)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"asset {filename} is not valid base64") from exc
    if not blob:
        raise ValueError(f"asset {filename} decoded empty")
    if len(blob) > MAX_ASSET_BYTES:
        raise ValueError(f"asset {filename} exceeds {MAX_ASSET_BYTES} bytes")
    return blob


def _read_asset_bytes(store: MediaStore, item: dict[str, Any], slug: str) -> bytes:
    key = str(item.get("key") or "").strip()
    if key:
        try:
            return store.get_bytes(key)
        except Exception as exc:  # noqa: BLE001
            log.warning("bundle export get_bytes %s: %s", key, exc)
    filename = _safe_filename(str(item.get("filename") or item.get("name") or ""))
    if filename and filename != "asset.bin":
        guessed = store.object_key("article", slug, filename)
        try:
            return store.get_bytes(guessed)
        except Exception as exc:  # noqa: BLE001
            log.warning("bundle export get_bytes %s: %s", guessed, exc)
    url = str(item.get("url") or "").strip()
    if url.startswith("http://") or url.startswith("https://"):
        with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310 — editor export of our own media
            data = resp.read(MAX_ASSET_BYTES + 1)
            if len(data) > MAX_ASSET_BYTES:
                raise ValueError(f"asset {filename} exceeds {MAX_ASSET_BYTES} bytes")
            return data
    raise FileNotFoundError(filename or key or url or "asset")


def export_article_bundle(
    cfg: Config,
    db: Database,
    slug: str,
    *,
    store: MediaStore | None = None,
) -> dict[str, Any]:
    slug = validate_slug(slug)
    doc = db.articles.find_one({"slug": slug})
    if not doc:
        raise KeyError(slug)
    media_store = store or MediaStore(cfg)
    assets: list[dict[str, Any]] = []
    asset_errors: list[str] = []
    total = 0
    for item in doc.get("media") or []:
        if not isinstance(item, dict):
            continue
        filename = _safe_filename(
            str(
                item.get("filename")
                or Path(str(item.get("key") or "")).name
                or item.get("name")
                or ""
            )
        )
        try:
            blob = _read_asset_bytes(media_store, item, slug)
        except Exception as exc:  # noqa: BLE001
            asset_errors.append(f"{filename}: {exc}")
            continue
        total += len(blob)
        if total > MAX_ASSETS_TOTAL_BYTES:
            raise ValueError("article assets exceed export size limit")
        if len(assets) >= MAX_ASSETS:
            raise ValueError(f"article has more than {MAX_ASSETS} assets")
        assets.append(
            {
                "filename": filename,
                "name": str(item.get("name") or Path(filename).stem),
                "type": _asset_kind(filename, str(item.get("type") or "")),
                "content_type": _guess_mime(filename, str(item.get("content_type") or "")),
                "data": base64.b64encode(blob).decode("ascii"),
            }
        )
    ser = serialize_article(doc, include_body=True, include_versions=False)
    article = {
        "slug": ser.get("slug"),
        "title": ser.get("title") or "",
        "dek": ser.get("dek") or "",
        "author": ser.get("author") or "Staff",
        "date": ser.get("date") or "",
        "section": ser.get("section") or "News",
        "tags": ser.get("tags") or [],
        "hero": _hero_ref(doc),
        "markdown": ser.get("markdown") or ser.get("body") or "",
        "disclaimer": bool(doc.get("disclaimer", True)),
        "agent_source": ser.get("agent_source") or "grok",
        "creation_prompt": ser.get("creation_prompt") or "",
        "status": ser.get("status") or "draft",
        "post_to_x": bool(ser.get("post_to_x", True)),
        "scheduled_at": ser.get("scheduled_at"),
        "published": ser.get("published") or ser.get("published_at") or "",
    }
    return {
        "format": BUNDLE_FORMAT,
        "exported_at": utcnow().isoformat().replace("+00:00", "Z"),
        "article": article,
        "assets": assets,
        "asset_errors": asset_errors,
    }


def parse_bundle(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("bundle must be a JSON object")
    inner = payload.get("bundle") if isinstance(payload.get("bundle"), dict) else payload
    fmt = str(inner.get("format") or "").strip()
    if fmt and fmt != BUNDLE_FORMAT:
        raise ValueError(f"unsupported bundle format: {fmt}")
    article = inner.get("article")
    assets = inner.get("assets")
    if not isinstance(article, dict):
        # Bare article-shaped object (title/markdown) is not enough without format.
        if inner.get("slug") and (inner.get("markdown") or inner.get("body") or inner.get("title")):
            article = inner
            assets = inner.get("assets") or []
        else:
            raise ValueError("bundle is missing article")
    if assets is None:
        assets = []
    if not isinstance(assets, list):
        raise ValueError("assets must be an array")
    if len(assets) > MAX_ASSETS:
        raise ValueError(f"bundle has more than {MAX_ASSETS} assets")
    return {"article": article, "assets": assets}


def import_article_bundle(
    cfg: Config,
    db: Database,
    payload: dict[str, Any],
    *,
    edited_by: str,
    overwrite: bool = False,
    as_draft: bool = True,
    store: MediaStore | None = None,
) -> dict[str, Any]:
    parsed = parse_bundle(payload)
    src = parsed["article"]
    raw_slug = str(payload.get("slug") or src.get("slug") or "").strip()
    slug = validate_slug(raw_slug)
    existing = db.articles.find_one({"slug": slug})
    if existing and not overwrite:
        raise BundleConflict(slug)

    media_store = store or MediaStore(cfg)
    media_store.ensure_bucket()
    media_items: list[dict[str, Any]] = []
    total = 0
    for item in parsed["assets"]:
        if not isinstance(item, dict):
            raise ValueError("each asset must be an object")
        filename = _safe_filename(str(item.get("filename") or item.get("name") or "asset.bin"))
        blob = _decode_b64(str(item.get("data") or ""), filename)
        total += len(blob)
        if total > MAX_ASSETS_TOTAL_BYTES:
            raise ValueError("bundle assets exceed import size limit")
        content_type = _guess_mime(filename, str(item.get("content_type") or ""))
        key = media_store.object_key("article", slug, filename)
        url = media_store.upload_bytes(blob, key, content_type=content_type)
        media_items.append(
            {
                "type": _asset_kind(filename, str(item.get("type") or "")),
                "name": str(item.get("name") or Path(filename).stem),
                "filename": filename,
                "key": key,
                "url": url,
                "content_type": content_type,
            }
        )

    status = "draft" if as_draft else (str(src.get("status") or "draft"))
    if status not in {"draft", "published", "scheduled"}:
        raise ValueError(f"invalid status: {status}")
    hero = str(src.get("hero") or "")
    if hero.startswith("http://") or hero.startswith("https://"):
        hero = ""
    create_payload: dict[str, Any] = {
        "slug": slug,
        "title": src.get("title") or slug,
        "dek": src.get("dek") or "",
        "author": src.get("author") or "Staff",
        "date": src.get("date") or "",
        "section": src.get("section") or "News",
        "tags": src.get("tags") or [],
        "hero": hero,
        "markdown": src.get("markdown") or src.get("body") or "",
        "disclaimer": src.get("disclaimer", True),
        "agent_source": src.get("agent_source") or "grok",
        "creation_prompt": src.get("creation_prompt") or src.get("article_def") or "",
        "status": status,
        "post_to_x": src.get("post_to_x", True),
        "media": media_items,
        "reason": "imported article bundle",
    }
    if not as_draft:
        if src.get("scheduled_at"):
            create_payload["scheduled_at"] = src.get("scheduled_at")
        if src.get("published") or src.get("published_at"):
            create_payload["published_at"] = src.get("published") or src.get("published_at")

    if existing:
        update_payload = dict(create_payload)
        update_payload.pop("slug", None)
        return update_article(db, slug, update_payload, edited_by=edited_by)
    return create_article(db, create_payload, edited_by=edited_by, cfg=cfg)
