"""Request lifecycle: creation, status transitions, payment, timeline, API serialisation."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, Request

from app.core.audit import audit
from app.core.config import settings
from app.core.jobs import enqueue_job
from app.db.mongo import DB, Doc, parallel
from app.models.enums import NotificationType
from app.schemas.requests import DeliveryOut, DesignOut, RequestDetail, RequestOut, RevisionOut
from app.services.file_service import file_to_dict
from app.services.notification_service import broadcast_badges, broadcast_request_update, notify, notify_admins

ALLOWED: Dict[str, set] = {
    "pending": {"accepted", "rejected", "completed"},
    "accepted": {"in_progress", "review", "rejected", "completed", "pending"},
    "in_progress": {"review", "completed", "accepted"},
    "review": {"completed", "in_progress"},
    "rejected": {"pending", "accepted"},
    "completed": {"in_progress", "review"},
}
OPEN_STATUSES = ["pending", "accepted", "in_progress", "review"]
STATUS_LABEL = {"pending": "Pending", "accepted": "Accepted", "rejected": "Rejected", "in_progress": "In Progress", "review": "In Review", "completed": "Completed"}


def now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# loading / serialising
# ---------------------------------------------------------------------------
def get_request_or_404(db: DB, request_id: int, user: Optional[Doc] = None) -> Doc:
    req = db.requests.get(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if user is not None and not user.get("is_admin"):
        client = user.get("client")
        if not client or req.client_id != client.id:
            raise HTTPException(status_code=404, detail="Request not found")
    return req


def request_out(db: DB, req: Doc, *, client: Optional[Doc] = None, service: Optional[Doc] = None, user: Optional[Doc] = None, project: Optional[Doc] = None) -> RequestOut:
    # Independent lookups run concurrently: one database round trip instead of three.
    client, service, project = parallel(
        lambda: client or db.clients.get(req.get("client_id")),
        lambda: service or db.services.get(req.get("service_id")),
        lambda: project or (db.projects.get(req["project_id"]) if req.get("project_id") else None),
    )
    cuser = user or (db.users.get(client.user_id) if client else None)
    return RequestOut(
        id=req.id,
        client_id=req.get("client_id"),
        client_name=cuser.get("full_name", "") if cuser else "",
        company_name=client.get("company_name", "") if client else "",
        project_id=req.get("project_id"),
        project_name=project.get("name") if project else None,
        service_id=req.get("service_id"),
        service_name=service.get("name", "") if service else "",
        service_slug=service.get("slug", "") if service else "",
        title=req.get("title", ""),
        description=req.get("description"),
        brief=req.get("brief") or {},
        priority=req.get("priority", "normal"),
        status=req.get("status", "pending"),
        pipeline_stage=req.get("pipeline_stage"),
        ai_summary=req.get("ai_summary"),
        submitted_at=req.get("submitted_at"),
        accepted_at=req.get("accepted_at"),
        started_at=req.get("started_at"),
        review_at=req.get("review_at"),
        completed_at=req.get("completed_at"),
        rejected_at=req.get("rejected_at"),
        rejection_reason=req.get("rejection_reason"),
        due_at=req.get("due_at"),
        revision_count=int(req.get("revision_count") or 0),
        price_amount=float(req["price_amount"]) if req.get("price_amount") is not None else None,
        price_currency=req.get("price_currency") or "USD",
        is_paid=bool(req.get("is_paid")),
        paid_at=req.get("paid_at"),
        turnaround_days=int(service.get("turnaround_days", 0)) if service else 0,
        created_at=req.get("created_at"),
        updated_at=req.get("updated_at"),
    )


def request_outs(db: DB, reqs: List[Doc]) -> List[RequestOut]:
    """Serialise many requests with batched, concurrent lookups (two round trips for any page size)."""
    clients, services, projects = parallel(
        lambda: db.clients.by_ids({r.get("client_id") for r in reqs}),
        lambda: db.services.by_ids({r.get("service_id") for r in reqs}),
        lambda: db.projects.by_ids({r.get("project_id") for r in reqs if r.get("project_id")}),
    )
    users = db.users.by_ids({c.get("user_id") for c in clients.values()})
    out = []
    for r in reqs:
        c = clients.get(r.get("client_id"))
        out.append(request_out(db, r, client=c, service=services.get(r.get("service_id")), user=users.get(c.get("user_id")) if c else None, project=projects.get(r.get("project_id"))))
    return out


def client_deliveries(db: DB, req: Doc, rows: List[Doc], service: Optional[Doc] = None) -> List[DeliveryOut]:
    """Deliveries as the client sees them: only the designs they ordered, in the service's formats."""
    from app.services import deliverables

    service = service if service is not None else db.services.get(req.get("service_id"))
    slug = (service or {}).get("slug") or ""
    out: List[DeliveryOut] = []
    for d in rows:
        items = deliverables.for_delivery(d, slug, req.get("brief"))
        ids = [int(i["file_id"]) for i in items]
        links = [{"name": i.get("name"), "url": f"/api/v1/files/{i['file_id']}/download", "file_id": i["file_id"]} for i in items]
        package = d.get("package_file_id") if d.get("selected") else None
        if package:
            pkg = next((l for l in (d.get("download_links") or []) if isinstance(l, dict) and l.get("file_id") == package), None)
            if pkg:
                links.insert(0, pkg)
        out.append(DeliveryOut.model_validate({**d.public(), "file_ids": ids, "download_links": links, "files": items, "package_file_id": package}))
    return out


