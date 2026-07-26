"""Article CRUD, publish, versions, public visibility."""

from __future__ import annotations


def test_create_list_get_publish(client, admin_session):
    create = client.post(
        "/api/articles",
        headers=admin_session,
        json={
            "slug": "test-story",
            "title": "Test Story",
            "dek": "A dek",
            "author": "Unit Test",
            "section": "Local",
            "markdown": "Hello **world**",
            "status": "draft",
            "media": [
                {
                    "type": "image",
                    "name": "hero",
                    "url": "http://assets.agentnews.local/agentnews-media/article/test-story/hero.jpg",
                    "key": "article/test-story/hero.jpg",
                }
            ],
            "hero": "hero",
        },
    )
    assert create.status_code == 201, create.get_data(as_text=True)
    body = create.get_json()["article"]
    assert body["slug"] == "test-story"
    assert body["status"] == "draft"
    assert len(body["versions"]) == 1

    # Public list hides drafts
    pub = client.get("/api/articles")
    assert pub.status_code == 200
    assert all(a["slug"] != "test-story" for a in pub.get_json()["articles"])

    # Admin list shows
    admin_list = client.get("/api/articles/admin", headers=admin_session)
    assert any(a["slug"] == "test-story" for a in admin_list.get_json()["articles"])

    # Publish
    pub_res = client.post("/api/articles/test-story/publish", headers=admin_session)
    assert pub_res.status_code == 200
    assert pub_res.get_json()["article"]["status"] == "published"
    assert pub_res.get_json()["cdn"]["purge"]["status"] == "stub"

    got = client.get("/api/articles/test-story")
    assert got.status_code == 200
    assert "Hello **world**" in got.get_json()["body"]
    assert got.get_json()["hero"].startswith("http")


def test_version_history_on_edit(client, admin_session):
    client.post(
        "/api/articles",
        headers=admin_session,
        json={
            "slug": "ver-story",
            "title": "V1",
            "markdown": "one",
            "status": "draft",
        },
    )
    upd = client.put(
        "/api/articles/ver-story",
        headers=admin_session,
        json={"markdown": "two", "title": "V2", "reason": "rewrite"},
    )
    assert upd.status_code == 200
    versions = upd.get_json()["article"]["versions"]
    assert len(versions) == 2
    assert versions[-1]["reason"] == "rewrite"
    assert versions[-1]["markdown"] == "two"

    hist = client.get("/api/articles/ver-story/versions", headers=admin_session)
    assert hist.status_code == 200
    assert len(hist.get_json()["versions"]) == 2


def test_editor_cannot_list_users(client, db, admin_session):
    # Create editor
    from app.db import utcnow
    from app.services.passwords import hash_password

    db.users.insert_one(
        {
            "username": "ed",
            "password_hash": hash_password("ed-pass-123"),
            "role": "editor",
            "active": True,
            "created_at": utcnow(),
            "updated_at": utcnow(),
        }
    )
    login = client.post("/api/auth/login", json={"username": "ed", "password": "ed-pass-123"})
    headers = {"X-Session-Id": login.get_json()["session_id"]}
    # Editor can create articles
    res = client.post(
        "/api/articles",
        headers=headers,
        json={"slug": "ed-story", "title": "Ed", "markdown": "x", "status": "draft"},
    )
    assert res.status_code == 201
    # Editor cannot list users
    users = client.get("/api/users", headers=headers)
    assert users.status_code == 403
