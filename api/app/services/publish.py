"""Publish side effects: CDN purge/prime + optional X post.

X posting runs only on the first transition to published (manual or scheduler).
"""

from __future__ import annotations

import logging
from typing import Any

from pymongo import ReturnDocument
from pymongo.database import Database

from app.config import Config
from app.db import utcnow
from app.services.articles import serialize_article
from app.services.cdn import CdnService
from app.services.x_post import XPostService

log = logging.getLogger(__name__)


def run_cdn(cfg: Config, doc: dict[str, Any]) -> dict[str, Any]:
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


def run_x_post(cfg: Config, db: Database, doc: dict[str, Any]) -> dict[str, Any]:
    result = XPostService(cfg).maybe_post_article(doc)
    db.articles.update_one({"slug": doc["slug"]}, {"$set": {"x_post": result}})
    return result


def after_publish(
    cfg: Config,
    db: Database,
    doc: dict[str, Any],
    *,
    newly_published: bool,
) -> dict[str, Any]:
    """CDN on every published save; X post only the first time it goes live."""
    out: dict[str, Any] = {"cdn": run_cdn(cfg, doc), "x_post": None}
    if newly_published:
        out["x_post"] = run_x_post(cfg, db, doc)
    elif doc.get("x_post"):
        out["x_post"] = doc.get("x_post")
    return out


def publish_due_articles(cfg: Config, db: Database, *, limit: int = 20) -> list[dict[str, Any]]:
    """Claim due scheduled articles and run publish side effects."""
    now = utcnow()
    done: list[dict[str, Any]] = []
    for _ in range(max(1, min(limit, 100))):
        doc = db.articles.find_one_and_update(
            {"status": "scheduled", "scheduled_at": {"$lte": now}},
            {
                "$set": {
                    "status": "published",
                    "published_at": now,
                    "updated_at": now,
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        if not doc:
            break
        if not doc.get("date"):
            db.articles.update_one(
                {"slug": doc["slug"]},
                {"$set": {"date": now.date().isoformat()}},
            )
            doc["date"] = now.date().isoformat()
        log.info("Scheduled publish due: %s", doc.get("slug"))
        side = after_publish(cfg, db, doc, newly_published=True)
        done.append({"slug": doc["slug"], **side})
    return done
