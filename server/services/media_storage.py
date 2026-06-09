"""Local media storage helpers for entry images.

This module intentionally stores only storage keys in the database and resolves
them to browser-usable URLs at response time, so the backend can later swap the
storage backend without changing the entry contracts again.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path, PurePosixPath
from typing import Final
from uuid import uuid4

from flask import current_app, request


DEFAULT_MEDIA_URL_PREFIX: Final[str] = "/media"
_MIME_TO_EXTENSION: Final[dict[str, str]] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


def ensure_media_root(media_root: str) -> None:
    os.makedirs(media_root, exist_ok=True)


def is_legacy_data_url(value: object) -> bool:
    return isinstance(value, str) and value.strip().startswith("data:image/")


def store_generated_image(image_bytes: bytes, *, user_id: int, entry_kind: str) -> str:
    return _store_image_bytes(
        image_bytes,
        user_id=user_id,
        entry_kind=entry_kind,
        extension="png",
    )


def store_uploaded_image(image_bytes: bytes, *, user_id: int, entry_kind: str) -> str:
    return _store_image_bytes(
        image_bytes,
        user_id=user_id,
        entry_kind=entry_kind,
        extension="jpg",
    )


def migrate_legacy_data_url(data_url: str, *, user_id: int, entry_kind: str) -> str:
    if not is_legacy_data_url(data_url):
        raise ValueError("Value is not a legacy image data URL.")

    header, _, encoded = data_url.partition(",")
    mime_type = header.removeprefix("data:").partition(";")[0].strip().lower()
    extension = _MIME_TO_EXTENSION.get(mime_type)
    if not extension:
        raise ValueError(f"Unsupported legacy image mime type: {mime_type}")

    image_bytes = base64.b64decode(encoded, validate=True)
    return _store_image_bytes(
        image_bytes,
        user_id=user_id,
        entry_kind=entry_kind,
        extension=extension,
    )


def delete_image(storage_key: str | None) -> None:
    if not storage_key:
        return

    image_path = _storage_key_to_path(storage_key)
    try:
        image_path.unlink(missing_ok=True)
    except TypeError:
        if image_path.exists():
            image_path.unlink()

    _cleanup_empty_parent_dirs(image_path.parent)


def resolve_image_url(storage_key: str | None) -> str | None:
    if not storage_key:
        return None

    base_url = (current_app.config.get("MEDIA_BASE_URL") or "").rstrip("/")
    if not base_url:
        base_url = request.url_root.rstrip("/")

    media_prefix = current_app.config.get("MEDIA_URL_PREFIX", DEFAULT_MEDIA_URL_PREFIX).rstrip("/")
    safe_key = "/".join(PurePosixPath(storage_key).parts)
    return f"{base_url}{media_prefix}/{safe_key}"


def media_path_exists(storage_key: str | None) -> bool:
    if not storage_key:
        return False
    return _storage_key_to_path(storage_key).exists()


def _store_image_bytes(
    image_bytes: bytes,
    *,
    user_id: int,
    entry_kind: str,
    extension: str,
) -> str:
    if not image_bytes:
        raise ValueError("No image bytes were provided for storage.")

    storage_key = f"entries/{entry_kind}/{user_id}/{uuid4().hex}.{extension}"
    image_path = _storage_key_to_path(storage_key)
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(image_bytes)
    return storage_key


def _storage_key_to_path(storage_key: str) -> Path:
    posix_key = PurePosixPath(storage_key)
    if posix_key.is_absolute() or ".." in posix_key.parts:
        raise ValueError("Invalid media storage key.")

    media_root = Path(current_app.config["MEDIA_ROOT"])
    return media_root.joinpath(*posix_key.parts)


def _cleanup_empty_parent_dirs(path: Path) -> None:
    media_root = Path(current_app.config["MEDIA_ROOT"]).resolve()
    current = path.resolve()

    while current != media_root and media_root in current.parents:
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent
