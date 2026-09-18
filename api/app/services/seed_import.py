"""Import a generated articles/<slug>/ folder into an existing Mongo draft."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pymongo.database import Database

from app.config import Config
from app.db import utcnow
from app.services.articles import next_version_entry
from app.services.media_store import MediaStore
from scripts.onboard_content import media_name_from_path, parse_md, parse_when

log = logging.getLogger(__name__)


def find_article_folder(articles_dir: Path, slug: str, alt_slug: str | None = None) -> Path | None:
    for name in (slug, alt_slug):
        if not name:
            continue
        folder = articles_dir / name
        if (folder / "article.md").is_file():
            return folder
    return None


def collect_media(store: MediaStore, folder: Path, slug: str) -> list[dict[str, Any]]:
    media_items: list[dict[str, Any]] = []
    assets = folder / "assets"
    if not assets.is_dir():
        return media_items
    for asset in sorted(assets.rglob("*")):
        if not asset.is_file():
            continue
        rel_name = asset.name
        key = store.object_key("article", slug, rel_name)
        url = store.upload_file(asset, key)
        media_items.append(
            {
                "type": "video"
                if asset.suffix.lower() in {".mp4", ".webm", ".mov", ".ogg"}
                else "image",
                "name": media_name_from_path(rel_name),
                "filename": rel_name,
                "key": key,
                "url": url,
            }
        )
    return media_items


def merge_folder_into_article(
    cfg: Config,
    db: Database,
    store: MediaStore,
    folder: Path,
    *,
    target_slug: str,
    edited_by: str = "grok",
) -> dict[str, Any]:
    """Fill an existing CMS article from disk without changing publish/schedule flags."""
    existing = db.articles.find_one({"slug": target_slug})
    if not existing:
        raise KeyError(target_slug)
    md = folder / "article.md"
    if not md.is_file():
        raise FileNotFoundError(str(md))
    meta, body = parse_md(md)
    store.ensure_bucket()
    media_items = collect_media(store, folder, target_slug)
    hero = meta.get("hero") or ""
    hero_name = media_name_from_path(str(hero)) if hero else ""
    now = utcnow()
    published_at = parse_when(meta.get("published"), meta.get("date"))
    date_str = meta.get("date") or existing.get("date") or ""
    if published_at and not date_str:
        date_str = published_at.date().isoformat()
    versions = list(existing.get("versions") or [])
    next_ver = (versions[-1]["version"] + 1) if versions else 1
    versions.append(
        next_version_entry(
            version=next_ver,
            markdown=body,
            title=meta.get("title") or existing.get("title") or target_slug,
            edited_by=edited_by,
            reason="generated from creation_prompt",
        )
    )
    updates: dict[str, Any] = {
        "title": meta.get("title") or existing.get("title") or target_slug,
        "dek": meta.get("dek") or existing.get("dek") or "",
        "author": meta.get("author") or existing.get("author") or "Staff",
        "date": date_str,
        "section": meta.get("section") or existing.get("section") or "News",
        "tags": meta.get("tags") or existing.get("tags") or [],
        "hero": hero_name or existing.get("hero") or "",
        "markdown": body,
        "media": media_items,
        "agent_source": meta.get("agent_source") or "grok",
        "updated_at": now,
        "versions": versions,
    }
    if published_at and existing.get("status") == "published" and not existing.get("published_at"):
        updates["published_at"] = published_at
    db.articles.update_one({"slug": target_slug}, {"$set": updates})
    log.info("Imported generated folder %s → slug %s media=%d", folder.name, target_slug, len(media_items))
    return db.articles.find_one({"slug": target_slug})  # type: ignore[return-value]
