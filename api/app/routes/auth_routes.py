"""Login / logout / me / active sessions."""

from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from app.auth import get_config, require_admin, require_editor_or_admin, session_id_from_request
from app.db import get_db
from app.services.passwords import verify_password
from app.services.sessions import (
    create_session,
    destroy_session,
    list_active_sessions,
)

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.post("/login")
def login():  # type: ignore[no-untyped-def]
    cfg = get_config()
    db = get_db(cfg)
    data = request.get_json(silent=True) or {}
    username = str(data.get("username") or "").strip().lower()
    password = str(data.get("password") or "")
    if not username or not password:
        return jsonify({"error": "bad_request", "message": "username and password required"}), 400
    user = db.users.find_one({"username": username, "active": {"$ne": False}})
    if not user or not verify_password(password, user.get("password_hash") or ""):
        return jsonify({"error": "unauthorized", "message": "invalid credentials"}), 401
    sid = create_session(db, user, cfg)
    return jsonify(
        {
            "session_id": sid,
            "username": user["username"],
            "role": user.get("role"),
            "idle_minutes": cfg.session_idle_minutes,
        }
    )


@bp.post("/logout")
def logout():  # type: ignore[no-untyped-def]
    cfg = get_config()
    db = get_db(cfg)
    sid = session_id_from_request()
    if sid:
        destroy_session(db, sid)
    return jsonify({"ok": True})


@bp.get("/me")
@require_editor_or_admin
def me():  # type: ignore[no-untyped-def]
    return jsonify(
        {
            "username": g.username,
            "role": g.role,
            "session_id": g.session.get("session_id"),
            "last_seen_at": g.session.get("last_seen_at").isoformat()
            if g.session.get("last_seen_at")
            else None,
        }
    )


@bp.get("/sessions")
@require_admin
def active_sessions():  # type: ignore[no-untyped-def]
    cfg = get_config()
    db = get_db(cfg)
    sessions = list_active_sessions(db, cfg)
    # Redact full session ids for list? Spec wants to see logged-in users —
    # return truncated id + username
    safe = []
    for s in sessions:
        sid = s.get("session_id") or ""
        safe.append(
            {
                "session_id_prefix": sid[:8] + "…" if len(sid) > 8 else sid,
                "username": s.get("username"),
                "role": s.get("role"),
                "created_at": s["created_at"].isoformat() if s.get("created_at") else None,
                "last_seen_at": s["last_seen_at"].isoformat() if s.get("last_seen_at") else None,
            }
        )
    return jsonify({"sessions": safe, "count": len(safe)})
