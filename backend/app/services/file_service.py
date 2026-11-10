"""Upload validation + persistence of file documents."""
from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile

from app.core.config import settings
from app.db.mongo import DB, Doc, utcnow
from app.services.storage import StoredFile, get_storage, storage_for

ALLOWED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".tiff", ".heic",
    ".pdf", ".ai", ".psd", ".eps", ".sketch", ".fig", ".xd", ".indd",
    ".doc", ".docx", ".ppt", ".pptx", ".key", ".xls", ".xlsx", ".csv", ".txt", ".md", ".rtf",
    ".zip", ".rar", ".7z",
    ".mp4", ".mov", ".webm", ".mp3", ".wav",
    ".ttf", ".otf", ".woff", ".woff2",
    ".json",
}
BLOCKED_MIME_PREFIXES = ("application/x-msdownload", "application/x-sh", "text/x-python", "application/javascript")
MAGIC = {
    b"\x89PNG": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
    b"GIF8": "image/gif",
    b"%PDF": "application/pdf",
    b"PK\x03\x04": "application/zip",
    b"RIFF": "image/webp",
}


def _sniff(data: bytes, declared: str, ext: str) -> str:
    for magic, mime in MAGIC.items():
        if data.startswith(magic):
            if mime == "application/zip" and ext in (".docx", ".pptx", ".xlsx", ".key", ".sketch", ".fig"):
                return mimetypes.guess_type(f"x{ext}")[0] or declared
            return mime
    if ext == ".svg":
        if b"<script" in data[:512].lower():
            raise HTTPException(status_code=400, detail="SVG with scripts is not allowed")
        return "image/svg+xml"
    return mimetypes.guess_type(f"x{ext}")[0] or declared or "application/octet-stream"


def validate_upload(filename: str, data: bytes, declared_mime: str) -> tuple[str, str]:
    name = Path(filename or "upload").name
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type {ext or '(none)'} is not allowed")
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.max_upload_mb} MB limit")
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    mime = _sniff(data, declared_mime or "", ext)
    if mime.startswith(BLOCKED_MIME_PREFIXES):
        raise HTTPException(status_code=400, detail="Executable content is not allowed")
    return name, mime


def store_bytes(
    db: DB,
    *,
    data: bytes,
    filename: str,
    mime_type: str,
    folder: str,
    kind: str,
    owner_user_id: Optional[int],
    client_id: Optional[int] = None,
    request_id: Optional[int] = None,
    parent_file_id: Optional[int] = None,
    meta: Optional[dict] = None,
) -> Doc:
    stored = get_storage().save(data, filename, folder, mime_type)
    version = 1
    if parent_file_id:
        parent = db.files.get(parent_file_id)
        if parent:
            version = int(parent.get("version", 1)) + 1
    return db.files.insert(
        {
            "owner_user_id": owner_user_id,
            "client_id": client_id,
            "request_id": request_id,
            "kind": kind,
            "original_name": filename,
            "stored_name": stored.stored_name,
            "backend": stored.backend,
            "path": stored.path,
            "drive_file_id": stored.drive_file_id,
            "public_url": stored.public_url,
            "mime_type": mime_type,
            "size_bytes": len(data),
            "version": version,
            "parent_file_id": parent_file_id,
            "checksum": hashlib.sha256(data).hexdigest(),
            "meta": {**(meta or {}), **stored.meta},
            "created_at": utcnow(),
        }
    )


async def store_upload(
    db: DB,
    upload: UploadFile,
    *,
    folder: str,
    kind: str,
    owner_user_id: Optional[int],
    client_id: Optional[int] = None,
    request_id: Optional[int] = None,
    parent_file_id: Optional[int] = None,
) -> Doc:
    data = await upload.read()
    name, mime = validate_upload(upload.filename or "upload", data, upload.content_type or "")
    return store_bytes(db, data=data, filename=name, mime_type=mime, folder=folder, kind=kind, owner_user_id=owner_user_id,
                       client_id=client_id, request_id=request_id, parent_file_id=parent_file_id)


def read_file_bytes(row: Doc) -> bytes:
    backend = storage_for(row.get("backend", "local"))
    return backend.read(StoredFile(backend=row.get("backend", "local"), stored_name=row.get("stored_name"), path=row.get("path"), drive_file_id=row.get("drive_file_id")))


def file_to_dict(row: Doc) -> dict:
    return {
        "id": row.id,
        "kind": row.get("kind"),
        "original_name": row.get("original_name"),
        "mime_type": row.get("mime_type"),
        "size_bytes": row.get("size_bytes", 0),
        "version": row.get("version", 1),
        "public_url": row.get("public_url"),
        "request_id": row.get("request_id"),
        "client_id": row.get("client_id"),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "download_url": f"/api/v1/files/{row.id}/download",
    }
