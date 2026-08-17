"""Media storage helpers for entry images and attachments.

This module intentionally stores only storage keys in the database and resolves
them to browser-usable URLs at response time, so the backend can later swap the
storage backend without changing the entry contracts again.
"""

from __future__ import annotations

import base64
import mimetypes
import os
import time
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Final
from uuid import uuid4

from flask import Response, current_app, request
from PIL import Image, ImageOps, UnidentifiedImageError


DEFAULT_MEDIA_URL_PREFIX: Final[str] = "/media"
LOCAL_MEDIA_BACKEND: Final[str] = "local"
R2_MEDIA_BACKEND: Final[str] = "r2"
SUPPORTED_MEDIA_BACKENDS: Final[set[str]] = {LOCAL_MEDIA_BACKEND, R2_MEDIA_BACKEND}
_MIME_TO_EXTENSION: Final[dict[str, str]] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
_ALLOWED_EXTENSIONS: Final[set[str]] = {
    "jpg",
    "jpeg",
    "png",
    "webp",
    "pdf",
    "mp3",
    "wav",
    "m4a",
    "ogg",
    "webm",
    "aiff",
}
GENERATED_IMAGE_MAX_SIZE: Final[tuple[int, int]] = (1024, 1024)
GENERATED_IMAGE_JPEG_QUALITY: Final[int] = 86


def ensure_media_root(media_root: str) -> None:
    if _backend_from_env() == R2_MEDIA_BACKEND:
        return
    os.makedirs(media_root, exist_ok=True)


def is_legacy_data_url(value: object) -> bool:
    return isinstance(value, str) and value.strip().startswith("data:image/")


def store_generated_image(image_bytes: bytes, *, user_id: int, entry_kind: str) -> str:
    image_bytes = _normalise_generated_image_bytes(image_bytes)
    return _store_image_bytes(
        image_bytes,
        user_id=user_id,
        entry_kind=entry_kind,
        extension="jpg",
    )


def store_uploaded_image(image_bytes: bytes, *, user_id: int, entry_kind: str) -> str:
    return _store_image_bytes(
        image_bytes,
        user_id=user_id,
        entry_kind=entry_kind,
        extension="jpg",
    )


def store_profile_image(image_bytes: bytes, *, user_id: int) -> str:
    """Store a normalised profile image behind a cloud-portable storage key."""
    if not image_bytes:
        raise ValueError("No image bytes were provided for storage.")

    storage_key = f"profiles/{user_id}/{uuid4().hex}.jpg"
    _write_media_bytes(storage_key, image_bytes)
    return storage_key


def store_imported_image(
    image_bytes: bytes,
    *,
    user_id: int,
    entry_kind: str,
    filename: str,
) -> str:
    extension = Path(filename or "").suffix.lower().lstrip(".")
    if extension not in _ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported imported image extension: {extension or 'unknown'}")

    if extension == "jpeg":
        extension = "jpg"

    return _store_image_bytes(
        image_bytes,
        user_id=user_id,
        entry_kind=entry_kind,
        extension=extension,
    )


