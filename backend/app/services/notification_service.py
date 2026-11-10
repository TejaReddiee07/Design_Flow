"""Central place to create notifications and push them in real time."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from app.core.events import publish
from app.db.mongo import DB, Doc, utcnow


def admin_user_ids(db: DB) -> List[int]:
    return db.admin_ids()


def unread_count(db: DB, user_id: int) -> int:
    return db.notifications.count({"user_id": user_id, "is_read": False})


def serialize(n: Doc) -> Dict[str, Any]:
    return {
        "id": n.id,
        "type": n.get("type"),
        "title": n.get("title"),
        "body": n.get("body"),
        "link": n.get("link"),
        "service_id": n.get("service_id"),
        "request_id": n.get("request_id"),
        "data": n.get("data") or {},
        "is_read": bool(n.get("is_read")),
        "created_at": n["created_at"].isoformat() if n.get("created_at") else None,
    }


def notify(
    db: DB,
    user_ids: Iterable[int],
    *,
    type: str,
    title: str,
    body: Optional[str] = None,
    link: Optional[str] = None,
    service_id: Optional[int] = None,
    request_id: Optional[int] = None,
    data: Optional[Dict[str, Any]] = None,
    commit: bool = False,  # kept for call compatibility; Mongo writes are immediate
) -> List[Doc]:
    rows: List[Doc] = []
    for uid in {int(u) for u in user_ids if u is not None}:
        n = db.notifications.insert(
            {
                "user_id": uid,
                "type": type,
                "title": title,
                "body": body,
                "link": link,
                "service_id": service_id,
                "request_id": request_id,
                "data": data or {},
                "is_read": False,
                "read_at": None,
                "created_at": utcnow(),
            }
        )
        rows.append(n)
        publish(f"user:{uid}", "notification", {"notification": serialize(n), "unread_count": unread_count(db, uid)})
    return rows


def notify_admins(db: DB, **kwargs: Any) -> List[Doc]:
    return notify(db, admin_user_ids(db), **kwargs)


def service_pending_counts(db: DB) -> Dict[int, int]:
    rows = db.requests.aggregate([{"$match": {"status": "pending"}}, {"$group": {"_id": "$service_id", "n": {"$sum": 1}}}])
    return {r["_id"]: r["n"] for r in rows if r.get("_id") is not None}


def broadcast_badges(db: DB, highlight_service_id: Optional[int] = None) -> None:
    counts = service_pending_counts(db)
    services = db.services.find({}, sort=[("sort_order", 1)], projection={"slug": 1, "name": 1})
    publish(
        "role:admin",
        "badge_counts",
        {
            "services": [{"id": s.id, "slug": s.slug, "name": s.name, "pending": counts.get(s.id, 0)} for s in services],
            "total_pending": sum(counts.values()),
            "highlight_service_id": highlight_service_id,
        },
    )


def broadcast_request_update(db: DB, req: Doc, extra: Optional[Dict[str, Any]] = None) -> None:
    payload = {
        "request_id": req.id,
        "status": req.get("status"),
        "service_id": req.get("service_id"),
        "client_id": req.get("client_id"),
        "pipeline_stage": req.get("pipeline_stage"),
        "title": req.get("title"),
    }
    if extra:
        payload.update(extra)
    publish("role:admin", "request_update", payload)
    client = db.clients.get(req.get("client_id"))
    if client and client.get("user_id"):
        publish(f"user:{client.user_id}", "request_update", payload)
