from __future__ import annotations

import re
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.audit import audit
from app.core.config import settings
from app.core.deps import require_admin
from app.core.jobs import enqueue_job
from app.db.mongo import DB, Doc, get_db, utcnow
from app.schemas.common import Page
from app.schemas.misc import (
    LeadConvertIn,
    LeadCreate,
    LeadGenerateIn,
    LeadOut,
    LeadUpdate,
    OutreachDraftIn,
    OutreachOut,
    OutreachSendIn,
)
from app.services.email import get_email

router = APIRouter(prefix="/leads", tags=["leads"])
outreach_router = APIRouter(prefix="/outreach", tags=["leads"])


def _lead_out(db: DB, lead: Doc, counts: Optional[Dict[int, int]] = None) -> LeadOut:
    data = lead.public()
    data.setdefault("analysis", {})
    data["analysis"] = data.get("analysis") or {}
    data["outreach_count"] = counts.get(lead.id, 0) if counts is not None else db.outreach.count({"lead_id": lead.id})
    return LeadOut.model_validate(data)


def _lead_outs(db: DB, rows: List[Doc]) -> List[LeadOut]:
    ids = [l.id for l in rows]
    counts: Dict[int, int] = {}
    if ids:
        for r in db.outreach.aggregate([{"$match": {"lead_id": {"$in": ids}}}, {"$group": {"_id": "$lead_id", "n": {"$sum": 1}}}]):
            counts[r["_id"]] = r["n"]
    return [_lead_out(db, l, counts) for l in rows]


def _outreach_out(db: DB, o: Doc, leads: Optional[Dict[int, Doc]] = None) -> OutreachOut:
    lead = (leads or {}).get(o.get("lead_id")) if leads is not None else db.leads.get(o.get("lead_id"))
    if lead is None and leads is not None:
        lead = db.leads.get(o.get("lead_id"))
    data = o.public()
    data["company_name"] = lead.get("company_name", "") if lead else ""
    data["contact_email"] = lead.get("contact_email") if lead else None
    data.setdefault("follow_up_count", 0)
    data.setdefault("generated_by", "agent")
    data.setdefault("channel", "email")
    return OutreachOut.model_validate(data)


def _outreach_outs(db: DB, rows: List[Doc]) -> List[OutreachOut]:
    leads = db.leads.by_ids({o.get("lead_id") for o in rows})
    return [_outreach_out(db, o, leads) for o in rows]


@router.get("", response_model=Page[LeadOut])
def list_leads(
    status: Optional[str] = None,
    q: Optional[str] = None,
    min_score: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, le=200),
    db: DB = Depends(get_db),
    user: Doc = Depends(require_admin),
):
    filt: dict = {}
    if status:
        filt["status"] = status
    if min_score is not None:
        filt["score"] = {"$gte": min_score}
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        filt["$or"] = [{"company_name": rx}, {"contact_email": rx}, {"industry": rx}]
    rows, total = db.leads.paginate(filt, [("score", -1), ("created_at", -1)], page, page_size)
    return Page(items=_lead_outs(db, rows), total=total, page=page, page_size=page_size)


