"""Agent News Flask application factory."""

from __future__ import annotations

import logging

from flask import Flask, g, request

from app.config import Config
from app.db import ensure_indexes, get_db, ping_mongo
from app.routes import register_blueprints
from app.services.bootstrap import ensure_bootstrap_admin


def create_app(config: Config | None = None) -> Flask:
    cfg = config or Config.from_env()
    # Do not register Flask's built-in static route at "". It 404s unknown
    # paths (e.g. /admin/login) before the SPA fallback blueprint can run.
    app = Flask(__name__, static_folder=None)
    app.config.from_mapping(cfg.as_flask_mapping())
    app.config["APP_CONFIG"] = cfg

    logging.basicConfig(
        level=logging.DEBUG if cfg.debug else logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    @app.before_request
    def _api_no_store() -> None:
        # Attach response header later for /api; store flag on g
        g.is_api = request.path.startswith("/api/")

    @app.after_request
    def _set_cache_headers(response):  # type: ignore[no-untyped-def]
        if getattr(g, "is_api", False):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
        # CORS (optional, env-driven)
        origins = cfg.cors_origins
        origin = request.headers.get("Origin")
        if origins and origin and origin in origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Headers"] = (
                f"Content-Type, {cfg.session_header}"
            )
            response.headers["Access-Control-Allow-Methods"] = (
                "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            )
            response.headers["Vary"] = "Origin"
        return response

    @app.route("/api/health")
    def health():  # type: ignore[no-untyped-def]
        from flask import jsonify

        mongo_ok = ping_mongo(cfg)
        return jsonify(
            {
                "status": "ok" if mongo_ok else "degraded",
                "mongo": mongo_ok,
                "site_domain": cfg.site_domain,
                "assets_domain": cfg.assets_domain,
            }
        ), (200 if mongo_ok else 503)

    register_blueprints(app)

    # Indexes + seed admin (best-effort; tests may use mongomock without real server)
    try:
        db = get_db(cfg)
        ensure_indexes(db)
        ensure_bootstrap_admin(db, cfg)
    except Exception as exc:  # noqa: BLE001 — startup should not crash compose loops
        app.logger.warning("Startup index/bootstrap skipped: %s", exc)

    try:
        from app.services.scheduler import start_publish_scheduler

        start_publish_scheduler(app)
    except Exception as exc:  # noqa: BLE001
        app.logger.warning("Publish scheduler not started: %s", exc)

    return app
