"""Gcore CDN purge/prime + Spaces CDN media prime.

When credentials are unset, operations are logged stubs (local/dev safe).
"""

from __future__ import annotations

import logging
from typing import Any

import requests

from app.config import Config

log = logging.getLogger(__name__)


class CdnService:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg

    @property
    def gcore_configured(self) -> bool:
        return bool(self.cfg.gcore_api_token and self.cfg.gcore_resource_id)

    def purge_paths(self, paths: list[str]) -> dict[str, Any]:
        """Purge main-site CDN paths (article pages, homepage)."""
        if not paths:
            return {"status": "noop", "reason": "empty paths"}
        if not self.gcore_configured:
            log.info("CDN purge stub (Gcore unset): %s", paths)
            return {"status": "stub", "paths": paths}

        # Gcore CDN API — purge by URL
        # https://api.gcore.com/cdn/resources/{id}/purge
        url = f"https://api.gcore.com/cdn/resources/{self.cfg.gcore_resource_id}/purge"
        headers = {
            "Authorization": f"APIKey {self.cfg.gcore_api_token}",
            "Content-Type": "application/json",
        }
        # Prefer full URLs when base is set
        if self.cfg.gcore_cdn_base_url:
            base = self.cfg.gcore_cdn_base_url.rstrip("/")
            urls = [f"{base}/{p.lstrip('/')}" for p in paths]
            payload: dict[str, Any] = {"urls": urls}
        else:
            payload = {"paths": paths}
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=30)
            log.info("Gcore purge status=%s body=%s", resp.status_code, resp.text[:300])
            return {
                "status": "ok" if resp.ok else "error",
                "http_status": resp.status_code,
                "paths": paths,
            }
        except requests.RequestException as exc:
            log.warning("Gcore purge failed: %s", exc)
            return {"status": "error", "error": str(exc), "paths": paths}

    def prime_urls(self, urls: list[str]) -> dict[str, Any]:
        """Warm CDN / origin by HTTP GET so social crawlers get warm cache."""
        results: list[dict[str, Any]] = []
        for u in urls:
            if not u:
                continue
            try:
                resp = requests.get(
                    u,
                    timeout=20,
                    headers={"User-Agent": "AgentNews-CDN-Primer/1.0"},
                    allow_redirects=True,
                )
                results.append({"url": u, "status": resp.status_code})
                log.info("Prime %s → %s", u, resp.status_code)
            except requests.RequestException as exc:
                results.append({"url": u, "error": str(exc)})
                log.warning("Prime failed %s: %s", u, exc)
        return {"status": "ok", "results": results}

    def after_article_publish(
        self,
        *,
        slug: str,
        article_url: str,
        og_image_url: str | None,
        media_urls: list[str] | None = None,
    ) -> dict[str, Any]:
        purge = self.purge_paths(
            [
                f"/article/{slug}",
                f"/article/{slug}/",
                "/",
                "/api/articles",
                f"/api/articles/{slug}",
            ]
        )
        to_prime = [article_url]
        if og_image_url:
            to_prime.append(og_image_url)
        if self.cfg.spaces_cdn_prime and media_urls:
            to_prime.extend(media_urls)
        prime = self.prime_urls(list(dict.fromkeys(to_prime)))
        return {"purge": purge, "prime": prime}
