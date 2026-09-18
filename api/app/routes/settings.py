"""Editor-visible feature flags (X post, scheduler)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from app.auth import get_config, require_editor_or_admin
from app.services.generate import generate_configured
from app.services.x_post import XPostService

bp = Blueprint("settings", __name__, url_prefix="/api")


@bp.get("/settings")
@require_editor_or_admin
def settings():  # type: ignore[no-untyped-def]
    cfg = get_config()
    x = XPostService(cfg)
    return jsonify(
        {
            "x_post_enabled": cfg.x_post_enabled,
            "x_post_configured": x.configured,
            "scheduler_enabled": cfg.scheduler_enabled,
            "scheduler_poll_seconds": cfg.scheduler_poll_seconds,
            "generate_configured": generate_configured(cfg),
        }
    )
