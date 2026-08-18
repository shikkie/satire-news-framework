#!/usr/bin/env python3
"""Onboard existing articles/ and ads/ into MongoDB + S3 (MinIO/Spaces).

Usage (compose):
  docker compose exec api python -m scripts.onboard_content

Local:
  SEED_ARTICLES_DIR=../../articles SEED_ADS_DIR=../../ads \\
    MONGO_URI=mongodb://127.0.0.1:27017 \\
    python -m scripts.onboard_content [--dry-run] [--articles-only] [--ads-only]
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

# Allow `python -m scripts.onboard_content` from /app
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Config  # noqa: E402
from app.db import ensure_indexes, get_db, utcnow  # noqa: E402
from app.services.media_store import MediaStore  # noqa: E402

log = logging.getLogger("onboard")

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)


def parse_simple_yaml(text: str) -> dict:
    data: dict = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
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


def parse_md(path: Path) -> tuple[dict, str]:
    raw = path.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(raw)
    if m:
        return parse_simple_yaml(m.group(1)), m.group(2).strip()
    return {}, raw.strip()


def media_name_from_path(rel: str) -> str:
    name = Path(rel).name
    stem = Path(name).stem
    return stem


def parse_when(*candidates) -> datetime | None:
    """Parse frontmatter published/date into an aware UTC datetime."""
    for raw in candidates:
        if raw is None:
            continue
        text = str(raw).strip()
        if not text:
            continue
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    return None


def onboard_articles(
    cfg: Config,
    store: MediaStore,
    articles_dir: Path,
    *,
    dry_run: bool,
) -> int:
    db = get_db(cfg)
    count = 0
    if not articles_dir.is_dir():
        log.warning("articles dir missing: %s", articles_dir)
        return 0
    for folder in sorted(articles_dir.iterdir()):
        if not folder.is_dir() or folder.name.startswith("."):
            continue
        md = folder / "article.md"
        if not md.is_file():
            continue
        slug = folder.name
        meta, body = parse_md(md)
        media_items: list[dict] = []
        assets = folder / "assets"
        if assets.is_dir():
            for asset in sorted(assets.rglob("*")):
                if not asset.is_file():
                    continue
                rel_name = asset.name
                key = store.object_key("article", slug, rel_name)
                if dry_run:
                    url = cfg.public_media_url(key)
                else:
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
        hero = meta.get("hero") or ""
        hero_name = ""
        if hero:
            hero_name = media_name_from_path(str(hero))
        now = utcnow()
        published_at = parse_when(meta.get("published"), meta.get("date")) or now
        date_str = meta.get("date") or published_at.date().isoformat()
        version = {
            "version": 1,
            "markdown": body,
            "title": meta.get("title") or slug,
            "edited_by": "onboard",
            "edited_at": now,
            "reason": "migrated from articles/ filesystem",
        }
        doc = {
            "slug": slug,
            "title": meta.get("title") or slug,
            "dek": meta.get("dek") or "",
            "author": meta.get("author") or "Staff",
            "date": date_str,
            "section": meta.get("section") or "News",
            "tags": meta.get("tags") or [],
            "disclaimer": meta.get("disclaimer", True),
            "hero": hero_name or hero,
            "markdown": body,
            "media": media_items,
            "agent_source": meta.get("agent_source") or "grok",
            "status": "published",
            "published_at": published_at,
            "created_at": now,
            "updated_at": now,
            "versions": [version],
            "published": meta.get("published") or "",
        }
        if dry_run:
            log.info("[dry-run] article %s media=%d", slug, len(media_items))
        else:
            db.articles.update_one({"slug": slug}, {"$set": doc}, upsert=True)
            log.info("upserted article %s media=%d", slug, len(media_items))
        count += 1
    return count


def onboard_ads(
    cfg: Config,
    store: MediaStore,
    ads_dir: Path,
    *,
    dry_run: bool,
) -> int:
    db = get_db(cfg)
    count = 0
    if not ads_dir.is_dir():
        log.warning("ads dir missing: %s", ads_dir)
        return 0
    for folder in sorted(ads_dir.iterdir()):
        if not folder.is_dir() or folder.name.startswith("."):
            continue
        md = folder / "business.md"
        if not md.is_file():
            continue
        slug = folder.name
        meta, body = parse_md(md)
        media_items: list[dict] = []
        assets = folder / "assets"
        if assets.is_dir():
            for asset in sorted(assets.rglob("*")):
                if not asset.is_file():
                    continue
                rel_name = asset.name
                key = store.object_key("ad", slug, rel_name)
                if dry_run:
                    url = cfg.public_media_url(key)
                else:
                    url = store.upload_file(asset, key)
                media_items.append(
                    {
                        "type": "image",
                        "name": media_name_from_path(rel_name),
                        "filename": rel_name,
                        "key": key,
                        "url": url,
                    }
                )
        now = utcnow()
        doc = {
            "slug": slug,
            "name": meta.get("name") or meta.get("title") or slug,
            "tagline": meta.get("tagline") or meta.get("dek") or "",
            "body": body,
            "markdown": body,
            "cta": meta.get("cta") or "",
            "url": meta.get("url") or meta.get("link") or "#",
            "logo": meta.get("logo") or "logo",
            "image": meta.get("image") or meta.get("hero") or "hero",
            "hero": meta.get("hero") or "hero",
            "weight": int(meta.get("weight") or 1),
            "active": meta.get("active", True) is not False,
            "media": media_items,
            "created_at": now,
            "updated_at": now,
        }
        if dry_run:
            log.info("[dry-run] ad %s media=%d", slug, len(media_items))
        else:
            db.ads.update_one({"slug": slug}, {"$set": doc}, upsert=True)
            log.info("upserted ad %s media=%d", slug, len(media_items))
        count += 1
    return count


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Onboard articles/ads into Mongo + S3")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--articles-only", action="store_true")
    parser.add_argument("--ads-only", action="store_true")
    parser.add_argument("--articles-dir", type=Path, default=None)
    parser.add_argument("--ads-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    cfg = Config.from_env()
    articles_dir = args.articles_dir or Path(cfg.seed_articles_dir)
    ads_dir = args.ads_dir or Path(cfg.seed_ads_dir)

    # Prefer repo-local paths when running outside docker
    repo_root = Path(__file__).resolve().parents[2]
    if not articles_dir.is_dir() and (repo_root / "articles").is_dir():
        articles_dir = repo_root / "articles"
    if not ads_dir.is_dir() and (repo_root / "ads").is_dir():
        ads_dir = repo_root / "ads"

    store = MediaStore(cfg)
    if not args.dry_run:
        try:
            store.ensure_bucket()
        except Exception as exc:  # noqa: BLE001
            log.warning("ensure_bucket: %s", exc)
        ensure_indexes(get_db(cfg))

    n_art = n_ads = 0
    if not args.ads_only:
        n_art = onboard_articles(cfg, store, articles_dir, dry_run=args.dry_run)
    if not args.articles_only:
        n_ads = onboard_ads(cfg, store, ads_dir, dry_run=args.dry_run)

    log.info("done articles=%d ads=%d dry_run=%s", n_art, n_ads, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
