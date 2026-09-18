"""CMS generate-from-prompt endpoint."""

from app.services.acp_grok import format_acp_event
from app.services.generate import compose_generate_brief


def test_format_acp_event_tool_line():
    line = format_acp_event("tool", "articles/x/article.md", {"name": "write", "status": "completed"})
    assert "write" in line
    assert "completed" in line


def test_compose_brief_includes_slug_and_prompt():
    text = compose_generate_brief("my-slug", "Kitten calls 911.")
    assert "my-slug" in text
    assert "Kitten calls 911." in text
    assert "satire-news-cms-article-generator" in text
    assert "Do not git commit" in text
    invent = compose_generate_brief(
        "draft-abcd1234",
        "Kitten calls 911.",
        invent_slug=True,
        taken_slugs=["existing-slug"],
    )
    assert "Invent a unique kebab-case slug" in invent
    assert "existing-slug" in invent


def test_generate_requires_prompt(client, admin_session):
    client.post(
        "/api/articles",
        headers=admin_session,
        json={"slug": "empty-prompt", "title": "T", "status": "draft"},
    )
    res = client.post("/api/articles/empty-prompt/generate", headers=admin_session, json={})
    assert res.status_code == 400


def test_generate_not_configured(client, admin_session):
    client.post(
        "/api/articles",
        headers=admin_session,
        json={
            "slug": "has-prompt",
            "title": "T",
            "status": "draft",
            "creation_prompt": "A brief.",
        },
    )
    res = client.post(
        "/api/articles/has-prompt/generate",
        headers=admin_session,
        json={"creation_prompt": "A brief."},
    )
    assert res.status_code == 503


def test_generate_starts_job(app, client, admin_session, monkeypatch, tmp_path):
    grok = tmp_path / "grok"
    grok.write_text("#!/bin/sh\nexit 0\n")
    grok.chmod(0o755)
    object.__setattr__(app.config["APP_CONFIG"], "grok_bin", str(grok))
    called = {}

    def fake_start(_app, slug):
        called["slug"] = slug

    monkeypatch.setattr("app.routes.articles.start_generate", fake_start)
    client.post(
        "/api/articles",
        headers=admin_session,
        json={
            "slug": "gen-me",
            "title": "T",
            "status": "draft",
            "creation_prompt": "Write the bit.",
        },
    )
    res = client.post(
        "/api/articles/gen-me/generate",
        headers=admin_session,
        json={"creation_prompt": "Write the bit."},
    )
    assert res.status_code == 202, res.get_data(as_text=True)
    assert called["slug"] == "gen-me"
    assert res.get_json()["article"]["generation"]["status"] == "running"


def test_generate_without_slug_creates_placeholder(app, client, admin_session, monkeypatch, tmp_path):
    grok = tmp_path / "grok"
    grok.write_text("#!/bin/sh\nexit 0\n")
    grok.chmod(0o755)
    object.__setattr__(app.config["APP_CONFIG"], "grok_bin", str(grok))
    monkeypatch.setattr("app.routes.articles.start_generate", lambda *_a, **_k: None)
    res = client.post(
        "/api/articles/generate",
        headers=admin_session,
        json={"creation_prompt": "City bans spoons."},
    )
    assert res.status_code == 202, res.get_data(as_text=True)
    art = res.get_json()["article"]
    assert art["slug"].startswith("draft-")
    assert art["placeholder"] is True
    assert art["generation"]["status"] == "running"
