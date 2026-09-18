"""Mongo-backed sessions with idle TTL."""

from __future__ import annotations

import secrets
from datetime import UTC, timedelta
from typing import Any

from pymongo.database import Database

from app.config import Config
from app.db import utcnow

ROLE_ADMIN = "admin"
ROLE_EDITOR = "editor"
VALID_ROLES = frozenset({ROLE_ADMIN, ROLE_EDITOR})


def create_session(db: Database, user: dict[str, Any], cfg: Config) -> str:
    session_id = secrets.token_urlsafe(32)
    now = utcnow()
    db.sessions.insert_one(
        {
            "session_id": session_id,
            "user_id": user["_id"],
            "username": user["username"],
            "role": user.get("role") or ROLE_EDITOR,
            "created_at": now,
            "last_seen_at": now,
        }
    )
    return session_id


def touch_session(db: Database, session_id: str, cfg: Config) -> dict[str, Any] | None:
    """Validate idle TTL, extend last_seen_at, return session doc or None."""
    doc = db.sessions.find_one({"session_id": session_id})
    if not doc:
        return None
    last = doc.get("last_seen_at")
    if last is None:
        return None
    # Normalize naive datetimes from mongomock
    now = utcnow()
    if getattr(last, "tzinfo", None) is None:

        last = last.replace(tzinfo=UTC)
    idle = timedelta(minutes=cfg.session_idle_minutes)
    if now - last > idle:
        db.sessions.delete_one({"session_id": session_id})
        return None
    db.sessions.update_one(
        {"session_id": session_id},
        {"$set": {"last_seen_at": now}},
    )
    doc["last_seen_at"] = now
    return doc


def destroy_session(db: Database, session_id: str) -> bool:
    result = db.sessions.delete_one({"session_id": session_id})
    return result.deleted_count > 0


def list_active_sessions(db: Database, cfg: Config) -> list[dict[str, Any]]:
    """Return non-expired sessions; purge expired as a side effect."""
    now = utcnow()
    idle = timedelta(minutes=cfg.session_idle_minutes)
    out: list[dict[str, Any]] = []
    for doc in db.sessions.find().sort("last_seen_at", -1):
        last = doc.get("last_seen_at")
        if last is None:
            continue
        if getattr(last, "tzinfo", None) is None:

            last = last.replace(tzinfo=UTC)
        if now - last > idle:
            db.sessions.delete_one({"_id": doc["_id"]})
            continue
        out.append(
            {
                "session_id": doc["session_id"],
                "username": doc.get("username"),
                "role": doc.get("role"),
                "created_at": doc.get("created_at"),
                "last_seen_at": doc.get("last_seen_at"),
            }
        )
    return out