def request_detail(db: DB, req: Doc, viewer: Optional[Doc] = None) -> RequestDetail:
    # Everything the detail page needs, fetched concurrently (two round trips instead of eleven).
    client, service, project, designs, revisions, deliveries, files, logs = parallel(
        lambda: db.clients.get(req.get("client_id")),
        lambda: db.services.get(req.get("service_id")),
        lambda: db.projects.get(req["project_id"]) if req.get("project_id") else None,
        lambda: db.designs.find({"request_id": req.id}, sort=[("version", 1)]),
        lambda: db.revisions.find({"request_id": req.id}, sort=[("round", 1)]),
        lambda: db.deliveries.find({"request_id": req.id}, sort=[("_id", 1)]),
        lambda: db.files.find({"request_id": req.id}, sort=[("_id", 1)]),
        lambda: db.agent_logs.find({"request_id": req.id}, sort=[("created_at", 1)], limit=100),
    )
    cuser = db.users.get(client.user_id) if client else None
    base = request_out(db, req, client=client, service=service, user=cuser, project=project).model_dump()
    if viewer is not None and not viewer.get("is_admin"):
        # The client sees the designs delivered to them, never studio drafts, boards, sources or notes.
        from app.services import deliverables

        slug = (service or {}).get("slug") or ""
        dels = client_deliveries(db, req, deliveries, service)
        visible = {fid for dl in dels for fid in dl.file_ids} | {dl.package_file_id for dl in dels if dl.package_file_id}
        visible |= {int(i["thumb_file_id"]) for dl in dels for i in dl.files if i.get("thumb_file_id")}
        delivered_designs = {dl.design_id for dl in dels if dl.design_id}
        designs_out = []
        for d in designs:
            if d.id not in delivered_designs:
                continue
            items = [i for i in deliverables.select(slug, req.get("brief"), d.get("files") or []) if int(i.get("file_id") or 0) in visible]
            cover = next((i for i in items if (i.get("format") or "").lower() in ("png", "jpg", "jpeg", "webp")), None)
            designs_out.append(DesignOut.model_validate({**d.public(), "file_id": cover["file_id"] if cover else None, "preview_url": None,
                                                         "files": items, "package_file_id": None}))

        def _shown(f: Doc) -> bool:
            if f.get("kind") not in ("design", "delivery", "thumb"):
                return True
            if f.get("kind") == "delivery" and not (f.get("meta") or {}).get("role"):
                return True
            return f.id in visible

        return RequestDetail(
            **base,
            designs=designs_out,
            revisions=[RevisionOut.model_validate(r.public()) for r in revisions],
            deliveries=dels,
            files=[file_to_dict(f) for f in files if f.get("kind") != "thumb" and _shown(f)],
            timeline=timeline(db, req, designs=designs, revisions=revisions, deliveries=deliveries, service=service, logs=logs),
        )
    return RequestDetail(
        **base,
        designs=[DesignOut.model_validate(d.public()) for d in designs],
        revisions=[RevisionOut.model_validate(r.public()) for r in revisions],
        deliveries=[DeliveryOut.model_validate(d.public()) for d in deliveries],
        files=[file_to_dict(f) for f in files],
        timeline=timeline(db, req, designs=designs, revisions=revisions, deliveries=deliveries, service=service, logs=logs),
    )


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------
def create_request(
    db: DB,
    *,
    user: Doc,
    service_id: Optional[int],
    service_slug: Optional[str],
    client_id: Optional[int],
    project_id: Optional[int],
    title: str,
    description: Optional[str],
    brief: Dict[str, Any],
    priority: str,
    file_ids: List[int],
    http_request: Optional[Request] = None,
) -> Doc:
    if user.get("is_admin"):
        if not client_id:
            raise HTTPException(status_code=400, detail="client_id is required for admin-created requests")
        client = db.clients.get(client_id)
    else:
        client = user.get("client")
    if not client:
        raise HTTPException(status_code=400, detail="Client not found")

    service = db.services.get(service_id) if service_id else (db.services.find_one({"slug": service_slug}) if service_slug else None)
    if not service or not service.get("is_active", True):
        raise HTTPException(status_code=400, detail="Unknown or inactive service")

    missing = [f["label"] for f in (service.get("form_schema") or []) if f.get("required") and not str(brief.get(f["key"], "") or "").strip()]
    if missing:
        raise HTTPException(status_code=422, detail=f"Missing required fields: {', '.join(missing)}")

    if project_id:
        project = db.projects.get(project_id)
        if not project or project.client_id != client.id:
            raise HTTPException(status_code=400, detail="Invalid project")

    currency = (client.get("currency") or settings.default_currency).upper()
    price = settings.convert_price(float(service.get("starting_price") or 0), currency)
    ts = now()
    req = db.requests.insert(
        {
            "client_id": client.id,
            "project_id": project_id,
            "service_id": service.id,
            "title": title.strip(),
            "description": description,
            "brief": brief,
            "priority": priority,
            "status": "pending",
            "submitted_at": ts,
            "accepted_at": None, "started_at": None, "review_at": None, "completed_at": None, "rejected_at": None,
            "rejection_reason": None,
            "due_at": ts + timedelta(days=int(service.get("turnaround_days") or 2)),
            "revision_count": 0,
            "price_amount": price,
            "price_currency": currency,
            "is_paid": price <= 0,
            "paid_at": None,
            "current_run_id": None,
            "pipeline_stage": None,
            "ai_summary": None,
        }
    )
    if price > 0:
        db.payments.insert(
            {
                "client_id": client.id, "request_id": req.id, "amount": price, "currency": currency,
                "settled_amount": None, "settled_currency": settings.reporting_currency,
                "provider": "pending", "status": "pending", "provider_payment_id": None,
                "invoice_number": f"INV-{ts:%Y%m%d}-{req.id:04d}", "invoice_url": None,
                "description": f"{service['name']}: {req['title']}", "paid_at": None,
            }
        )
    if file_ids:
        for f in db.files.find({"_id": {"$in": [int(i) for i in file_ids]}}):
            if user.get("is_admin") or f.get("owner_user_id") == user.id or f.get("client_id") == client.id:
                db.files.update(f.id, {"request_id": req.id, "client_id": client.id})
    audit(db, action="request.create", entity="service_request", entity_id=req.id, user=user, after={"title": req.title, "service": service.slug}, request=http_request)
    notify_admins(
        db,
        type=NotificationType.NEW_REQUEST.value,
        title=f"New request: {req.title}",
        body=f"{client.company_name} submitted a {service.name} request ({priority} priority).",
        link=f"/admin#/requests/{req.id}",
        service_id=service.id,
        request_id=req.id,
        data={"client_id": client.id, "priority": priority},
    )
    broadcast_badges(db, highlight_service_id=service.id)
    broadcast_request_update(db, req, {"event": "created"})
    enqueue_job("project_manager_triage", {"request_id": req.id})
    return req


