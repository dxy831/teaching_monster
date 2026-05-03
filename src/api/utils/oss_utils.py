from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any, Dict
from urllib.parse import quote, urlparse, urlunparse

import oss2

from ..config import settings


def ensure_oss_config() -> None:
    if not settings.oss_enabled:
        raise ValueError("OSS competition upload is disabled. Set OSS_ENABLED=true.")

    missing = [
        name
        for name, value in {
            "OSS_ENDPOINT": settings.oss_endpoint,
            "OSS_BUCKET_NAME": settings.oss_bucket_name,
            "OSS_ACCESS_KEY_ID": settings.oss_access_key_id,
            "OSS_ACCESS_KEY_SECRET": settings.oss_access_key_secret,
        }.items()
        if not value
    ]
    if missing:
        raise ValueError(f"Missing OSS configuration: {', '.join(missing)}")


def build_oss_object_key(request_id: str, filename: str, prefix: str | None = None) -> str:
    clean_prefix = (prefix if prefix is not None else settings.oss_key_prefix).strip("/")
    clean_request_id = request_id.strip().strip("/")
    if clean_prefix:
        return f"{clean_prefix}/{clean_request_id}/{filename}"
    return f"{clean_request_id}/{filename}"


def _build_bucket() -> oss2.Bucket:
    auth = oss2.Auth(settings.oss_access_key_id, settings.oss_access_key_secret)
    return oss2.Bucket(auth, settings.oss_endpoint, settings.oss_bucket_name)


def upload_file_to_oss(local_path: str, object_key: str, content_type: str | None = None) -> Dict[str, Any]:
    ensure_oss_config()
    path = Path(local_path)
    if not path.exists():
        raise FileNotFoundError(f"File does not exist: {local_path}")

    guessed_content_type = content_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    bucket = _build_bucket()
    result = bucket.put_object_from_file(
        object_key,
        str(path),
        headers={"Content-Type": guessed_content_type},
    )
    return {
        "object_key": object_key,
        "etag": result.etag,
        "content_type": guessed_content_type,
    }


def generate_oss_signed_url(object_key: str, expires_seconds: int | None = None) -> str:
    ensure_oss_config()
    bucket = _build_bucket()
    expires = expires_seconds if expires_seconds is not None else settings.oss_url_expire_seconds
    encoded_object_key = quote(object_key, safe="/")
    signed_url = bucket.sign_url("GET", encoded_object_key, expires)
    parsed = urlparse(signed_url)
    return urlunparse(("https", parsed.netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
