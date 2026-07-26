"""Auth and session idle TTL tests."""

from __future__ import annotations

from datetime import timedelta

from app.db import utcnow
from freezegun import freeze_time


def test_login_logout_me(client, admin_session):
    me = client.get("/api/auth/me", headers=admin_session)
    assert me.status_code == 200
    assert me.get_json()["username"] == "admin"
    assert me.get_json()["role"] == "admin"

    out = client.post("/api/auth/logout", headers=admin_session)
    assert out.status_code == 200
    me2 = client.get("/api/auth/me", headers=admin_session)
    assert me2.status_code == 401


def test_bad_login(client):
    res = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "wrong"},
    )
    assert res.status_code == 401


def test_session_idle_expiry(client, db, cfg, admin_session):
    # Force last_seen_at into the past
    sid = admin_session["X-Session-Id"]
    old = utcnow() - timedelta(minutes=cfg.session_idle_minutes + 1)
    db.sessions.update_one({"session_id": sid}, {"$set": {"last_seen_at": old}})
    res = client.get("/api/auth/me", headers=admin_session)
    assert res.status_code == 401


def test_session_idle_resets(client):
    # Login must happen inside freeze_time so last_seen_at matches frozen clock
    with freeze_time("2026-07-26 12:00:00") as frozen:
        login = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "test-admin-pass"},
        )
        assert login.status_code == 200
        headers = {"X-Session-Id": login.get_json()["session_id"]}
        r1 = client.get("/api/auth/me", headers=headers)
        assert r1.status_code == 200
        frozen.tick(timedelta(minutes=10))
        r2 = client.get("/api/auth/me", headers=headers)
        assert r2.status_code == 200
        frozen.tick(timedelta(minutes=10))
        # another touch within idle window after previous reset
        r3 = client.get("/api/auth/me", headers=headers)
        assert r3.status_code == 200
        frozen.tick(timedelta(minutes=16))
        r4 = client.get("/api/auth/me", headers=headers)
        assert r4.status_code == 401


def test_api_cache_control(client):
    res = client.get("/api/health")
    assert res.headers.get("Cache-Control") == "no-store"


def test_admin_sessions_list(client, admin_session):
    res = client.get("/api/auth/sessions", headers=admin_session)
    assert res.status_code == 200
    data = res.get_json()
    assert data["count"] >= 1
    assert data["sessions"][0]["username"] == "admin"
