from __future__ import annotations

import re
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.audit import audit
from app.core.deps import get_current_user, require_admin
from app.core.naming import company_or_name
from app.core.security import hash_password
from app.db.mongo import DB, Doc, get_db
from app.schemas.clients import ClientCreate, ClientOut, ClientOverview, ClientUpdate
from app.schemas.common import Page

router = APIRouter(prefix="/clients", tags=["clients"])
ACTIVE_STATUSES = ["accepted", "in_progress", "review"]


def client_out(db: DB, c: Doc, user: Optional[Doc] = None) -> ClientOut:
    user = user or db.users.get(c.get("user_id"))
    reqs = db.requests.find({"client_id": c.id}, projection={"status": 1, "is_paid": 1})
    paid = db.payments.find({"client_id": c.id, "status": "paid"}, projection={"amount": 1})
    return ClientOut(
        id=c.id,
        user_id=c.get("user_id"),
        email=user.get("email", "") if user else "",
        full_name=user.get("full_name", "") if user else "",
        company_name=c.get("company_name", ""),
        website=c.get("website"),
        industry=c.get("industry"),
        brand_notes=c.get("brand_notes"),
        drive_folder_id=c.get("drive_folder_id"),
        currency=c.get("currency") or "USD",
        status=c.get("status", "active"),
        onboarding_stage=c.get("onboarding_stage", "new"),
        active_requests=sum(1 for r in reqs if r.get("status") in ACTIVE_STATUSES),
        unpaid_requests=sum(1 for r in reqs if not r.get("is_paid") and r.get("status") != "rejected"),
        total_requests=len(reqs),
        total_paid=float(sum(float(p.get("amount") or 0) for p in paid)),
        created_at=c.get("created_at"),
        last_login_at=user.get("last_login_at") if user else None,
    )


@router.get("", response_model=Page[ClientOut])
def list_clients(
    q: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: DB = Depends(get_db),
    user: Doc = Depends(require_admin),
):
    flt: Dict = {}
    if status:
        flt["status"] = status
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        matching_users = db.users.find({"$or": [{"email": rx}, {"full_name": rx}]}, projection={"_id": 1})
        flt["$or"] = [{"company_name": rx}, {"user_id": {"$in": [u.id for u in matching_users]}}]
    rows, total = db.clients.paginate(flt, [("created_at", -1)], page, page_size)
    users = db.users.by_ids({c.get("user_id") for c in rows})
    return Page(items=[client_out(db, c, users.get(c.get("user_id"))) for c in rows], total=total, page=page, page_size=page_size)


@router.post("", response_model=ClientOut, status_code=201)
def create_client(body: ClientCreate, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    email = body.email.lower()
    if db.users.exists({"email": email}):
        raise HTTPException(status_code=409, detail="Email already registered")
    u = db.users.insert({"email": email, "password_hash": hash_password(body.password), "full_name": body.full_name, "role": "client",
                         "is_active": True, "avatar_url": None, "phone": None, "timezone": "UTC", "last_login_at": None})
    c = db.clients.insert({"user_id": u.id, "company_name": company_or_name(body.company_name, body.full_name), "website": body.website, "industry": body.industry,
                           "brand_notes": body.brand_notes, "drive_folder_id": None, "currency": body.currency.upper(), "status": "active", "onboarding_stage": "new"})
    db.conversations.insert({"client_id": c.id, "last_message_at": None, "last_message_preview": None, "admin_unread": 0, "client_unread": 0})
    audit(db, action="client.create", entity="client", entity_id=c.id, user=user, after={"email": email})
    return client_out(db, c, u)


@router.get("/me", response_model=ClientOut)
def my_client(db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    if not user.get("client"):
        raise HTTPException(status_code=404, detail="No client profile")
    return client_out(db, user["client"], user)


@router.get("/{client_id}", response_model=ClientOut)
def get_client(client_id: int, db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    if not user.get("is_admin") and (not user.get("client") or user["client"].id != client_id):
        raise HTTPException(status_code=403, detail="Forbidden")
    c = db.clients.get(client_id)
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    return client_out(db, c)


@router.patch("/{client_id}", response_model=ClientOut)
def update_client(client_id: int, body: ClientUpdate, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    c = db.clients.get(client_id)
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    data = body.model_dump(exclude_unset=True)
    before: Dict = {}
    changes: Dict = {}
    for k, v in data.items():
        if k == "is_active":
            if v is not None:
                u = db.users.get(c.get("user_id"))
                before[k] = u.get("is_active") if u else None
                if u:
                    db.users.update(u.id, {"is_active": v})
        elif v is not None:
            before[k] = c.get(k)
            changes[k] = v.upper() if k == "currency" else v
    if "company_name" in changes:
        owner = db.users.get(c.get("user_id"))
        changes["company_name"] = company_or_name(changes["company_name"], owner.get("full_name") if owner else "")
    if changes:
        c = db.clients.update(c.id, changes)
    audit(db, action="client.update", entity="client", entity_id=c.id, user=user, before=before, after=data)
    return client_out(db, c)


@router.delete("/{client_id}")
def delete_client(client_id: int, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    c = db.clients.get(client_id)
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    audit(db, action="client.delete", entity="client", entity_id=c.id, user=user, before={"company": c.get("company_name")})
    if c.get("user_id"):
        db.refresh_tokens.delete_many({"user_id": c["user_id"]})
        db.notifications.delete_many({"user_id": c["user_id"]})
        db.users.delete(c["user_id"])
    conv = db.conversations.find_one({"client_id": c.id})
    if conv:
        db.messages.delete_many({"conversation_id": conv.id})
        db.conversations.delete(conv.id)
    db.clients.delete(c.id)
    return {"ok": True}


@router.get("/{client_id}/overview", response_model=ClientOverview)
def client_overview(client_id: int, db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    if not user.get("is_admin") and (not user.get("client") or user["client"].id != client_id):
        raise HTTPException(status_code=403, detail="Forbidden")
    c = db.clients.get(client_id)
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    reqs = db.requests.find({"client_id": c.id}, sort=[("submitted_at", -1)])
    services = db.services.by_ids({r.get("service_id") for r in reqs})
    by_status: Dict[str, int] = {}
    for r in reqs:
        by_status[r.get("status", "pending")] = by_status.get(r.get("status", "pending"), 0) + 1
    payments = db.payments.find({"client_id": c.id}, sort=[("created_at", -1)], limit=12)
    assets = db.assets.find({"client_id": c.id})
    projects = db.projects.find({"client_id": c.id})
    return ClientOverview(
        client=client_out(db, c),
        requests_by_status=by_status,
        recent_requests=[{"id": r.id, "title": r.get("title"), "status": r.get("status"), "service": (services.get(r.get("service_id")) or {}).get("name", ""),
                          "priority": r.get("priority"), "submitted_at": r.get("submitted_at")} for r in reqs[:10]],
        payments=[{"id": p.id, "amount": float(p.get("amount") or 0), "currency": p.get("currency"), "status": p.get("status"),
                   "invoice_number": p.get("invoice_number"), "paid_at": p.get("paid_at"), "description": p.get("description")} for p in payments],
        brand_assets=[{"id": a.id, "type": a.get("type"), "name": a.get("name"), "value": a.get("value"), "file_id": a.get("file_id")} for a in assets],
        projects=[{"id": p.id, "name": p.get("name"), "status": p.get("status")} for p in projects],
    )
