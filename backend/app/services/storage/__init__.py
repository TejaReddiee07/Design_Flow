"""Storage factory: picks Google Drive when configured, local disk otherwise."""
from __future__ import annotations

import logging
from functools import lru_cache

from app.core.config import settings
from app.services.storage.base import StorageBackend, StoredFile  # noqa: F401
from app.services.storage.local import LocalStorage

log = logging.getLogger("storage")


@lru_cache
def get_storage() -> StorageBackend:
    if settings.storage_backend.lower() == "gdrive":
        try:
            from app.services.storage.google_drive import GoogleDriveStorage

            backend = GoogleDriveStorage()
            log.info("Using Google Drive storage")
            return backend
        except Exception as exc:
            log.warning("Google Drive not available (%s); falling back to local storage", exc)
    return LocalStorage()


def storage_for(backend_name: str) -> StorageBackend:
    """Backend used to read a file stored earlier (may differ from the current default)."""
    if backend_name == "gdrive":
        from app.services.storage.google_drive import GoogleDriveStorage

        return GoogleDriveStorage()
    return LocalStorage()
