"""Register Flask blueprints."""

from __future__ import annotations

from flask import Flask


def register_blueprints(app: Flask) -> None:
    from app.routes.ads import bp as ads_bp
    from app.routes.articles import bp as articles_bp
    from app.routes.auth_routes import bp as auth_bp
    from app.routes.spa import bp as spa_bp
    from app.routes.settings import bp as settings_bp
    from app.routes.users import bp as users_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(articles_bp)
    app.register_blueprint(ads_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(spa_bp)
