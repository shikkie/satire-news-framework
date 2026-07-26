"""Environment-driven configuration. Domain + credentials switch local ↔ prod."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_int(key: str, default: int) -> int:
    raw = os.environ.get(key)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    site_domain: str = "agentnews.local"
    assets_domain: str = "assets.agentnews.local"
    site_name: str = "Agent News"
    site_url: str = "http://agentnews.local"
    assets_url: str = "http://assets.agentnews.local"

    secret_key: str = "dev-only-change-me"
    debug: bool = False
    cors_origins: tuple[str, ...] = field(default_factory=tuple)

    admin_username: str = "admin"
    admin_password: str = "change-me-admin-password"

    mongo_uri: str = "mongodb://127.0.0.1:27017"
    mongo_db: str = "agentnews"

    s3_endpoint_url: str = "http://127.0.0.1:9000"
    s3_public_endpoint_url: str = "http://assets.agentnews.local"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "agentnews-media"
    s3_region: str = "us-east-1"
    s3_force_path_style: bool = True
    media_public_base_url: str = "http://assets.agentnews.local/agentnews-media"

    session_idle_minutes: int = 15
    session_header: str = "X-Session-Id"

    gcore_api_token: str = ""
    gcore_resource_id: str = ""
    gcore_cdn_base_url: str = ""
    spaces_cdn_prime: bool = True

    static_dir: str = ""
    seed_articles_dir: str = "/app/seed/articles"
    seed_ads_dir: str = "/app/seed/ads"

    @classmethod
    def from_env(cls) -> Config:
        # Load .env if present (repo root or cwd)
        try:
            from dotenv import load_dotenv

            for candidate in (
                Path.cwd() / ".env",
                Path(__file__).resolve().parents[2] / ".env",
            ):
                if candidate.is_file():
                    load_dotenv(candidate, override=False)
                    break
        except ImportError:
            pass

        cors_raw = _env("CORS_ORIGINS")
        cors = tuple(o.strip() for o in cors_raw.split(",") if o.strip()) if cors_raw else ()

        static_default = str(Path(__file__).resolve().parents[1] / "static")
        return cls(
            site_domain=_env("SITE_DOMAIN", "agentnews.local"),
            assets_domain=_env("ASSETS_DOMAIN", "assets.agentnews.local"),
            site_name=_env("SITE_NAME", "Agent News"),
            site_url=_env("SITE_URL", "http://agentnews.local"),
            assets_url=_env("ASSETS_URL", "http://assets.agentnews.local"),
            secret_key=_env("SECRET_KEY", "dev-only-change-me"),
            debug=_env_bool("FLASK_DEBUG", _env("FLASK_ENV") == "development"),
            cors_origins=cors,
            admin_username=_env("ADMIN_USERNAME", "admin"),
            admin_password=_env("ADMIN_PASSWORD", "change-me-admin-password"),
            mongo_uri=_env("MONGO_URI", "mongodb://127.0.0.1:27017"),
            mongo_db=_env("MONGO_DB", "agentnews"),
            s3_endpoint_url=_env("S3_ENDPOINT_URL", "http://127.0.0.1:9000"),
            s3_public_endpoint_url=_env(
                "S3_PUBLIC_ENDPOINT_URL", "http://assets.agentnews.local"
            ),
            s3_access_key=_env("S3_ACCESS_KEY", "minioadmin"),
            s3_secret_key=_env("S3_SECRET_KEY", "minioadmin"),
            s3_bucket=_env("S3_BUCKET", "agentnews-media"),
            s3_region=_env("S3_REGION", "us-east-1"),
            s3_force_path_style=_env_bool("S3_FORCE_PATH_STYLE", True),
            media_public_base_url=_env(
                "MEDIA_PUBLIC_BASE_URL",
                "http://assets.agentnews.local/agentnews-media",
            ),
            session_idle_minutes=_env_int("SESSION_IDLE_MINUTES", 15),
            session_header=_env("SESSION_HEADER", "X-Session-Id"),
            gcore_api_token=_env("GCORE_API_TOKEN"),
            gcore_resource_id=_env("GCORE_RESOURCE_ID"),
            gcore_cdn_base_url=_env("GCORE_CDN_BASE_URL"),
            spaces_cdn_prime=_env_bool("SPACES_CDN_PRIME", True),
            static_dir=_env("STATIC_DIR", static_default),
            seed_articles_dir=_env("SEED_ARTICLES_DIR", "/app/seed/articles"),
            seed_ads_dir=_env("SEED_ADS_DIR", "/app/seed/ads"),
        )

    def as_flask_mapping(self) -> dict:
        return {
            "SECRET_KEY": self.secret_key,
            "DEBUG": self.debug,
        }

    def public_media_url(self, key: str) -> str:
        base = self.media_public_base_url.rstrip("/")
        return f"{base}/{key.lstrip('/')}"

    def article_page_url(self, slug: str) -> str:
        return f"{self.site_url.rstrip('/')}/article/{slug}"