# ---------------------------------------------------------------------------
# transitions
# ---------------------------------------------------------------------------
def transition(
    db: DB,
    req: Doc,
    new_status: str,
    *,
    user: Optional[Doc] = None,
    note: Optional[str] = None,
    actor: Optional[str] = None,
    http_request: Optional[Request] = None,
    force: bool = False,
) -> Doc:
    old = req.get("status")
    if old == new_status:
        return req
    if not force and new_status not in ALLOWED.get(old, set()):
        raise HTTPException(status_code=409, detail=f"Cannot move request from {old} to {new_status}")

    ts = now()
    changes: Dict[str, Any] = {"status": new_status}
    if new_status == "accepted":
        changes.update(accepted_at=ts, rejected_at=None, rejection_reason=None)
    elif new_status == "rejected":
        changes.update(rejected_at=ts, rejection_reason=note, pipeline_stage=None)
    elif new_status == "in_progress":
        changes.update(started_at=req.get("started_at") or ts, completed_at=None)
    elif new_status == "review":
        changes.update(review_at=ts)
    elif new_status == "completed":
        changes.update(completed_at=ts, pipeline_stage="complete")
    elif new_status == "pending":
        changes.update(accepted_at=None, rejected_at=None)
    req = db.requests.update(req.id, changes)

    audit(db, action=f"request.{new_status}", entity="service_request", entity_id=req.id, user=user, actor=actor,
          before={"status": old}, after={"status": new_status, "note": note}, request=http_request)

    client = db.clients.get(req.client_id)
    if client and client.get("user_id"):
        body = {
            "accepted": "Your request was accepted and is now in the queue.",
            "rejected": f"Your request was declined. {note or ''}".strip(),
            "in_progress": "Work on your request has started.",
            "review": "A draft is ready and is being reviewed.",
            "completed": "Your request is complete. Files are ready in the portal.",
            "pending": "Your request was reopened and is pending review.",
        }.get(new_status, f"Status changed to {STATUS_LABEL.get(new_status, new_status)}")
        notify(db, [client.user_id], type=NotificationType.REQUEST_STATUS.value, title=f"{STATUS_LABEL.get(new_status, new_status)}: {req.title}",
               body=body, link=f"/portal#/requests/{req.id}", service_id=req.service_id, request_id=req.id, data={"status": new_status})
    if actor and actor.startswith("agent") and user is None:
        is_review = new_status == "review"
        notify_admins(
            db,
            type=NotificationType.APPROVAL_NEEDED.value if is_review else NotificationType.AGENT.value,
            title=(f"Ready for your review: {req.title}" if is_review else f"{STATUS_LABEL.get(new_status, new_status)}: {req.title}"),
            body=note or f"Pipeline moved the request to {STATUS_LABEL.get(new_status)}.",
            link=f"/admin#/requests/{req.id}", service_id=req.service_id, request_id=req.id,
        )
    broadcast_badges(db, highlight_service_id=req.service_id if old == "pending" or new_status == "pending" else None)
    broadcast_request_update(db, req, {"event": "status", "from": old, "to": new_status})

    if new_status == "accepted" and settings.agent_auto_run_on_accept and settings.agents_enabled:
        enqueue_job("request_pipeline", {"request_id": req.id})
    return req


