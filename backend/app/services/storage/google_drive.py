"""Google Drive storage via a service account.

Setup:
  1. Create a service account in Google Cloud, enable the Drive API, download its JSON key.
  2. Put the key at GDRIVE_SERVICE_ACCOUNT_FILE (default ./secrets/gdrive-service-account.json).
  3. Create a folder in your Drive, share it with the service account email (Editor),
     copy the folder id from the URL into GDRIVE_ROOT_FOLDER_ID.
  4. Set STORAGE_BACKEND=gdrive.
"""
from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Optional

from app.core.config import PROJECT_DIR, settings
from app.services.storage.base import StorageBackend, StoredFile

log = logging.getLogger("storage.gdrive")
SCOPES = ["https://www.googleapis.com/auth/drive"]


class GoogleDriveStorage(StorageBackend):
    name = "gdrive"

    def __init__(self) -> None:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        key_path = Path(settings.gdrive_service_account_file)
        if not key_path.is_absolute():
            key_path = PROJECT_DIR / key_path
        if not key_path.exists():
            raise FileNotFoundError(f"Service account file not found: {key_path}")
        creds = service_account.Credentials.from_service_account_file(str(key_path), scopes=SCOPES)
        self.service = build("drive", "v3", credentials=creds, cache_discovery=False)
        self.root_id = settings.gdrive_root_folder_id or None

    # -- folders -----------------------------------------------------------
    def _find_folder(self, name: str, parent: Optional[str]) -> Optional[str]:
        q = f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        if parent:
            q += f" and '{parent}' in parents"
        res = self.service.files().list(q=q, fields="files(id, name)", pageSize=1).execute()
        files = res.get("files", [])
        return files[0]["id"] if files else None

    def create_folder(self, name: str, parent: Optional[str] = None) -> str:
        parent = parent or self.root_id
        existing = self._find_folder(name, parent)
        if existing:
            return existing
        meta = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
        if parent:
            meta["parents"] = [parent]
        folder = self.service.files().create(body=meta, fields="id").execute()
        return folder["id"]

    def _ensure_path(self, folder: str) -> Optional[str]:
        """folder like 'clients/12/requests/40' -> nested Drive folders."""
        parent = self.root_id
        for part in [p for p in folder.split("/") if p]:
            parent = self.create_folder(part, parent)
        return parent

    # -- files -------------------------------------------------------------
    def save(self, data: bytes, filename: str, folder: str, mime_type: str) -> StoredFile:
        from googleapiclient.http import MediaIoBaseUpload

        parent = self._ensure_path(folder)
        meta = {"name": filename}
        if parent:
            meta["parents"] = [parent]
        media = MediaIoBaseUpload(io.BytesIO(data), mimetype=mime_type or "application/octet-stream", resumable=False)
        created = (
            self.service.files()
            .create(body=meta, media_body=media, fields="id, webViewLink, webContentLink, size")
            .execute()
        )
        file_id = created["id"]
        try:
            self.service.permissions().create(
                fileId=file_id, body={"role": "reader", "type": "anyone"}, fields="id"
            ).execute()
        except Exception as exc:  # pragma: no cover
            log.warning("Could not make Drive file public: %s", exc)
        return StoredFile(
            backend=self.name,
            stored_name=filename,
            drive_file_id=file_id,
            public_url=created.get("webViewLink"),
            size_bytes=int(created.get("size", len(data))),
            meta={"download": created.get("webContentLink")},
        )

    def read(self, stored: StoredFile) -> bytes:
        from googleapiclient.http import MediaIoBaseDownload

        request = self.service.files().get_media(fileId=stored.drive_file_id)
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buf.getvalue()

    def delete(self, stored: StoredFile) -> None:
        if stored.drive_file_id:
            self.service.files().delete(fileId=stored.drive_file_id).execute()

    def share_link(self, stored: StoredFile) -> Optional[str]:
        return stored.public_url
