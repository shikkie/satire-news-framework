"""Auth helpers / decorators."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from flask import current_app, g, jsonify, request

from app.config import Config
from app.db import get_db
from app.services.sessions import ROLE_ADMIN, touch_session

F = TypeVar("F", bound=Callable[..., Any])


def get_config() -> Config:
    return current_app.config["APP_CONFIG"]


def session_id_from_request() -> str | None:
    cfg = get_config()
    header = request.headers.get(cfg.session_header) or request.headers.get(
        cfg.session_header.lower()
    )
    if header:
        return header.strip()
    # Also accept Authorization: Session <id>
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("session "):
        return auth[8:].strip()
    return None


def load_session() -> dict[str, Any] | None:
    sid = session_id_from_request()
    if not sid:
        return None
    cfg = get_config()
    db = get_db(cfg)
    return touch_session(db, sid, cfg)


def require_auth(*roles: str) -> Callable[[F], F]:
    """Require valid session; optional role allow-list."""

    def decorator(fn: F) -> F:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any):
            sess = load_session()
            if not sess:
                return jsonify({"error": "unauthorized", "message": "login required"}), 401
            if roles and sess.get("role") not in roles:
                return jsonify({"error": "forbidden", "message": "insufficient role"}), 403
            g.session = sess
            g.username = sess.get("username")
            g.role = sess.get("role")
            return fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def require_admin[F: Callable[..., Any]](fn: F) -> F:
    return require_auth(ROLE_ADMIN)(fn)


def require_editor_or_admin[F: Callable[..., Any]](fn: F) -> F:
    return require_auth(ROLE_ADMIN, "editor")(fn)
