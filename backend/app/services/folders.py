"""Readable storage folders: every client has their own folder, named after the client.

    clients/<Company name> #<client id>/
        <Service name>/
            Request <id> - <title>/
                Drafts/v<version>/...        files produced by the Design Agent (or uploaded by the admin)
                Final/...                    the delivered package (ZIP + delivery notes)
                Uploads/...                  files the client attached
        Brand assets/...

The same names are used on local disk and on Google Drive, so the admin can also browse them outside the app.
"""
from __future__ import annotations

import re
from typing import Optional

from app.db.mongo import DB, Doc

_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_name(value: Optional[str], *, fallback: str = "Untitled", limit: int = 80) -> str:
    """Make a string safe as a folder/file name on Windows, macOS, Linux and Drive (keeps spaces and &)."""
    text = _FORBIDDEN.sub(" ", str(value or "")).strip()
    text = re.sub(r"\s+", " ", text).strip(" .")
    return (text[:limit].rstrip(" .") or fallback)


def client_folder(db: DB, client_id: Optional[int], client: Optional[Doc] = None) -> str:
    if not client_id:
        return "clients/Shared"
    client = client or db.clients.get(client_id)
    name = safe_name(client.get("company_name") if client else None, fallback="Client")
    return f"clients/{name} #{int(client_id)}"


def service_folder(db: DB, client_id: Optional[int], service: Optional[Doc]) -> str:
    return f"{client_folder(db, client_id)}/{safe_name(service.get('name') if service else None, fallback='Other')}"


def request_folder(db: DB, req: Doc, sub: Optional[str] = None, *, service: Optional[Doc] = None, client: Optional[Doc] = None) -> str:
    service = service or db.services.get(req.get("service_id"))
    base = f"{client_folder(db, req.get('client_id'), client)}/{safe_name(service.get('name') if service else None, fallback='Other')}"
    base += f"/Request {int(req.id)} - {safe_name(req.get('title'), limit=60)}"
    return f"{base}/{sub.strip('/')}" if sub else base


def brand_assets_folder(db: DB, client_id: Optional[int]) -> str:
    return f"{client_folder(db, client_id)}/Brand assets"