def store_entry_asset(
    file_bytes: bytes,
    *,
    user_id: int,
    entry_kind: str,
    filename: str,
) -> str:
    extension = Path(filename or "").suffix.lower().lstrip(".")
    if extension not in _ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported asset extension: {extension or 'unknown'}")

    if extension == "jpeg":
        extension = "jpg"

    return _store_image_bytes(
        file_bytes,
        user_id=user_id,
        entry_kind=f"{entry_kind}-assets",
        extension=extension,
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

    if _active_backend() == R2_MEDIA_BACKEND:
        _r2_client().delete_object(Bucket=_r2_bucket_name(), Key=_safe_storage_key(storage_key))
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

    safe_key = "/".join(PurePosixPath(storage_key).parts)
    r2_public_base_url = (current_app.config.get("R2_PUBLIC_BASE_URL") or "").rstrip("/")
    if _active_backend() == R2_MEDIA_BACKEND and r2_public_base_url:
        return f"{r2_public_base_url}/{safe_key}"

    base_url = (current_app.config.get("MEDIA_BASE_URL") or "").rstrip("/")
    if not base_url:
        base_url = request.url_root.rstrip("/")

    media_prefix = current_app.config.get("MEDIA_URL_PREFIX", DEFAULT_MEDIA_URL_PREFIX).rstrip("/")
    if base_url.endswith(media_prefix):
        return f"{base_url}/{safe_key}"
    return f"{base_url}{media_prefix}/{safe_key}"


def media_path_exists(storage_key: str | None) -> bool:
    if not storage_key:
        return False
    if _active_backend() == R2_MEDIA_BACKEND:
        try:
            _r2_client().head_object(Bucket=_r2_bucket_name(), Key=_safe_storage_key(storage_key))
            return True
        except Exception:  # noqa: BLE001
            return False
    return _storage_key_to_path(storage_key).exists()


def read_media_bytes(storage_key: str | None) -> bytes | None:
    if not storage_key:
        return None
    if _active_backend() == R2_MEDIA_BACKEND:
        try:
            response = _r2_client().get_object(Bucket=_r2_bucket_name(), Key=_safe_storage_key(storage_key))
        except Exception:  # noqa: BLE001
            return None
        body = response.get("Body")
        if body is None:
            return None
        return body.read()

    image_path = _storage_key_to_path(storage_key)
    if not image_path.exists():
        return None
    return image_path.read_bytes()


def read_image_bytes(storage_key: str | None) -> bytes | None:
    return read_media_bytes(storage_key)


def build_media_response(storage_key: str):
    media_bytes = read_media_bytes(storage_key)
    if media_bytes is None:
        return None
    mimetype, _encoding = mimetypes.guess_type(storage_key)
    return Response(media_bytes, mimetype=mimetype or "application/octet-stream")


def health_check(*, write: bool = False) -> dict[str, object]:
    """Return a sanitized media-storage readiness report."""
    started_at = time.perf_counter()
    report: dict[str, object] = {
        "backend": None,
        "ok": False,
        "configured": False,
        "read_ok": False,
        "write_ok": None if not write else False,
        "public_base_url_configured": False,
        "latency_ms": None,
    }
    try:
        backend = _active_backend()
        report["backend"] = backend
        report["public_base_url_configured"] = bool(
            str(current_app.config.get("R2_PUBLIC_BASE_URL") or "").strip()
            or str(current_app.config.get("MEDIA_BASE_URL") or "").strip()
        )

        if backend == R2_MEDIA_BACKEND:
            report["configured"] = all(
                str(current_app.config.get(name) or "").strip()
                for name in (
                    "R2_ENDPOINT_URL",
                    "R2_ACCESS_KEY_ID",
                    "R2_SECRET_ACCESS_KEY",
                    "R2_BUCKET_NAME",
                )
            )
            if not report["configured"]:
                report["message"] = "R2 media storage configuration is incomplete."
                return report
            client = _r2_client()
            report["read_ok"] = True
            if write:
                probe_key = f"health/{uuid4().hex}.txt"
                client.put_object(
                    Bucket=_r2_bucket_name(),
                    Key=probe_key,
                    Body=b"ok",
                    ContentType="text/plain",
                )
                client.delete_object(Bucket=_r2_bucket_name(), Key=probe_key)
                report["write_ok"] = True
        else:
            media_root = Path(current_app.config["MEDIA_ROOT"])
            ensure_media_root(str(media_root))
            report["configured"] = True
            report["read_ok"] = media_root.exists() and media_root.is_dir()
            if write:
                probe_path = media_root / "health" / f"{uuid4().hex}.txt"
                probe_path.parent.mkdir(parents=True, exist_ok=True)
                probe_path.write_bytes(b"ok")
                probe_path.unlink(missing_ok=True)
                _cleanup_empty_parent_dirs(probe_path.parent)
                report["write_ok"] = True
    except Exception as exc:  # noqa: BLE001
        report["error_type"] = exc.__class__.__name__
        report["message"] = "Media storage check failed."
        return report

    report["ok"] = bool(report["configured"] and report["read_ok"] and (not write or report["write_ok"]))
    report["latency_ms"] = round((time.perf_counter() - started_at) * 1000, 2)
    return report


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
    _write_media_bytes(storage_key, image_bytes)
    return storage_key


def _normalise_generated_image_bytes(image_bytes: bytes) -> bytes:
    if not image_bytes:
        raise ValueError("No generated image bytes were provided for storage.")

    try:
        image = Image.open(BytesIO(image_bytes))
        image = ImageOps.exif_transpose(image)
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Generated image data was not a supported image.") from exc

    if image.mode not in ("RGB", "L"):
        background = Image.new("RGB", image.size, (255, 255, 255))
        rgba_image = image.convert("RGBA")
        background.paste(rgba_image, mask=rgba_image.split()[-1])
        image = background
    else:
        image = image.convert("RGB")

    image.thumbnail(GENERATED_IMAGE_MAX_SIZE, Image.Resampling.LANCZOS)

    output = BytesIO()
    image.save(
        output,
        format="JPEG",
        quality=GENERATED_IMAGE_JPEG_QUALITY,
        optimize=True,
        progressive=True,
    )
    return output.getvalue()


def _write_media_bytes(storage_key: str, media_bytes: bytes) -> None:
    if _active_backend() == R2_MEDIA_BACKEND:
        _r2_client().put_object(
            Bucket=_r2_bucket_name(),
            Key=_safe_storage_key(storage_key),
            Body=media_bytes,
            ContentType=mimetypes.guess_type(storage_key)[0] or "application/octet-stream",
        )
        return

    image_path = _storage_key_to_path(storage_key)
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(media_bytes)


def _storage_key_to_path(storage_key: str) -> Path:
    safe_key = _safe_storage_key(storage_key)

    media_root = Path(current_app.config["MEDIA_ROOT"])
    return media_root.joinpath(*PurePosixPath(safe_key).parts)


def _safe_storage_key(storage_key: str) -> str:
    posix_key = PurePosixPath(str(storage_key or "").strip())
    if not posix_key.parts or posix_key.is_absolute() or ".." in posix_key.parts:
        raise ValueError("Invalid media storage key.")
    return "/".join(posix_key.parts)


def _backend_from_env() -> str:
    backend = (os.getenv("MEDIA_STORAGE_BACKEND") or LOCAL_MEDIA_BACKEND).strip().lower()
    return backend if backend in SUPPORTED_MEDIA_BACKENDS else LOCAL_MEDIA_BACKEND


def _active_backend() -> str:
    backend = (
        current_app.config.get("MEDIA_STORAGE_BACKEND")
        or os.getenv("MEDIA_STORAGE_BACKEND")
        or LOCAL_MEDIA_BACKEND
    )
    backend = str(backend).strip().lower()
    if backend not in SUPPORTED_MEDIA_BACKENDS:
        raise RuntimeError(f"Unsupported MEDIA_STORAGE_BACKEND: {backend}")
    return backend


def _r2_bucket_name() -> str:
    bucket_name = str(current_app.config.get("R2_BUCKET_NAME") or "").strip()
    if not bucket_name:
        raise RuntimeError("R2_BUCKET_NAME must be configured when MEDIA_STORAGE_BACKEND=r2")
    return bucket_name


def _r2_client():
    client = current_app.config.get("R2_CLIENT")
    if client is not None:
        return client

    endpoint_url = str(current_app.config.get("R2_ENDPOINT_URL") or "").strip()
    access_key_id = str(current_app.config.get("R2_ACCESS_KEY_ID") or "").strip()
    secret_access_key = str(current_app.config.get("R2_SECRET_ACCESS_KEY") or "").strip()
    if not endpoint_url or not access_key_id or not secret_access_key:
        raise RuntimeError(
            "R2_ENDPOINT_URL, R2_ACCESS_KEY_ID, and R2_SECRET_ACCESS_KEY must be "
            "configured when MEDIA_STORAGE_BACKEND=r2"
        )

    try:
        import boto3
        from botocore.config import Config
    except ImportError as exc:
        raise RuntimeError("boto3 is required when MEDIA_STORAGE_BACKEND=r2") from exc

    client = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )
    current_app.config["R2_CLIENT"] = client
    return client


def _cleanup_empty_parent_dirs(path: Path) -> None:
    media_root = Path(current_app.config["MEDIA_ROOT"]).resolve()
    current = path.resolve()

    while current != media_root and media_root in current.parents:
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent
