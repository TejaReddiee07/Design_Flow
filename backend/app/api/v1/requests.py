from __future__ import annotations

import re
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.audit import audit
from app.core.deps import get_current_user, require_admin
from app.core.jobs import enqueue_job
from app.db.mongo import DB, Doc, get_db, parallel, utcnow
from app.models.enums import NotificationType
from app.schemas.common import Page
from app.schemas.requests import (
    DeliveryCreate,
    DeliveryOut,
    DesignCreate,
    DesignOut,
    RejectIn,
    RequestCreate,
    RequestDetail,
    RequestOut,
    RequestUpdate,
    RevisionCreate,
    RevisionOut,
    StatusIn,
)
from app.services import deliverables
from app.services import request_service as rs
from app.services.notification_service import broadcast_badges, broadcast_request_update, notify, notify_admins

router = APIRouter(prefix="/requests", tags=["requests"])


def _out(db: DB, req: Doc) -> RequestOut:
    return rs.request_out(db, req)


@router.get("", response_model=Page[RequestOut])
def list_requests(
    status: Optional[str] = None,
    service_id: Optional[int] = None,
    client_id: Optional[int] = None,
    project_id: Optional[int] = None,
    priority: Optional[str] = None,
    q: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: DB = Depends(get_db),
    user: Doc = Depends(get_current_user),
):
    flt: Dict = {}
    if not user.get("is_admin"):
        flt["client_id"] = user["client"].id if user.get("client") else -1
    elif client_id:
        flt["client_id"] = client_id
    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        flt["status"] = {"$in": statuses} if len(statuses) != 1 else statuses[0]
    if service_id:
        flt["service_id"] = service_id
    if project_id:
        flt["project_id"] = project_id
    if priority:
        flt["priority"] = priority
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        flt["$or"] = [{"title": rx}, {"description": rx}]
    rows, total = db.requests.paginate(flt, [("submitted_at", -1)], page, page_size)
    return Page(items=rs.request_outs(db, rows), total=total, page=page, page_size=page_size)


