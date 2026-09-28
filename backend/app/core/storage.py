"""Safe filesystem paths for user-controlled file identifiers (uploads, backups)."""
import os
import uuid

from app.core.config import settings


class InvalidStoragePath(ValueError):
    """Raised when a client-supplied file name escapes its storage directory."""


def _resolve_inside(base_dir: str, name: str) -> str:
    if not name or name in (".", ".."):
        raise InvalidStoragePath("Fayl nomi bo'sh yoki noto'g'ri")
    if "/" in name or "\\" in name or ":" in name or "\x00" in name:
        raise InvalidStoragePath("Fayl nomida katalog belgilari bo'lishi mumkin emas")

    base_real = os.path.realpath(base_dir)
    full_real = os.path.realpath(os.path.join(base_real, name))
    if os.path.dirname(full_real) != base_real:
        raise InvalidStoragePath("Fayl yo'li ruxsat etilgan katalogdan tashqarida")
    return full_real


def resolve_upload_path(file_id: str) -> str:
    """Absolute path of an uploaded file; rejects any traversal attempt."""
    return _resolve_inside(settings.UPLOAD_DIR, file_id)


def resolve_backup_path(filename: str) -> str:
    """Absolute path of a backup snapshot; rejects any traversal attempt."""
    return _resolve_inside(settings.BACKUP_DIR, filename)


def build_upload_filename(original_name: str) -> str:
    """Unique stored name `<uuid>_<basename>`, stripping any client-supplied directories."""
    base = os.path.basename((original_name or "").replace("\\", "/")).replace(":", "_")
    return f"{uuid.uuid4()}_{base or 'file'}"


def ensure_storage_dirs() -> None:
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.BACKUP_DIR, exist_ok=True)
