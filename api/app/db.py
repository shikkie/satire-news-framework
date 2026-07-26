"""MongoDB helpers."""

from __future__ import annotations

from datetime import UTC
from typing import Any

from pymongo import ASCENDING, DESCENDING, TEXT, MongoClient
from pymongo.database import Database

from app.config import Config

_client: MongoClient | None = None
_override_db: Database | None = None


def set_db_override(db: Database | None) -> None:
    """Tests inject mongomock Database here."""
    global _override_db
    _override_db = db


def get_client(cfg: Config) -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(cfg.mongo_uri, serverSelectionTimeoutMS=5000)
    return _client


def get_db(cfg: Config | None = None) -> Database:
    if _override_db is not None:
        return _override_db
    if cfg is None:
        cfg = Config.from_env()
    return get_client(cfg)[cfg.mongo_db]


def ping_mongo(cfg: Config) -> bool:
    if _override_db is not None:
        return True
    try:
        get_client(cfg).admin.command("ping")
        return True
    except Exception:  # noqa: BLE001
        return False


def ensure_indexes(db: Database) -> None:
    db.users.create_index("username", unique=True)
    db.sessions.create_index("session_id", unique=True)
    db.sessions.create_index("last_seen_at")
    db.articles.create_index("slug", unique=True)
    db.articles.create_index([("status", ASCENDING), ("published_at", DESCENDING)])
    db.articles.create_index([("created_at", DESCENDING)])
    db.articles.create_index([("updated_at", DESCENDING)])
    # Text index for search
    try:
        db.articles.create_index(
            [
                ("title", TEXT),
                ("dek", TEXT),
                ("markdown", TEXT),
                ("author", TEXT),
                ("tags", TEXT),
            ],
            name="article_text",
            default_language="english",
        )
    except Exception:  # noqa: BLE001 — mongomock / reindex races
        # Text index optional under mongomock; regex search still works.
        import logging

        logging.getLogger(__name__).debug("article text index skipped", exc_info=True)
    db.ads.create_index("slug", unique=True)
    db.ads.create_index("active")


def utcnow() -> Any:
    from datetime import datetime

    return datetime.now(UTC)
