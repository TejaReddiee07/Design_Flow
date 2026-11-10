"""Storage backend interface."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class StoredFile:
    backend: str
    stored_name: str
    path: Optional[str] = None  # local relative path
    drive_file_id: Optional[str] = None
    public_url: Optional[str] = None
    size_bytes: int = 0
    meta: Dict[str, Any] = field(default_factory=dict)


class StorageBackend:
    name = "base"

    def save(self, data: bytes, filename: str, folder: str, mime_type: str) -> StoredFile:
        raise NotImplementedError

    def read(self, stored: StoredFile) -> bytes:
        raise NotImplementedError

    def delete(self, stored: StoredFile) -> None:
        raise NotImplementedError

    def create_folder(self, name: str, parent: Optional[str] = None) -> str:
        """Returns a folder identifier (path or Drive id)."""
        raise NotImplementedError

    def share_link(self, stored: StoredFile) -> Optional[str]:
        return stored.public_url
