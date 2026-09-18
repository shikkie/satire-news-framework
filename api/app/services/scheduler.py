"""Background poller: scheduled articles whose time has come go live (and to X)."""

from __future__ import annotations

import logging
import threading
import time

from flask import Flask

from app.db import get_db
from app.services.publish import publish_due_articles

log = logging.getLogger(__name__)

_started = False
_lock = threading.Lock()


def start_publish_scheduler(app: Flask) -> None:
    global _started
    cfg = app.config.get("APP_CONFIG")
    if cfg is None or not cfg.scheduler_enabled:
        return
    if app.config.get("TESTING"):
        return
    with _lock:
        if _started:
            return
        _started = True

    interval = max(5, int(cfg.scheduler_poll_seconds or 30))

    def _loop() -> None:
        # First pass after a short delay so gunicorn is listening.
        time.sleep(min(interval, 5))
        while True:
            try:
                with app.app_context():
                    n = publish_due_articles(cfg, get_db(cfg))
                    if n:
                        log.info("Scheduler published %d article(s)", len(n))
            except Exception:
                log.exception("Scheduler tick failed")
            time.sleep(interval)

    thread = threading.Thread(target=_loop, name="article-publish-scheduler", daemon=True)
    thread.start()
    log.info("Article publish scheduler started (every %ss)", interval)
