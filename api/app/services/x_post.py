"""Post a published article to X (Twitter).

Master switch: Config.x_post_enabled.
Per-article: article.post_to_x (default True).
Missing credentials → stub/log, same pattern as Gcore CDN.
"""

from __future__ import annotations

import logging
from typing import Any

import requests

from app.config import Config
from app.db import utcnow
from app.services.articles import serialize_article

log = logging.getLogger(__name__)

# X counts a URL as a t.co wrap (23) regardless of length.
TCO_URL_LENGTH = 23
TWEET_MAX = 280


def compose_tweet_text(title: str, url: str) -> str:
    """Headline + blank line + article URL, within 280 (URL = 23)."""
    link = (url or "").strip()
    headline = (title or "Agent News").strip() or "Agent News"
    # "\n\n" + t.co URL
    budget = TWEET_MAX - (2 + TCO_URL_LENGTH)
    if len(headline) > budget:
        headline = headline[: max(0, budget - 1)].rstrip() + "…"
    if link:
        return f"{headline}\n\n{link}"
    return headline[:TWEET_MAX]


class XPostService:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg

    @property
    def configured(self) -> bool:
        return bool(
            self.cfg.x_api_key
            and self.cfg.x_api_secret
            and self.cfg.x_access_token
            and self.cfg.x_access_token_secret
        )

    def maybe_post_article(self, doc: dict[str, Any]) -> dict[str, Any]:
        """Post once on first publish. Never fails the publish pipeline."""
        existing = doc.get("x_post") or {}
        if existing.get("id"):
            return {**existing, "status": "already_posted"}
        if not self.cfg.x_post_enabled:
            return {"status": "disabled", "reason": "X_POST_ENABLED is off"}
        if not doc.get("post_to_x", True):
            return {"status": "skipped", "reason": "post_to_x is false"}

        ser = serialize_article(doc, include_body=False)
        url = self.cfg.article_page_url(doc["slug"])
        text = compose_tweet_text(ser.get("title") or doc.get("slug") or "", url)

        if not self.configured:
            log.info("X post stub (credentials unset): slug=%s text=%s", doc.get("slug"), text)
            return {
                "status": "stub",
                "text": text,
                "url": url,
                "posted_at": utcnow(),
            }
        return self._post_tweet(text)

    def _post_tweet(self, text: str) -> dict[str, Any]:
        try:
            from requests_oauthlib import OAuth1
        except ImportError:
            log.warning("requests-oauthlib missing; cannot post to X")
            return {"status": "error", "error": "requests-oauthlib not installed"}

        auth = OAuth1(
            self.cfg.x_api_key,
            self.cfg.x_api_secret,
            self.cfg.x_access_token,
            self.cfg.x_access_token_secret,
        )
        endpoint = f"{self.cfg.x_api_base.rstrip('/')}/2/tweets"
        try:
            resp = requests.post(
                endpoint,
                json={"text": text},
                auth=auth,
                timeout=30,
            )
        except requests.RequestException as exc:
            log.warning("X post failed: %s", exc)
            return {"status": "error", "error": str(exc), "text": text}

        body: dict[str, Any] = {}
        try:
            body = resp.json() if resp.content else {}
        except ValueError:
            body = {"raw": resp.text[:500]}

        if not resp.ok:
            log.warning("X post HTTP %s: %s", resp.status_code, str(body)[:300])
            return {
                "status": "error",
                "http_status": resp.status_code,
                "error": str(body)[:500],
                "text": text,
            }

        tweet_id = ""
        data = body.get("data") if isinstance(body, dict) else None
        if isinstance(data, dict):
            tweet_id = str(data.get("id") or "")
        tweet_url = f"https://x.com/i/web/status/{tweet_id}" if tweet_id else ""
        log.info("X post ok id=%s", tweet_id)
        return {
            "status": "ok",
            "id": tweet_id,
            "url": tweet_url,
            "text": text,
            "posted_at": utcnow(),
        }