def mark_paid(db: DB, req: Doc, *, provider: str, provider_payment_id: Optional[str] = None, invoice_url: Optional[str] = None,
              user: Optional[Doc] = None, amount: Optional[float] = None) -> Doc:
    """Settle the request's invoice (checkout return, webhook, mock or admin 'mark paid')."""
    if req.get("is_paid"):
        return req
    ts = now()
    service = db.services.get(req.service_id)
    client = db.clients.get(req.client_id)
    pay = db.payments.find_one({"request_id": req.id}, sort=[("_id", -1)])
    final_amount = float(amount) if amount else float((pay or {}).get("amount") or req.get("price_amount") or 0)
    currency = (pay or {}).get("currency") or req.get("price_currency") or "USD"
    fields = {
        "status": "paid", "provider": provider, "paid_at": ts, "amount": final_amount,
        "settled_currency": settings.reporting_currency, "settled_amount": settings.to_reporting(final_amount, currency),
    }
    if provider_payment_id:
        fields["provider_payment_id"] = provider_payment_id
    if invoice_url:
        fields["invoice_url"] = invoice_url
    if pay:
        pay = db.payments.update(pay.id, fields)
    else:
        pay = db.payments.insert({"client_id": req.client_id, "request_id": req.id, "currency": currency, "invoice_number": f"INV-{ts:%Y%m%d}-{req.id:04d}",
                                  "description": f"{service['name'] if service else 'Request'}: {req.title}", **fields})
    req = db.requests.update(req.id, {"is_paid": True, "paid_at": ts})
    audit(db, action="request.paid", entity="service_request", entity_id=req.id, user=user, actor=None if user else provider,
          after={"amount": final_amount, "currency": currency, "provider": provider})
    notify_admins(db, type=NotificationType.PAYMENT.value, title=f"New payment received: {client.company_name if client else ''}",
                  body=f"{currency} {final_amount:,.2f} (= {pay.settled_currency} {float(pay.settled_amount or 0):,.0f}) for {req.title}",
                  link=f"/admin#/requests/{req.id}", service_id=req.service_id, request_id=req.id)
    if client and client.get("user_id") and user and user.get("is_admin"):
        notify(db, [client.user_id], type=NotificationType.PAYMENT.value, title=f"Payment confirmed: {req.title}",
               body="Thank you. Your request is in the queue.", link=f"/portal#/requests/{req.id}", request_id=req.id)
    broadcast_request_update(db, req, {"event": "paid"})
    return req


