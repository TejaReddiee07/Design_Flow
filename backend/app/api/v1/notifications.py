from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Query

from app.core.deps import get_current_user
from app.core.events import publish
from app.db.mongo import DB, Doc, get_db, utcnow
from app.schemas.misc import MarkReadIn, NotificationOut
from app.services.notification_service import unread_count

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=List[NotificationOut])
def list_notifications(
    unread_only: bool = False,
    service_id: Optional[int] = None,
    type: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: DB = Depends(get_db),
    user: Doc = Depends(get_current_user),
):
    filt: dict = {"user_id": user.id}
    if unread_only:
        filt["is_read"] = False
    if service_id:
        filt["service_id"] = service_id
    if type:
        filt["type"] = type
    rows = db.notifications.find(filt, sort=[("created_at", -1), ("_id", -1)], skip=offset, limit=limit)
    return [NotificationOut.model_validate(n.public()) for n in rows]


@router.get("/unread-count")
def unread(db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    rows = db.notifications.find({"user_id": user.id, "is_read": False}, projection={"service_id": 1})
    by_service: Dict[int, int] = {}
    for n in rows:
        sid = n.get("service_id")
        if sid:
            by_service[sid] = by_service.get(sid, 0) + 1
    return {"unread_count": len(rows), "by_service": by_service}


def _push_count(db: DB, user_id: int) -> int:
    count = unread_count(db, user_id)
    publish(f"user:{user_id}", "unread_count", {"unread_count": count})
    return count


@router.post("/mark-read")
def mark_read(body: MarkReadIn, db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    if body.ids:
        db.notifications.update_many(
            {"user_id": user.id, "_id": {"$in": [int(i) for i in body.ids]}, "is_read": False},
            {"is_read": True, "read_at": utcnow()},
        )
    return {"ok": True, "unread_count": _push_count(db, user.id)}


@router.post("/{notification_id}/read")
def mark_one(notification_id: int, db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    n = db.notifications.get(notification_id)
    if n and n.get("user_id") == user.id and not n.get("is_read"):
        db.notifications.update(n.id, {"is_read": True, "read_at": utcnow()})
    return {"ok": True, "unread_count": _push_count(db, user.id)}


@router.post("/mark-all-read")
def mark_all(db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    db.notifications.update_many({"user_id": user.id, "is_read": False}, {"is_read": True, "read_at": utcnow()})
    return {"ok": True, "unread_count": _push_count(db, user.id)}


@router.delete("/{notification_id}")
def delete_notification(notification_id: int, db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    n = db.notifications.get(notification_id)
    if n and n.get("user_id") == user.id:
        db.notifications.delete(n.id)
    return {"ok": True, "unread_count": _push_count(db, user.id)}
