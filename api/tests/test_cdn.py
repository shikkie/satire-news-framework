"""CDN service stubs."""

from app.config import Config
from app.services.cdn import CdnService


def test_purge_stub_without_credentials():
    cfg = Config(gcore_api_token="", gcore_resource_id="")
    svc = CdnService(cfg)
    result = svc.purge_paths(["/article/foo"])
    assert result["status"] == "stub"


def test_after_publish_structure(monkeypatch):
    cfg = Config(gcore_api_token="", gcore_resource_id="", spaces_cdn_prime=False)
    svc = CdnService(cfg)

    def fake_prime(urls):
        return {"status": "ok", "results": [{"url": u, "status": 200} for u in urls]}

    monkeypatch.setattr(svc, "prime_urls", fake_prime)
    out = svc.after_article_publish(
        slug="foo",
        article_url="http://agentnews.local/article/foo",
        og_image_url="http://assets/x.jpg",
        media_urls=["http://assets/x.jpg"],
    )
    assert out["purge"]["status"] == "stub"
    assert out["prime"]["status"] == "ok"
