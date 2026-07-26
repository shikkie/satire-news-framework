"""Pytest fixtures — mongomock DB, Flask test client."""

from __future__ import annotations

import sys
from pathlib import Path

import mongomock
import pytest

# api/ on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from app.config import Config  # noqa: E402
from app.db import ensure_indexes, set_db_override  # noqa: E402
from app.services.bootstrap import ensure_bootstrap_admin  # noqa: E402


@pytest.fixture()
def cfg() -> Config:
    return Config(
        site_domain="agentnews.local",
        assets_domain="assets.agentnews.local",
        site_url="http://agentnews.local",
        assets_url="http://assets.agentnews.local",
        secret_key="test-secret",
        admin_username="admin",
        admin_password="test-admin-pass",
        mongo_uri="mongodb://localhost",
        mongo_db="agentnews_test",
        media_public_base_url="http://assets.agentnews.local/agentnews-media",
        session_idle_minutes=15,
        gcore_api_token="",
        gcore_resource_id="",
        static_dir=str(Path(__file__).parent / "fixtures_static"),
    )


@pytest.fixture()
def db(cfg: Config):
    client = mongomock.MongoClient()
    database = client[cfg.mongo_db]
    set_db_override(database)
    ensure_indexes(database)
    ensure_bootstrap_admin(database, cfg)
    yield database
    set_db_override(None)


@pytest.fixture()
def app(cfg: Config, db):  # noqa: ARG001
    application = create_app(cfg)
    application.config["TESTING"] = True
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def admin_session(client):
    res = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "test-admin-pass"},
    )
    assert res.status_code == 200, res.get_data(as_text=True)
    sid = res.get_json()["session_id"]
    return {"X-Session-Id": sid}
