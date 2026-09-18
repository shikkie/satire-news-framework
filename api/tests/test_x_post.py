"""X posting + scheduled publish."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.config import Config
from app.db import utcnow
from app.services.publish import publish_due_articles
from app.services.x_post import XPostService, compose_tweet_text


def test_compose_tweet_includes_url_and_fits():
    text = compose_tweet_text("Short headline", "http://bandit:8088/article/foo")
    assert "Short headline" in text
    assert "http://bandit:8088/article/foo" in text
    # URL is counted as 23; keep composed python length generous but headline truncated
    long = "W" * 400
    clipped = compose_tweet_text(long, "http://example.com/article/x")
    assert clipped.endswith("http://example.com/article/x")
    assert "…" in clipped


def test_x_disabled_on_publish(client, admin_session):
    res = client.post(
        "/api/articles",
        headers=admin_session,
        json={
            "slug": "no-x-story",
            "title": "No X",
            "markdown": "body",
            "status": "published",
            "post_to_x": True,
        },
    )
    assert res.status_code == 201, res.get_data(as_text=True)
    x = res.get_json()["x_post"]
    assert x["status"] == "disabled"


def test_x_skipped_when_article_toggle_off(app, client, admin_session):
    object.__setattr__(app.config["APP_CONFIG"], "x_post_enabled", True)

    res = client.post(
        "/api/articles",
        headers=admin_session,
        json={
            "slug": "skip-x-story",
            "title": "Skip X",
            "markdown": "body",
            "status": "published",
            "post_to_x": False,
        },
    )
    assert res.status_code == 201
    assert res.get_json()["x_post"]["status"] == "skipped"


def test_x_stub_when_enabled_without_creds(app, client, admin_session):
    object.__setattr__(app.config["APP_CONFIG"], "x_post_enabled", True)

    res = client.post(
        "/api/articles",
        headers=admin_session,
        json={
            "slug": "stub-x-story",
            "title": "Stub X",
            "markdown": "body",
            "status": "published",
            "post_to_x": True,
        },
    )
    assert res.status_code == 201
    x = res.get_json()["x_post"]
    assert x["status"] == "stub"
    assert "Stub X" in x["text"]

    # Already published: /publish does not tweet again
    again = client.post("/api/articles/stub-x-story/publish", headers=admin_session)
    assert again.get_json()["x_post"]["status"] == "stub"


def test_schedule_then_due_publish_posts_x(app, client, admin_session, db):
    object.__setattr__(app.config["APP_CONFIG"], "x_post_enabled", True)

    past = (utcnow() - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    future = (utcnow() + timedelta(days=1)).isoformat().replace("+00:00", "Z")

    waiting = client.post(
        "/api/articles",
        headers=admin_session,
        json={
            "slug": "sched-future",
            "title": "Later",
            "markdown": "wait",
            "status": "scheduled",
            "scheduled_at": future,
            "post_to_x": True,
        },
    )
    assert waiting.status_code == 201, waiting.get_data(as_text=True)
    assert waiting.get_json()["article"]["status"] == "scheduled"
    assert waiting.get_json()["x_post"] is None

    due = client.post(
        "/api/articles",
        headers=admin_session,
        json={
            "slug": "sched-due",
            "title": "Due now",
            "markdown": "go",
            "status": "scheduled",
            "scheduled_at": past,
            "post_to_x": True,
        },
    )
    # Past scheduled_at is treated as immediate publish
    assert due.status_code == 201
    assert due.get_json()["article"]["status"] == "published"
    assert due.get_json()["x_post"]["status"] == "stub"

    # Explicit future item is still scheduled until the due tick
    public = client.get("/api/articles")
    slugs = [a["slug"] for a in public.get_json()["articles"]]
    assert "sched-future" not in slugs

    # Force the future one due in Mongo, then tick
    db.articles.update_one(
        {"slug": "sched-future"},
        {"$set": {"scheduled_at": datetime(2020, 1, 1, tzinfo=UTC)}},
    )
    tick = client.post("/api/articles/admin/publish-due", headers=admin_session)
    assert tick.status_code == 200
    body = tick.get_json()
    assert body["count"] >= 1
    slugs = [p["slug"] for p in body["published"]]
    assert "sched-future" in slugs
    got = client.get("/api/articles/sched-future")
    assert got.status_code == 200
    assert got.get_json()["status"] == "published"


def test_settings_flags(client, admin_session):
    res = client.get("/api/settings", headers=admin_session)
    assert res.status_code == 200
    data = res.get_json()
    assert data["x_post_enabled"] is False
    assert data["x_post_configured"] is False
    assert "scheduler_enabled" in data


def test_x_configured_property():
    cfg = Config(
        x_post_enabled=True,
        x_api_key="k",
        x_api_secret="s",
        x_access_token="t",
        x_access_token_secret="ts",
    )
    assert XPostService(cfg).configured is True
    cfg2 = Config(x_post_enabled=True, x_api_key="k")
    assert XPostService(cfg2).configured is False


def test_publish_due_empty(db):
    cfg = Config(scheduler_enabled=False, x_post_enabled=False)
    assert publish_due_articles(cfg, db) == []