# ---------------------------------------------------------------------------
# timeline
# ---------------------------------------------------------------------------
def timeline(db: DB, req: Doc, *, designs=None, revisions=None, deliveries=None, service=None, logs=None) -> List[Dict[str, Any]]:
    designs = designs if designs is not None else db.designs.find({"request_id": req.id}, sort=[("version", 1)])
    revisions = revisions if revisions is not None else db.revisions.find({"request_id": req.id}, sort=[("round", 1)])
    deliveries = deliveries if deliveries is not None else db.deliveries.find({"request_id": req.id})
    service = service if service is not None else db.services.get(req.service_id)
    logs = logs if logs is not None else db.agent_logs.find({"request_id": req.id}, sort=[("created_at", 1)], limit=100)
    events: List[Dict[str, Any]] = []

    def add(ts, kind, title, body=None):
        if ts:
            events.append({"at": ts.isoformat() if hasattr(ts, "isoformat") else ts, "kind": kind, "title": title, "body": body})

    add(req.get("submitted_at") or req.get("created_at"), "submitted", "Request submitted",
        f"{req.get('price_currency')} {float(req.get('price_amount') or 0):,.0f} · {service.get('turnaround_days', 0) if service else ''}-day delivery" if req.get("price_amount") else None)
    add(req.get("paid_at"), "paid", "Payment received")
    add(req.get("accepted_at"), "accepted", "Accepted")
    add(req.get("rejected_at"), "rejected", "Rejected", req.get("rejection_reason"))
    add(req.get("started_at"), "in_progress", "Work started")
    for d in designs:
        add(d.get("created_at"), "design", f"Design v{d.get('version')}: {d.get('title') or 'concept'}", f"QA score {d.get('qa_score')}" if d.get("qa_score") else None)
    add(req.get("review_at"), "review", "Ready for review")
    for dl in deliveries:
        add(dl.get("delivered_at"), "delivery", f"Delivered (v{dl.get('version', 1)})", dl.get("message"))
    for rv in revisions:
        add(rv.get("created_at"), "revision", f"Revision round {rv.get('round')} requested", (rv.get("feedback") or "")[:200])
        add(rv.get("resolved_at"), "revision_done", f"Revision round {rv.get('round')} resolved")
    add(req.get("completed_at"), "completed", "Completed")
    for lg in logs:
        add(lg.get("created_at"), "agent", f"{str(lg.get('agent_key', '')).replace('_', ' ').title()} Agent: {lg.get('step') or ''}", lg.get("message"))
    events.sort(key=lambda e: e["at"] or "")
    return events