@router.post("", response_model=RequestOut, status_code=201)
def create_request(body: RequestCreate, http_request: Request, db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    req = rs.create_request(
        db,
        user=user,
        service_id=body.service_id,
        service_slug=body.service_slug,
        client_id=body.client_id,
        project_id=body.project_id,
        title=body.title,
        description=body.description,
        brief=body.brief,
        priority=body.priority.value,
        file_ids=body.file_ids,
        http_request=http_request,
    )
    return _out(db, req)


@router.get("/{request_id}", response_model=RequestDetail)
def get_request(request_id: int, db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    req = rs.get_request_or_404(db, request_id, user)
    return rs.request_detail(db, req, viewer=user)


@router.patch("/{request_id}", response_model=RequestOut)
def update_request(request_id: int, body: RequestUpdate, db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    req = rs.get_request_or_404(db, request_id, user)
    if not user.get("is_admin") and req.get("status") not in ("pending",):
        raise HTTPException(status_code=409, detail="Only pending requests can be edited")
    data = body.model_dump(exclude_unset=True)
    before = {k: req.get(k) for k in data}
    changes = {k: (v.value if hasattr(v, "value") else v) for k, v in data.items() if v is not None}
    if "project_id" in changes:
        project = db.projects.get(changes["project_id"])
        if not project or project.get("client_id") != req.get("client_id"):
            raise HTTPException(status_code=400, detail="Invalid project")
    if changes:
        req = db.requests.update(req.id, changes)
    audit(db, action="request.update", entity="service_request", entity_id=req.id, user=user, before=before, after=data)
    broadcast_request_update(db, req, {"event": "updated"})
    return _out(db, req)


@router.delete("/{request_id}")
def delete_request(request_id: int, db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    req = rs.get_request_or_404(db, request_id, user)
    if not user.get("is_admin") and req.get("status") != "pending":
        raise HTTPException(status_code=409, detail="Only pending requests can be withdrawn")
    audit(db, action="request.delete", entity="service_request", entity_id=req.id, user=user, before={"title": req.get("title")})
    sid = req.get("service_id")
    db.payments.delete_many({"request_id": req.id, "status": "pending"})
    db.designs.delete_many({"request_id": req.id})
    db.revisions.delete_many({"request_id": req.id})
    db.deliveries.delete_many({"request_id": req.id})
    db.files.update_many({"request_id": req.id}, {"request_id": None})
    db.requests.delete(req.id)
    broadcast_badges(db, highlight_service_id=sid)
    return {"ok": True}


# ---- Action buttons ------------------------------------------------------
@router.post("/{request_id}/accept", response_model=RequestOut)
def accept(request_id: int, http_request: Request, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    req = rs.get_request_or_404(db, request_id)
    return _out(db, rs.transition(db, req, "accepted", user=user, http_request=http_request))


@router.post("/{request_id}/reject", response_model=RequestOut)
def reject(request_id: int, http_request: Request, body: RejectIn = RejectIn(), db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    req = rs.get_request_or_404(db, request_id)
    return _out(db, rs.transition(db, req, "rejected", user=user, note=body.reason, http_request=http_request))


@router.post("/{request_id}/complete", response_model=RequestOut)
def complete(request_id: int, http_request: Request, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    req = rs.get_request_or_404(db, request_id)
    return _out(db, rs.transition(db, req, "completed", user=user, http_request=http_request, force=True))


@router.post("/{request_id}/start", response_model=RequestOut)
def start(request_id: int, http_request: Request, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    req = rs.get_request_or_404(db, request_id)
    return _out(db, rs.transition(db, req, "in_progress", user=user, http_request=http_request, force=True))


@router.post("/{request_id}/review", response_model=RequestOut)
def to_review(request_id: int, http_request: Request, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    req = rs.get_request_or_404(db, request_id)
    return _out(db, rs.transition(db, req, "review", user=user, http_request=http_request, force=True))


@router.post("/{request_id}/status", response_model=RequestOut)
def set_status(request_id: int, body: StatusIn, http_request: Request, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    req = rs.get_request_or_404(db, request_id)
    return _out(db, rs.transition(db, req, body.status.value, user=user, note=body.note, http_request=http_request, force=True))


@router.post("/{request_id}/run-pipeline", response_model=RequestOut)
def run_pipeline(request_id: int, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    req = rs.get_request_or_404(db, request_id)
    if req.get("status") == "pending":
        req = rs.transition(db, req, "accepted", user=user)
    else:
        enqueue_job("request_pipeline", {"request_id": req.id})
    return _out(db, req)


@router.post("/{request_id}/approve", response_model=RequestOut)
def approve(
    request_id: int,
    http_request: Request,
    design_id: Optional[int] = None,
    message: Optional[str] = None,
    db: DB = Depends(get_db),
    user: Doc = Depends(require_admin),
):
    """Admin approval step of the pipeline: approve the latest (or given) design and deliver."""
    req = rs.get_request_or_404(db, request_id)
    design = db.designs.get(design_id) if design_id else db.designs.find_one({"request_id": req.id}, sort=[("version", -1)])
    if design and design.get("request_id") == req.id:
        db.designs.update(design.id, {"status": "approved"})
    audit(db, action="request.approve", entity="service_request", entity_id=req.id, user=user, after={"design_id": design.id if design else None}, request=http_request)
    req = db.requests.update(req.id, {"pipeline_stage": "approved"})
    enqueue_job("request_resume", {"request_id": req.id, "approved": True, "message": message or ""})
    broadcast_request_update(db, req, {"event": "approved"})
    return _out(db, req)


@router.post("/{request_id}/rework", response_model=RequestOut)
def rework(request_id: int, http_request: Request, message: Optional[str] = None, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    """Admin sends the draft back: the Design Agent reworks it with the note, QA runs again, then it returns for approval."""
    req = rs.get_request_or_404(db, request_id)
    if req.get("status") not in ("review", "in_progress", "accepted"):
        raise HTTPException(status_code=400, detail="Only a request in review or in progress can be sent back for rework")
    audit(db, action="request.rework", entity="service_request", entity_id=req.id, user=user, after={"message": message or ""}, request=http_request)
    req = db.requests.update(req.id, {"pipeline_stage": "rework"})
    enqueue_job("request_resume", {"request_id": req.id, "approved": False, "message": message or ""})
    broadcast_request_update(db, req, {"event": "rework"})
    return _out(db, req)


@router.get("/{request_id}/live")
def live_state(request_id: int, since_id: Optional[int] = None, db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    """Everything the "See in live" page needs: the request, the agents, the stored event feed and the recent logs."""
    from app.agents import control, live
    from app.agents import llm as llm_mod
    from app.core.config import settings

    req = rs.get_request_or_404(db, request_id, user)
    detail_model, agent_rows, logs, events = parallel(
        lambda: rs.request_detail(db, req),
        lambda: db.agents.find({"key": {"$in": live.PIPELINE_AGENTS}}, sort=[("sort_order", 1)]),
        lambda: db.agent_logs.find({"request_id": req.id}, sort=[("_id", -1)], limit=150),
        lambda: live.events_for(db, req.id, since_id=since_id),
    )
    detail = detail_model.model_dump(mode="json")
    agents = [control.agent_dict(a) for a in agent_rows]
    provider = llm_mod.provider()
    return {
        "request": detail,
        "agents": agents,
        "events": events,
        "logs": [
            {
                "id": l.id, "agent_key": l.get("agent_key"), "run_id": l.get("run_id"), "step": l.get("step"), "status": l.get("status"),
                "level": l.get("level"), "message": l.get("message"), "output_summary": l.get("output_summary"), "tokens_in": l.get("tokens_in", 0),
                "tokens_out": l.get("tokens_out", 0), "duration_ms": l.get("duration_ms", 0), "created_at": l["created_at"].isoformat() if l.get("created_at") else None,
            }
            for l in reversed(logs)
        ],
        "llm": {"provider": provider, "model": settings.llm_model_for("design") if provider != "mock" else "mock"},
        "server_time": utcnow().isoformat(),
    }


# ---- Payment -------------------------------------------------------------
def _checkout_names(db: DB, req: Doc) -> tuple[str, str]:
    client = db.clients.get(req.get("client_id"))
    cuser = db.users.get(client.get("user_id")) if client else None
    service = db.services.get(req.get("service_id"))
    return (cuser.get("email", "") if cuser else "", f"{service.get('name') if service else 'Design'}: {req.get('title')}")


@router.post("/{request_id}/pay")
def pay(request_id: int, http_request: Request, db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    """Client pays for this request. Mock provider settles instantly; Stripe returns a checkout_url."""
    from app.core.config import settings
    from app.services.billing import get_billing

    req = rs.get_request_or_404(db, request_id, user)
    if req.get("is_paid"):
        return {"paid": True, "checkout_url": None, "request": _out(db, req).model_dump(mode="json")}
    if not req.get("price_amount") or float(req["price_amount"]) <= 0:
        req = rs.mark_paid(db, req, provider="free", user=user)
        return {"paid": True, "checkout_url": None, "request": _out(db, req).model_dump(mode="json")}
    provider = get_billing()
    # Send the client back to the same origin they are using (localhost vs 127.0.0.1 vs the public domain).
    origin = (http_request.headers.get("origin") or "").rstrip("/") or settings.app_url.rstrip("/")
    customer_email, product_name = _checkout_names(db, req)
    result = provider.create_request_checkout(
        request_id=req.id, client_id=req.get("client_id"), customer_email=customer_email, product_name=product_name,
        amount=float(req["price_amount"]), currency=req.get("price_currency") or "USD",
        success_url=f"{origin}/portal#/requests/{req.id}?payment=success",
        cancel_url=f"{origin}/portal#/requests/{req.id}?payment=cancel",
    )
    audit(db, action="request.checkout", entity="service_request", entity_id=req.id, user=user, after={"provider": result.provider}, request=http_request)
    if result.paid:
        req = rs.mark_paid(db, req, provider=result.provider, provider_payment_id=result.provider_payment_id, user=user)
    return {"paid": result.paid, "checkout_url": result.checkout_url, "provider": result.provider, "request": _out(db, req).model_dump(mode="json")}


@router.post("/{request_id}/confirm-payment")
def confirm_payment(request_id: int, session_id: str, db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    """Called when the client returns from Stripe Checkout: verify the session and settle the invoice."""
    from app.services.billing import get_billing

    req = rs.get_request_or_404(db, request_id, user)
    if req.get("is_paid"):
        return {"paid": True, "request": _out(db, req).model_dump(mode="json")}
    try:
        info = get_billing().verify_session(session_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not verify payment: {exc}")
    if info.get("paid") and (not info.get("request_id") or int(info["request_id"]) == req.id):
        req = rs.mark_paid(db, req, provider=get_billing().name, provider_payment_id=info.get("payment_id"), user=user, amount=float(info.get("amount") or 0) or None)
    return {"paid": bool(req.get("is_paid")), "request": _out(db, req).model_dump(mode="json")}


@router.post("/{request_id}/mark-paid", response_model=RequestOut)
def mark_paid(request_id: int, note: Optional[str] = None, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    """Admin records an offline payment (bank transfer, cash, etc.)."""
    req = rs.get_request_or_404(db, request_id)
    return _out(db, rs.mark_paid(db, req, provider="manual", provider_payment_id=note, user=user))


# ---- Designs -------------------------------------------------------------
def _design_out(d: Doc) -> DesignOut:
    return DesignOut.model_validate(d.public())


@router.get("/{request_id}/designs", response_model=List[DesignOut])
def designs(request_id: int, db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    req = rs.get_request_or_404(db, request_id, user)
    return [_design_out(d) for d in db.designs.find({"request_id": req.id}, sort=[("version", 1)])]


@router.post("/{request_id}/designs", response_model=DesignOut, status_code=201)
def add_design(request_id: int, body: DesignCreate, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    req = rs.get_request_or_404(db, request_id)
    last = db.designs.find_one({"request_id": req.id}, sort=[("version", -1)])
    version = (int(last.get("version", 0)) + 1) if last else 1
    d = db.designs.insert(
        {"request_id": req.id, "version": version, "title": body.title or f"Design v{version}", "concept": body.concept,
         "concept_data": body.concept_data, "file_id": body.file_id, "preview_url": body.preview_url,
         "generated_by": "human", "status": "draft", "qa_score": None, "qa_notes": None}
    )
    audit(db, action="design.create", entity="design", entity_id=d.id, user=user, after={"request_id": req.id, "version": version})
    broadcast_request_update(db, req, {"event": "design", "design_id": d.id})
    return _design_out(d)


@router.post("/{request_id}/designs/{design_id}/approve", response_model=DesignOut)
def approve_design(request_id: int, design_id: int, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    d = db.designs.get(design_id)
    if not d or d.get("request_id") != request_id:
        raise HTTPException(status_code=404, detail="Design not found")
    return _design_out(db.designs.update(d.id, {"status": "approved"}))


# ---- Revisions -----------------------------------------------------------
def _revision_out(r: Doc) -> RevisionOut:
    return RevisionOut.model_validate(r.public())


@router.get("/{request_id}/revisions", response_model=List[RevisionOut])
def revisions(request_id: int, db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    req = rs.get_request_or_404(db, request_id, user)
    return [_revision_out(r) for r in db.revisions.find({"request_id": req.id}, sort=[("round", 1)])]


@router.post("/{request_id}/revisions", response_model=RevisionOut, status_code=201)
def request_revision(request_id: int, body: RevisionCreate, http_request: Request, db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    req = rs.get_request_or_404(db, request_id, user)
    if req.get("status") not in ("completed", "review", "in_progress"):
        raise HTTPException(status_code=409, detail="Revisions can be requested once work has been delivered")
    rnd = int(req.get("revision_count") or 0) + 1
    rev = db.revisions.insert(
        {"request_id": req.id, "design_id": body.design_id, "round": rnd, "feedback": body.feedback, "change_items": [],
         "status": "pending", "submitted_by": user.id, "file_ids": body.file_ids, "resolved_at": None}
    )
    req = db.requests.update(req.id, {"revision_count": rnd})
    if body.file_ids:
        db.files.update_many({"_id": {"$in": [int(i) for i in body.file_ids]}}, {"request_id": req.id, "kind": "revision"})
    audit(db, action="revision.create", entity="revision", entity_id=rev.id, user=user, after={"request_id": req.id, "round": rnd}, request=http_request)
    notify_admins(
        db, type=NotificationType.REVISION.value, title=f"Revision requested: {req.get('title')}",
        body=f"Round {rnd}: {body.feedback[:140]}", link=f"/admin#/requests/{req.id}",
        service_id=req.get("service_id"), request_id=req.id,
    )
    rs.transition(db, req, "in_progress", user=user, note=f"Revision round {rnd}", force=True)
    enqueue_job("revision_pipeline", {"request_id": req.id, "revision_id": rev.id})
    return _revision_out(rev)


@router.patch("/{request_id}/revisions/{revision_id}", response_model=RevisionOut)
def update_revision(request_id: int, revision_id: int, status: str = Query(...), db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    rev = db.revisions.get(revision_id)
    if not rev or rev.get("request_id") != request_id:
        raise HTTPException(status_code=404, detail="Revision not found")
    changes = {"status": status}
    if status == "completed":
        changes["resolved_at"] = utcnow()
    return _revision_out(db.revisions.update(rev.id, changes))


# ---- Deliveries ----------------------------------------------------------
def _delivery_out(d: Doc) -> DeliveryOut:
    return DeliveryOut.model_validate(d.public())


@router.get("/{request_id}/deliveries", response_model=List[DeliveryOut])
def deliveries(request_id: int, db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    req = rs.get_request_or_404(db, request_id, user)
    rows = db.deliveries.find({"request_id": req.id}, sort=[("_id", 1)])
    if user.get("is_admin"):
        return [_delivery_out(d) for d in rows]
    return rs.client_deliveries(db, req, rows)


@router.post("/{request_id}/deliveries", response_model=DeliveryOut, status_code=201)
def create_delivery(request_id: int, body: DeliveryCreate, http_request: Request, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    req = rs.get_request_or_404(db, request_id)
    files = db.files.find({"_id": {"$in": [int(i) for i in body.file_ids]}}) if body.file_ids else []
    if files:
        db.files.update_many({"_id": {"$in": [f.id for f in files]}}, {"request_id": req.id, "kind": "delivery"})
    links = [{"name": f.get("original_name"), "url": f"/api/v1/files/{f.id}/download", "file_id": f.id} for f in files]
    version = db.deliveries.count({"request_id": req.id}) + 1
    d = db.deliveries.insert(
        {"request_id": req.id, "message": body.message, "file_ids": [f.id for f in files], "download_links": links,
         "delivered_by": "admin", "version": version, "delivered_at": utcnow()}
    )
    deliverables.invalidate(req.get("client_id"))
    audit(db, action="delivery.create", entity="delivery", entity_id=d.id, user=user, after={"request_id": req.id, "files": len(files)}, request=http_request)
    client = db.clients.get(req.get("client_id"))
    if client and client.get("user_id"):
        notify(db, [client["user_id"]], type=NotificationType.DELIVERY.value, title=f"Delivered: {req.get('title')}",
               body=body.message or "Your files are ready to download.", link=f"/portal#/requests/{req.id}",
               service_id=req.get("service_id"), request_id=req.id)
    if body.mark_completed:
        rs.transition(db, req, "completed", user=user, force=True)
    else:
        broadcast_request_update(db, req, {"event": "delivery"})
    return _delivery_out(d)
