"""Admin user management."""

from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from app.auth import get_config, require_admin
from app.db import get_db, utcnow
from app.services.passwords import hash_password
from app.services.sessions import VALID_ROLES

bp = Blueprint("users", __name__, url_prefix="/api/users")


@bp.get("")
@require_admin
def list_users():  # type: ignore[no-untyped-def]
    cfg = get_config()
    db = get_db(cfg)
    users = []
    for u in db.users.find().sort("username", 1):
        users.append(
            {
                "username": u.get("username"),
                "role": u.get("role"),
                "active": u.get("active", True),
                "created_at": u["created_at"].isoformat() if u.get("created_at") else None,
            }
        )
    return jsonify({"users": users})


@bp.post("")
@require_admin
def create_user():  # type: ignore[no-untyped-def]
    cfg = get_config()
    db = get_db(cfg)
    data = request.get_json(silent=True) or {}
    username = str(data.get("username") or "").strip().lower()
    password = str(data.get("password") or "")
    role = str(data.get("role") or "editor").strip().lower()
    if not username or not password:
        return jsonify({"error": "bad_request", "message": "username and password required"}), 400
    if role not in VALID_ROLES:
        return jsonify(
            {
                "error": "bad_request",
                "message": f"role must be one of {sorted(VALID_ROLES)}",
            }
        ), 400
    if db.users.find_one({"username": username}):
        return jsonify({"error": "conflict", "message": "username exists"}), 409
    now = utcnow()
    db.users.insert_one(
        {
            "username": username,
            "password_hash": hash_password(password),
            "role": role,
            "active": True,
            "created_at": now,
            "updated_at": now,
            "created_by": g.username,
        }
    )
    return jsonify({"username": username, "role": role}), 201


@bp.patch("/<username>")
@require_admin
def patch_user(username: str):  # type: ignore[no-untyped-def]
    cfg = get_config()
    db = get_db(cfg)
    username = username.strip().lower()
    user = db.users.find_one({"username": username})
    if not user:
        return jsonify({"error": "not_found"}), 404
    data = request.get_json(silent=True) or {}
    updates: dict = {"updated_at": utcnow()}
    if "role" in data:
        role = str(data["role"]).strip().lower()
        if role not in VALID_ROLES:
            return jsonify({"error": "bad_request", "message": "invalid role"}), 400
        updates["role"] = role
    if "active" in data:
        updates["active"] = bool(data["active"])
    if "password" in data and data["password"]:
        updates["password_hash"] = hash_password(str(data["password"]))
    db.users.update_one({"username": username}, {"$set": updates})
    return jsonify({"username": username, "ok": True})
