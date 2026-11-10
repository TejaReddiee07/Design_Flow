from __future__ import annotations

import re
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.audit import audit
from app.core.config import settings
from app.core.deps import require_admin
from app.core.security import hash_password
from app.db.mongo import DB, Doc, get_db
from app.schemas.common import Page
from app.schemas.misc import AdminUserCreate, AdminUserOut, AdminUserUpdate, AuditOut
from app.services.billing import get_billing
from app.services.email import get_email
from app.services.storage import get_storage

router = APIRouter(prefix="/admin", tags=["admin"])

ROLE_DESCRIPTIONS = {
    "admin": "Full access to everything",
    "client": "Client portal access",
    "staff": "Reserved for future team members",
}


def _uo(u: Doc) -> AdminUserOut:
    return AdminUserOut(
        id=u.id,
        email=u.get("email", ""),
        full_name=u.get("full_name", ""),
        role=u.get("role", ""),
        is_active=bool(u.get("is_active", True)),
        last_login_at=u.get("last_login_at"),
        created_at=u.get("created_at"),
    )


@router.get("/users", response_model=List[AdminUserOut])
def users(role: Optional[str] = None, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    filt: dict = {}
    if role:
        filt["role"] = role
    return [_uo(u) for u in db.users.find(filt, sort=[("created_at", -1), ("_id", -1)])]


@router.post("/users", response_model=AdminUserOut, status_code=201)
def create_user(body: AdminUserCreate, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    if db.users.find_one({"email": body.email.lower()}):
        raise HTTPException(status_code=409, detail="Email already exists")
    if body.role not in ("admin", "staff"):
        raise HTTPException(status_code=400, detail="Role must be admin or staff (clients register via /clients)")
    u = db.users.insert(
        {
            "email": body.email.lower(),
            "password_hash": hash_password(body.password),
            "full_name": body.full_name,
            "role": body.role,
            "is_active": True,
            "avatar_url": None,
            "phone": None,
            "timezone": "UTC",
            "last_login_at": None,
        }
    )
    audit(db, action="user.create", entity="user", user=user, after={"email": u.get("email"), "role": body.role})
    return _uo(u)


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(user_id: int, body: AdminUserUpdate, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    u = db.users.get(user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    data = body.model_dump(exclude_unset=True)
    if u.get("email") == settings.admin_email.lower() and any(k in data for k in ("role", "is_active", "password")):
        raise HTTPException(status_code=403, detail="The primary admin account is managed in the .env file and cannot be changed here.")
    changes: dict = {}
    if data.get("full_name"):
        changes["full_name"] = data["full_name"]
    if data.get("role"):
        if data["role"] not in ROLE_DESCRIPTIONS:
            raise HTTPException(status_code=400, detail="Unknown role")
        changes["role"] = data["role"]
    if "is_active" in data and data["is_active"] is not None:
        if u.id == user.id and not data["is_active"]:
            raise HTTPException(status_code=400, detail="You cannot deactivate yourself")
        changes["is_active"] = data["is_active"]
    if data.get("password"):
        changes["password_hash"] = hash_password(data["password"])
    if changes:
        u = db.users.update(u.id, changes)
    audit(db, action="user.update", entity="user", entity_id=u.id, user=user, after={k: v for k, v in data.items() if k != "password"})
    return _uo(u)


@router.get("/roles")
def roles(db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    counts: dict = {}
    for r in db.users.aggregate([{"$group": {"_id": "$role", "n": {"$sum": 1}}}]):
        counts[r.get("_id")] = r.get("n", 0)
    return [{"name": name, "description": desc, "users": counts.get(name, 0)} for name, desc in ROLE_DESCRIPTIONS.items()]


@router.get("/audit", response_model=Page[AuditOut])
def audit_log(
    action: Optional[str] = None,
    entity: Optional[str] = None,
    user_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, le=200),
    db: DB = Depends(get_db),
    user: Doc = Depends(require_admin),
):
    filt: dict = {}
    if action:
        filt["action"] = {"$regex": re.escape(action), "$options": "i"}
    if entity:
        filt["entity"] = entity
    if user_id:
        filt["user_id"] = user_id
    rows, total = db.audit_logs.paginate(filt, [("created_at", -1), ("_id", -1)], page, page_size)
    items = []
    for r in rows:
        data = r.public()
        data.setdefault("actor", "system")
        items.append(AuditOut.model_validate(data))
    return Page(items=items, total=total, page=page, page_size=page_size)


def _llm_provider_in_use() -> str:
    try:
        from app.agents.llm import ollama_available, provider

        if settings.llm_provider.lower() == "ollama":
            ollama_available()
        return provider()
    except Exception:  # pragma: no cover
        return "mock"


@router.get("/settings")
def system_settings(user: Doc = Depends(require_admin)):
    return {
        "app_name": settings.app_name,
        "app_env": settings.app_env,
        "app_url": settings.app_url,
        "llm": {
            "provider": _llm_provider_in_use(),
            "configured_provider": settings.llm_provider,
            "model": settings.llm_model_for("design"),
            "ollama_base_url": settings.ollama_base_url,
        },
        "admin_email": settings.admin_email,
        "built_by": "Nagateja Goli",
        "database": "mongodb",
        "storage": get_storage().name,
        "billing": get_billing().name,
        "email": get_email().name,
        "redis": bool(settings.redis_url),
        "agents_enabled": settings.agents_enabled,
        "auto_run_on_accept": settings.agent_auto_run_on_accept,
        "outreach_auto_send": settings.outreach_auto_send,
        "lead_provider": settings.lead_provider,
        "image_provider": settings.image_provider,
        "max_upload_mb": settings.max_upload_mb,
        "currency": settings.currency,
        "reporting_currency": settings.reporting_currency,
    }