@router.get("/stats")
def lead_stats(db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    leads = db.leads.find({}, projection={"status": 1, "score": 1})
    by_status: Dict[str, int] = {}
    for l in leads:
        by_status[l.get("status", "new")] = by_status.get(l.get("status", "new"), 0) + 1
    total = len(leads)
    converted = by_status.get("converted", 0)
    avg_score = (sum(float(l.get("score") or 0) for l in leads) / total) if total else 0.0
    sent = db.outreach.count({"status": {"$in": ["sent", "replied"]}})
    replied = db.outreach.count({"status": "replied"})
    return {
        "total": total,
        "by_status": by_status,
        "converted": converted,
        "conversion_rate": round(100 * converted / total, 1) if total else 0.0,
        "avg_score": round(avg_score, 1),
        "outreach_sent": sent,
        "replies": replied,
        "reply_rate": round(100 * replied / sent, 1) if sent else 0.0,
    }


@router.post("", response_model=LeadOut, status_code=201)
def create_lead(body: LeadCreate, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    lead = db.leads.insert({**body.model_dump(), "analysis": {}, "status": "new", "source": "manual", "client_id": None})
    audit(db, action="lead.create", entity="lead", user=user, after={"company": body.company_name})
    return _lead_out(db, lead)


@router.post("/generate")
def generate(body: LeadGenerateIn, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    enqueue_job("lead_generation", body.model_dump())
    audit(db, action="lead.generate", entity="lead", user=user, after=body.model_dump())
    return {"ok": True, "message": "Lead Agent queued"}


@router.post("/{lead_id}/convert")
def convert_lead(lead_id: int, body: LeadConvertIn, http_request: Request, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    """Turn a lead into a client account (+ optionally a request for the design they asked for).
    The client receives their login by email (SMTP) and the request enters the normal pipeline."""
    from app.core.security import hash_password, random_token
    from app.services import request_service as rs

    lead = db.leads.get(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if not lead.get("contact_email"):
        raise HTTPException(status_code=400, detail="Lead has no contact email; add one first")
    email = lead["contact_email"].lower()
    existing = db.users.find_one({"email": email})
    password = body.password or random_token(9)
    if existing:
        client = db.clients.find_one({"user_id": existing.id})
        if not client:
            raise HTTPException(status_code=409, detail="A non-client account already uses this email")
        created_account = False
    else:
        u = db.users.insert(
            {
                "email": email,
                "password_hash": hash_password(password),
                "full_name": lead.get("contact_name") or lead.get("company_name"),
                "role": "client",
                "is_active": True,
                "avatar_url": None,
                "phone": None,
                "timezone": "UTC",
                "last_login_at": None,
            }
        )
        client = db.clients.insert(
            {
                "user_id": u.id,
                "company_name": lead.get("company_name"),
                "website": lead.get("website"),
                "industry": lead.get("industry"),
                "brand_notes": lead.get("notes"),
                "drive_folder_id": None,
                "currency": body.currency.upper(),
                "status": "active",
                "onboarding_stage": "new",
            }
        )
        db.conversations.insert({"client_id": client.id, "last_message_at": None, "last_message_preview": None, "admin_unread": 0, "client_unread": 0})
        created_account = True
    db.leads.update(lead.id, {"status": "converted", "client_id": client.id})

    req_out = None
    slug = body.service_slug or (lead.get("analysis") or {}).get("interested_in")
    if slug:
        svc = db.services.find_one({"slug": slug})
        if svc:
            brief = {f["key"]: "" for f in (svc.get("form_schema") or [])}
            if "brand_name" in brief:
                brief["brand_name"] = lead.get("company_name")
            for f in svc.get("form_schema") or []:
                if f.get("required") and not brief.get(f["key"]):
                    brief[f["key"]] = lead.get("notes") or f"To be confirmed with {lead.get('company_name')}"
            req = rs.create_request(
                db,
                user=user,
                service_id=svc.id,
                service_slug=None,
                client_id=client.id,
                project_id=None,
                title=body.title or f"{svc.get('name')} for {lead.get('company_name')}",
                description=body.description or lead.get("notes"),
                brief=brief,
                priority="normal",
                file_ids=[],
                http_request=http_request,
            )
            req_out = {"id": req.id, "title": req.get("title"), "price_amount": float(req.get("price_amount") or 0), "price_currency": req.get("price_currency")}

    if body.send_email:
        login_url = f"{settings.app_url}/login"
        msg = (
            f"Hi {lead.get('contact_name') or lead.get('company_name')},\n\nYour Designflow account is ready.\n\nLogin: {login_url}\nEmail: {email}\n"
            + (f"Temporary password: {password}\n" if created_account else "")
            + (
                f"\nWe've opened a request for you: {req_out['title']} ({req_out['price_currency']} {req_out['price_amount']:,.0f}). "
                f"You can review it, pay and track progress in your portal.\n"
                if req_out
                else ""
            )
            + "\nBest,\nDesignflow"
        )
        get_email().send(email, "Your Designflow account", msg)
    audit(db, action="lead.convert", entity="lead", entity_id=lead.id, user=user, after={"client_id": client.id, "request": req_out})
    return {
        "client_id": client.id,
        "created_account": created_account,
        "email": email,
        "temporary_password": password if created_account else None,
        "request": req_out,
    }


@router.get("/{lead_id}", response_model=LeadOut)
def get_lead(lead_id: int, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    lead = db.leads.get(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return _lead_out(db, lead)


@router.patch("/{lead_id}", response_model=LeadOut)
def update_lead(lead_id: int, body: LeadUpdate, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    lead = db.leads.get(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    data = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if data:
        lead = db.leads.update(lead.id, data)
    audit(db, action="lead.update", entity="lead", entity_id=lead.id, user=user, after=data)
    return _lead_out(db, lead)


@router.delete("/{lead_id}")
def delete_lead(lead_id: int, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    if db.leads.get(lead_id):
        db.outreach.delete_many({"lead_id": lead_id})
        db.leads.delete(lead_id)
    return {"ok": True}


@router.get("/{lead_id}/outreach", response_model=List[OutreachOut])
def lead_outreach(lead_id: int, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    rows = db.outreach.find({"lead_id": lead_id}, sort=[("created_at", -1), ("_id", -1)])
    return _outreach_outs(db, rows)


# ---- Outreach ------------------------------------------------------------
@outreach_router.get("", response_model=Page[OutreachOut])
def list_outreach(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, le=200),
    db: DB = Depends(get_db),
    user: Doc = Depends(require_admin),
):
    filt: dict = {}
    if status:
        filt["status"] = status
    rows, total = db.outreach.paginate(filt, [("created_at", -1), ("_id", -1)], page, page_size)
    return Page(items=_outreach_outs(db, rows), total=total, page=page, page_size=page_size)


@outreach_router.post("/draft")
def draft(body: OutreachDraftIn, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    enqueue_job("outreach_draft", {"lead_ids": body.lead_ids, "tone": body.tone})
    audit(db, action="outreach.draft", entity="outreach", user=user, after=body.model_dump())
    return {"ok": True, "message": f"Outreach Agent drafting {len(body.lead_ids)} email(s)"}


@outreach_router.post("/send")
def send(body: OutreachSendIn, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    sent = 0
    email = get_email()
    for oid in body.outreach_ids:
        o = db.outreach.get(oid)
        if not o or o.get("status") == "sent":
            continue
        lead = db.leads.get(o.get("lead_id"))
        if not lead or not lead.get("contact_email"):
            continue
        ok = email.send(lead["contact_email"], o.get("subject") or "Hello", o.get("body") or "")
        if ok:
            db.outreach.update(o.id, {"status": "sent", "sent_at": utcnow()})
            if lead.get("status") == "new":
                db.leads.update(lead.id, {"status": "contacted"})
            sent += 1
    audit(db, action="outreach.send", entity="outreach", user=user, after={"ids": body.outreach_ids, "sent": sent})
    return {"ok": True, "sent": sent, "provider": email.name}


@outreach_router.get("/settings")
def outreach_settings(user: Doc = Depends(require_admin)):
    return {"auto_send": settings.outreach_auto_send, "email_provider": get_email().name}


@outreach_router.patch("/{outreach_id}", response_model=OutreachOut)
def update_outreach(
    outreach_id: int,
    status: Optional[str] = None,
    subject: Optional[str] = None,
    body: Optional[str] = None,
    reply_text: Optional[str] = None,
    db: DB = Depends(get_db),
    user: Doc = Depends(require_admin),
):
    o = db.outreach.get(outreach_id)
    if not o:
        raise HTTPException(status_code=404, detail="Outreach not found")
    changes: dict = {}
    if status:
        changes["status"] = status
    if subject is not None:
        changes["subject"] = subject
    if body is not None:
        changes["body"] = body
    if reply_text is not None:
        changes["reply_text"] = reply_text
        changes["status"] = "replied"
        lead = db.leads.get(o.get("lead_id"))
        if lead and lead.get("status") in ("new", "contacted"):
            db.leads.update(lead.id, {"status": "replied"})
    if changes:
        o = db.outreach.update(o.id, changes)
    return _outreach_out(db, o)
