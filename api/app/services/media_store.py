"""S3-compatible media storage (MinIO local / DigitalOcean Spaces prod)."""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import BinaryIO

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from app.config import Config

log = logging.getLogger(__name__)


class MediaStore:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self._client = boto3.client(
            "s3",
            endpoint_url=cfg.s3_endpoint_url or None,
            aws_access_key_id=cfg.s3_access_key,
            aws_secret_access_key=cfg.s3_secret_key,
            region_name=cfg.s3_region,
            config=BotoConfig(
                signature_version="s3v4",
                s3={"addressing_style": "path" if cfg.s3_force_path_style else "auto"},
            ),
        )

    def ensure_bucket(self) -> None:
        bucket = self.cfg.s3_bucket
        try:
            self._client.head_bucket(Bucket=bucket)
        except ClientError:
            try:
                self._client.create_bucket(Bucket=bucket)
                log.info("Created bucket %s", bucket)
            except ClientError as exc:
                log.warning("create_bucket %s: %s", bucket, exc)

    def object_key(self, kind: str, slug: str, filename: str) -> str:
        """kind is 'article' or 'ad'."""
        safe_slug = slug.strip("/").replace("..", "")
        safe_name = Path(filename).name
        return f"{kind}/{safe_slug}/{safe_name}"

    def public_url(self, key: str) -> str:
        return self.cfg.public_media_url(key)

    def upload_file(
        self,
        local_path: Path,
        key: str,
        *,
        content_type: str | None = None,
        cache_control: str = "public, max-age=31536000, immutable",
    ) -> str:
        if content_type is None:
            content_type = mimetypes.guess_type(str(local_path))[0] or "application/octet-stream"
        extra = {
            "ContentType": content_type,
            "CacheControl": cache_control,
            "ACL": "public-read",
        }
        try:
            self._client.upload_file(
                str(local_path),
                self.cfg.s3_bucket,
                key,
                ExtraArgs=extra,
            )
        except ClientError:
            # Some MinIO setups reject ACL — retry without
            extra.pop("ACL", None)
            self._client.upload_file(
                str(local_path),
                self.cfg.s3_bucket,
                key,
                ExtraArgs=extra,
            )
        return self.public_url(key)

    def upload_bytes(
        self,
        data: bytes | BinaryIO,
        key: str,
        *,
        content_type: str = "application/octet-stream",
        cache_control: str = "public, max-age=31536000, immutable",
    ) -> str:
        body = data if isinstance(data, (bytes, bytearray)) else data.read()
        extra = {
            "ContentType": content_type,
            "CacheControl": cache_control,
        }
        try:
            self._client.put_object(
                Bucket=self.cfg.s3_bucket,
                Key=key,
                Body=body,
                ACL="public-read",
                **extra,
            )
        except ClientError:
            self._client.put_object(
                Bucket=self.cfg.s3_bucket,
                Key=key,
                Body=body,
                **extra,
            )
        return self.public_url(key)

    def get_bytes(self, key: str) -> bytes:
        try:
            resp = self._client.get_object(Bucket=self.cfg.s3_bucket, Key=key)
        except ClientError as exc:
            raise FileNotFoundError(key) from exc
        body = resp.get("Body")
        if body is None:
            raise FileNotFoundError(key)
        return body.read()

    def delete_key(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self.cfg.s3_bucket, Key=key)
        except ClientError as exc:
            log.warning("delete %s: %s", key, exc)
