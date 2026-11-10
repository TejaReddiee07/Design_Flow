"""Local disk storage (default; also the fallback when Drive is not configured)."""
from __future__ import annotations

import secrets
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.services.storage.base import StorageBackend, StoredFile


class LocalStorage(StorageBackend):
    name = "local"

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = root or settings.upload_dir

    def _safe_folder(self, folder: str) -> Path:
        parts = [p for p in folder.replace("\\", "/").split("/") if p and p not in (".", "..")]
        target = self.root.joinpath(*parts) if parts else self.root
        target.mkdir(parents=True, exist_ok=True)
        return target

    def save(self, data: bytes, filename: str, folder: str, mime_type: str) -> StoredFile:
        # Keep the real file name on disk so client folders are readable in Explorer/Finder;
        # add " (2)", " (3)" ... when a file with that name already exists.
        from app.services.folders import safe_name

        target_dir = self._safe_folder(folder)
        original = Path(filename or "file")
        ext = original.suffix.lower()[:12]
        stem = safe_name(original.stem, fallback="file", limit=100)
        stored_name = f"{stem}{ext}"
        n = 2
        while (target_dir / stored_name).exists():
            stored_name = f"{stem} ({n}){ext}"
            n += 1
            if n > 500:  # pragma: no cover - pathological
                stored_name = f"{stem}-{secrets.token_hex(4)}{ext}"
                break
        path = target_dir / stored_name
        path.write_bytes(data)
        rel = path.relative_to(self.root).as_posix()
        return StoredFile(backend=self.name, stored_name=stored_name, path=rel, size_bytes=len(data))

    def read(self, stored: StoredFile) -> bytes:
        path = (self.root / (stored.path or stored.stored_name)).resolve()
        if not str(path).startswith(str(self.root.resolve())):
            raise PermissionError("Invalid path")
        return path.read_bytes()

    def delete(self, stored: StoredFile) -> None:
        path = self.root / (stored.path or stored.stored_name)
        if path.exists():
            path.unlink()

    def create_folder(self, name: str, parent: Optional[str] = None) -> str:
        folder = f"{parent}/{name}" if parent else name
        self._safe_folder(folder)
        return folder
