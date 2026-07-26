"""First-boot admin user seed."""

from __future__ import annotations

import logging

from pymongo.database import Database

from app.config import Config
from app.db import utcnow
from app.services.passwords import hash_password

log = logging.getLogger(__name__)


def ensure_bootstrap_admin(db: Database, cfg: Config) -> None:
    if db.users.count_documents({}) > 0:
        return
    username = (cfg.admin_username or "admin").strip().lower()
    password = cfg.admin_password
    if not password or password == "change-me-admin-password":
        log.warning(
            "Creating bootstrap admin %r with default/weak password — "
            "set ADMIN_PASSWORD in production",
            username,
        )
    now = utcnow()
    db.users.insert_one(
        {
            "username": username,
            "password_hash": hash_password(password),
            "role": "admin",
            "created_at": now,
            "updated_at": now,
            "active": True,
        }
    )
    log.info("Bootstrap admin user created: %s", username)
