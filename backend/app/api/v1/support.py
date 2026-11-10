from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from app.core.audit import audit
from app.core.deps import get_current_user
from app.db.mongo import DB, Doc, get_db, utcnow
from app.models.enums import NotificationType
from app.schemas.misc import TicketCreate, TicketOut, TicketReply
from app.services.notification_service import notify, notify_admins

router = APIRouter(prefix="/support", tags=["support"])


def _out(db: DB, t: Doc) -> TicketOut:
    client = db.clients.get(t.get("client_id"))
    data = t.public()
    data["company_name"] = client.get("company_name", "") if client else ""
    data.setdefault("messages", [])
    return TicketOut.model_validate(data)


def _get(db: DB, ticket_id: int, user: Doc) -> Doc:
    t = db.tickets.get(ticket_id)
    if not t or (not user.get("is_admin") and (not user.get("client") or t.get("client_id") != user["client"].id)):
        raise HTTPException(status_code=404, detail="Ticket not found")
    return t


@router.get("/tickets", response_model=List[TicketOut])
def list_tickets(status: Optional[str] = None, db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    filt: dict = {}
    if not user.get("is_admin"):
        filt["client_id"] = user["client"].id if user.get("client") else -1
    if status:
        filt["status"] = status
    return [_out(db, t) for t in db.tickets.find(filt, sort=[("updated_at", -1), ("_id", -1)])]


@router.post("/tickets", response_model=TicketOut, status_code=201)
def create_ticket(body: TicketCreate, db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    client = user.get("client")
    if not client:
        raise HTTPException(status_code=403, detail="Client account required")
    t = db.tickets.insert(
        {
            "client_id": client.id,
            "subject": body.subject,
            "status": "open",
            "priority": body.priority,
            "category": body.category,
            "messages": [{"sender": "client", "name": user.get("full_name", ""), "body": body.message, "at": utcnow().isoformat()}],
            "resolved_at": None,
        }
    )
    audit(db, action="ticket.create", entity="support_ticket", entity_id=t.id, user=user)
    notify_admins(
        db,
        type=NotificationType.SUPPORT.value,
        title=f"Support ticket: {body.subject}",
        body=f"{client.get('company_name', '')}: {body.message[:140]}",
        link=f"/admin#/support/{t.id}",
    )
    return _out(db, t)


@router.get("/tickets/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: int, db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    return _out(db, _get(db, ticket_id, user))


@router.post("/tickets/{ticket_id}/reply", response_model=TicketOut)
def reply(ticket_id: int, body: TicketReply, db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    t = _get(db, ticket_id, user)
    is_admin = bool(user.get("is_admin"))
    msgs = list(t.get("messages") or [])
    msgs.append({"sender": "admin" if is_admin else "client", "name": user.get("full_name", ""), "body": body.message, "at": utcnow().isoformat()})
    changes: dict = {"messages": msgs}
    if body.status and is_admin:
        changes["status"] = body.status
        if body.status in ("resolved", "closed"):
            changes["resolved_at"] = utcnow()
    elif is_admin and t.get("status") == "open":
        changes["status"] = "pending"
    elif not is_admin:
        changes["status"] = "open"
    t = db.tickets.update(t.id, changes)
    client = db.clients.get(t.get("client_id"))
    if is_admin and client:
        notify(db, [client.get("user_id")], type=NotificationType.SUPPORT.value, title=f"Reply: {t.get('subject')}", body=body.message[:140], link=f"/portal#/support/{t.id}")
    elif not is_admin:
        notify_admins(db, type=NotificationType.SUPPORT.value, title=f"Ticket updated: {t.get('subject')}", body=body.message[:140], link=f"/admin#/support/{t.id}")
    return _out(db, t)


@router.patch("/tickets/{ticket_id}", response_model=TicketOut)
def update_ticket(ticket_id: int, status: str, db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    t = _get(db, ticket_id, user)
    if not user.get("is_admin") and status != "closed":
        raise HTTPException(status_code=403, detail="Clients can only close tickets")
    changes: dict = {"status": status}
    if status in ("resolved", "closed"):
        changes["resolved_at"] = utcnow()
    return _out(db, db.tickets.update(t.id, changes))
