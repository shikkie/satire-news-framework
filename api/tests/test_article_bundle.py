"""Article JSON bundle export / import (base64 assets)."""

from __future__ import annotations

import base64
from pathlib import Path


class FakeMediaStore:
    objects: dict[str, bytes] = {}

    def __init__(self, cfg=None):  # noqa: ARG002
        self.cfg = cfg

    def ensure_bucket(self) -> None:
        return None

    def object_key(self, kind: str, slug: str, filename: str) -> str:
        return f"{kind}/{slug}/{Path(filename).name}"

    def public_url(self, key: str) -> str:
        return f"http://assets.agentnews.local/agentnews-media/{key}"

    def upload_bytes(self, data, key, *, content_type="application/octet-stream", **_kw):  # noqa: ARG002
        body = data if isinstance(data, (bytes, bytearray)) else data.read()
        self.objects[key] = bytes(body)
        return self.public_url(key)

    def get_bytes(self, key: str) -> bytes:
        if key not in self.objects:
            raise FileNotFoundError(key)
        return self.objects[key]


def _png_bytes() -> bytes:
    # 1x1 PNG
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )


def test_export_requires_auth(client):
    res = client.get("/api/articles/nope/export")
    assert res.status_code == 401


def test_export_import_roundtrip(client, admin_session, monkeypatch):
    FakeMediaStore.objects = {}
    monkeypatch.setattr("app.services.article_bundle.MediaStore", FakeMediaStore)
    png = _png_bytes()
    FakeMediaStore.objects["article/bundle-story/hero.png"] = png

    created = client.post(
        "/api/articles",
        headers=admin_session,
        json={
            "slug": "bundle-story",
            "title": "Bundle Story",
            "dek": "A portable tale",
            "author": "Exporter",
            "section": "Tech",
            "markdown": "See ![hero](assets/hero.png)",
            "status": "draft",
            "creation_prompt": "Write a portable story.",
            "hero": "hero",
            "tags": ["portable"],
            "media": [
                {
                    "type": "image",
                    "name": "hero",
                    "filename": "hero.png",
                    "key": "article/bundle-story/hero.png",
                    "url": "http://assets.agentnews.local/agentnews-media/article/bundle-story/hero.png",
                }
            ],
        },
    )
    assert created.status_code == 201, created.get_data(as_text=True)

    exported = client.get("/api/articles/bundle-story/export", headers=admin_session)
    assert exported.status_code == 200, exported.get_data(as_text=True)
    bundle = exported.get_json()
    assert bundle["format"] == "agentnews.article.v1"
    assert bundle["article"]["slug"] == "bundle-story"
    assert bundle["article"]["markdown"].startswith("See ")
    assert bundle["article"]["creation_prompt"] == "Write a portable story."
    assert len(bundle["assets"]) == 1
    assert bundle["assets"][0]["filename"] == "hero.png"
    assert base64.b64decode(bundle["assets"][0]["data"]) == png

    # Import to a new slug via wrapper object
    bundle["article"]["slug"] = "bundle-story-copy"
    imported = client.post(
        "/api/articles/import",
        headers=admin_session,
        json={"bundle": bundle, "as_draft": True},
    )
    assert imported.status_code == 201, imported.get_data(as_text=True)
    copy = imported.get_json()["article"]
    assert copy["slug"] == "bundle-story-copy"
    assert copy["status"] == "draft"
    assert copy["title"] == "Bundle Story"
    assert len(copy["media"]) == 1
    assert copy["media"][0]["filename"] == "hero.png"
    assert "bundle-story-copy" in copy["media"][0]["key"]
    assert FakeMediaStore.objects[copy["media"][0]["key"]] == png

    conflict = client.post(
        "/api/articles/import",
        headers=admin_session,
        json=bundle,
    )
    assert conflict.status_code == 409

    bundle["article"]["title"] = "Bundle Story (overwritten)"
    again = client.post(
        "/api/articles/import",
        headers=admin_session,
        json={"bundle": bundle, "overwrite": True, "as_draft": True},
    )
    assert again.status_code == 200, again.get_data(as_text=True)
    assert again.get_json()["article"]["title"] == "Bundle Story (overwritten)"


def test_import_raw_bundle_json(client, admin_session, monkeypatch):
    FakeMediaStore.objects = {}
    monkeypatch.setattr("app.services.article_bundle.MediaStore", FakeMediaStore)
    res = client.post(
        "/api/articles/import",
        headers=admin_session,
        json={
            "format": "agentnews.article.v1",
            "article": {
                "slug": "pasted-story",
                "title": "Pasted",
                "markdown": "Hello from paste.",
                "section": "Local",
                "creation_prompt": "paste me",
            },
            "assets": [],
        },
    )
    assert res.status_code == 201, res.get_data(as_text=True)
    art = res.get_json()["article"]
    assert art["slug"] == "pasted-story"
    assert art["markdown"] == "Hello from paste."
    assert art["status"] == "draft"
