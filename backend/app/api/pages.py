"""Serves the static frontend (landing, service pages, portal, admin)."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.config import FRONTEND_DIR

router = APIRouter(include_in_schema=False)


def _file(rel: str) -> FileResponse:
    path = (FRONTEND_DIR / rel).resolve()
    if not str(path).startswith(str(FRONTEND_DIR.resolve())) or not path.is_file():
        raise HTTPException(status_code=404, detail="Page not found")
    return FileResponse(path, media_type="text/html")


@router.get("/")
def landing():
    return _file("index.html")


@router.get("/login")
def login_page():
    return _file("login.html")


@router.get("/register")
def register_page():
    return _file("register.html")


@router.get("/portal")
@router.get("/portal/")
def portal():
    return _file("portal/index.html")


@router.get("/admin")
@router.get("/admin/")
def admin():
    return _file("admin/index.html")


@router.get("/admin/live/{request_id}")
def admin_live(request_id: int):
    """"See in live": one request's agents working in real time (opens in its own tab)."""
    return _file("admin/live.html")


@router.get("/services")
@router.get("/services/")
def services_index():
    return _file("services/index.html")


@router.get("/services/{slug}")
def service_page(slug: str):
    safe = "".join(ch for ch in slug if ch.isalnum() or ch == "-")
    return _file(f"services/{safe}.html")


@router.get("/privacy")
def privacy():
    return _file("legal/privacy.html")


@router.get("/terms")
def terms():
    return _file("legal/terms.html")
