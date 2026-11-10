from __future__ import annotations

from datetime import timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.audit import audit
from app.core.config import settings
from app.core.deps import get_current_user, get_optional_user, require_admin
from app.db.mongo import DB, Doc, get_db, parallel, utcnow
from app.db.seed_data import PRICE_UNITS
from app.schemas.requests import RequestOut
from app.schemas.services import ServiceAnalytics, ServiceOut, ServiceUpdate
from app.services.notification_service import broadcast_badges, service_pending_counts
from app.services.request_service import request_outs

router = APIRouter(prefix="/services", tags=["services"])


def service_prices(s: Doc) -> dict:
    usd = float(s.get("starting_price") or 0)
    return {"USD": settings.convert_price(usd, "USD"), "GBP": settings.convert_price(usd, "GBP"), "INR": settings.convert_price(usd, "INR")}


def _counts(db: DB, user: Optional[Doc]) -> tuple[Dict[int, int], Dict[int, int]]:
    """(pending by service, total by service) scoped to the viewer."""
    if not user:
        return {}, {}
    if user.get("is_admin"):
        pending, total_rows = parallel(
            lambda: service_pending_counts(db),
            lambda: db.requests.aggregate([{"$group": {"_id": "$service_id", "n": {"$sum": 1}}}]),
        )
        return pending, {r["_id"]: r["n"] for r in total_rows}
    cid = user["client"].id if user.get("client") else -1
    rows = db.requests.find({"client_id": cid}, projection={"service_id": 1, "status": 1})
    pending: Dict[int, int] = {}
    totals: Dict[int, int] = {}
    for r in rows:
        totals[r["service_id"]] = totals.get(r["service_id"], 0) + 1
        if r.get("status") == "pending":
            pending[r["service_id"]] = pending.get(r["service_id"], 0) + 1
    return pending, totals


def _out(s: Doc, pending: Dict[int, int], totals: Dict[int, int]) -> ServiceOut:
    item = ServiceOut.model_validate({**s.public(), "is_active": bool(s.get("is_active", True)), "sort_order": int(s.get("sort_order") or 0),
                                      "starting_price": float(s.get("starting_price") or 0)})
    item.pending_count = pending.get(s.id, 0)
    item.total_requests = totals.get(s.id, 0)
    item.prices = service_prices(s)
    item.price_unit = PRICE_UNITS.get(s.get("slug", ""), "per request")
    return item


def _with_counts(db: DB, services: List[Doc], user: Optional[Doc]) -> List[ServiceOut]:
    pending, totals = _counts(db, user)
    return [_out(s, pending, totals) for s in services]


@router.get("", response_model=List[ServiceOut])
def list_services(include_inactive: bool = False, db: DB = Depends(get_db), user: Optional[Doc] = Depends(get_optional_user)):
    flt: Dict = {}
    if not include_inactive or not (user and user.get("is_admin")):
        flt["is_active"] = {"$ne": False}  # seeded services carry no explicit flag until an admin deactivates one
    services, (pending, totals) = parallel(lambda: db.services.find(flt, sort=[("sort_order", 1)]), lambda: _counts(db, user))
    return [_out(s, pending, totals) for s in services]


@router.get("/counts")
def pending_counts(db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    counts = service_pending_counts(db)
    services = db.services.find({}, sort=[("sort_order", 1)], projection={"slug": 1, "name": 1})
    return {"services": [{"id": s.id, "slug": s.get("slug"), "name": s.get("name"), "pending": counts.get(s.id, 0)} for s in services],
            "total_pending": sum(counts.values())}


@router.get("/{slug}", response_model=ServiceOut)
def get_service(slug: str, db: DB = Depends(get_db), user: Optional[Doc] = Depends(get_optional_user)):
    svc = db.services.find_one({"slug": slug})
    if not svc and slug.isdigit():
        svc = db.services.get(int(slug))
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    return _with_counts(db, [svc], user)[0]


@router.patch("/{service_id}", response_model=ServiceOut)
def update_service(service_id: int, body: ServiceUpdate, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    svc = db.services.get(service_id)
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    data = body.model_dump(exclude_unset=True)
    before = {k: svc.get(k) for k in data}
    if data:
        svc = db.services.update(svc.id, data)
    audit(db, action="service.update", entity="service", entity_id=svc.id, user=user, before=before, after=data)
    broadcast_badges(db)
    return _with_counts(db, [svc], user)[0]


@router.get("/{service_id}/requests", response_model=List[RequestOut])
def service_requests(service_id: int, status: Optional[str] = None, limit: int = Query(100, le=500), db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    flt: Dict = {"service_id": service_id}
    if not user.get("is_admin"):
        flt["client_id"] = user["client"].id if user.get("client") else -1
    if status:
        flt["status"] = status
    return request_outs(db, db.requests.find(flt, sort=[("submitted_at", -1)], limit=limit))


@router.get("/{service_id}/analytics", response_model=ServiceAnalytics)
def service_analytics(service_id: int, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    svc = db.services.get(service_id)
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    rows = db.requests.find({"service_id": service_id})
    by_status: Dict[str, int] = {}
    for r in rows:
        by_status[r.get("status", "pending")] = by_status.get(r.get("status", "pending"), 0) + 1
    durations = [(r["completed_at"] - r["accepted_at"]).total_seconds() / 3600 for r in rows if r.get("completed_at") and r.get("accepted_at")]
    now = utcnow()
    since = now - timedelta(days=30)
    last30 = sum(1 for r in rows if (r.get("submitted_at") or r.get("created_at")) and (r.get("submitted_at") or r.get("created_at")) >= since)
    revised = sum(1 for r in rows if int(r.get("revision_count") or 0) > 0)
    trend = []
    for w in range(11, -1, -1):
        start = now - timedelta(weeks=w + 1)
        end = start + timedelta(weeks=1)
        trend.append({"week": start.date().isoformat(), "requests": sum(1 for r in rows if r.get("submitted_at") and start <= r["submitted_at"] < end)})
    return ServiceAnalytics(
        service_id=svc.id, slug=svc.get("slug", ""), name=svc.get("name", ""), total=len(rows), by_status=by_status,
        avg_turnaround_hours=round(sum(durations) / len(durations), 1) if durations else None, last_30_days=last30,
        revision_rate=round(100 * revised / len(rows), 1) if rows else 0.0, trend=trend,
    )
