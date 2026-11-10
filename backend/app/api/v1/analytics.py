from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List

from fastapi import APIRouter, Depends, Query

from app.core.config import settings
from app.core.deps import get_current_user, require_admin
from app.db.mongo import DB, Doc, get_db, parallel

router = APIRouter(prefix="/analytics", tags=["analytics"])

OPEN_STATUSES = ["pending", "accepted", "in_progress", "review"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _month_start(d: datetime) -> datetime:
    return d.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _daily(rows, key, days: int) -> List[Dict]:
    today = _now().date()
    buckets = {today - timedelta(days=i): 0.0 for i in range(days - 1, -1, -1)}
    for r in rows:
        d = key(r)
        if d is None:
            continue
        d = d.date() if isinstance(d, datetime) else d
        if d in buckets:
            buckets[d] += 1
    return [{"date": d.isoformat(), "value": v} for d, v in buckets.items()]


def _rep(p: Doc) -> float:
    """Payment amount in the reporting currency (REPORTING_CURRENCY)."""
    return settings.to_reporting(float(p.get("amount") or 0), p.get("currency", "USD"))


@router.get("/overview")
def overview(db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    now = _now()
    month_start = _month_start(now)
    prev_month_start = _month_start(month_start - timedelta(days=1))

    # All six aggregates are independent: fetch them concurrently (one round trip instead of six).
    clients, active_ids, payments, reqs, leads, agents = parallel(
        lambda: db.clients.find({}, projection={"created_at": 1}),
        lambda: db.requests.distinct("client_id", {"status": {"$in": OPEN_STATUSES}}),
        lambda: db.payments.find({}, projection={"amount": 1, "currency": 1, "status": 1, "paid_at": 1}),
        lambda: db.requests.find({}, projection={"status": 1, "accepted_at": 1, "completed_at": 1}),
        lambda: db.leads.find({}, projection={"status": 1, "created_at": 1}),
        lambda: db.agents.find({}, projection={"tasks_completed": 1, "tasks_failed": 1, "status": 1}),
    )
    total_clients = len(clients)
    new_clients_month = sum(1 for c in clients if c.get("created_at") and c["created_at"] >= month_start)
    # Active = clients who currently have at least one open order (not completed / rejected).
    active_clients = len(active_ids)

    paid_rows = [p for p in payments if p.get("status") == "paid"]
    pending_rows = [p for p in payments if p.get("status") == "pending"]
    total_revenue = sum(_rep(p) for p in paid_rows)
    monthly_revenue = sum(_rep(p) for p in paid_rows if p.get("paid_at") and p["paid_at"] >= month_start)
    prev_revenue = sum(_rep(p) for p in paid_rows if p.get("paid_at") and prev_month_start <= p["paid_at"] < month_start)
    unpaid_total = sum(_rep(p) for p in pending_rows)
    by_currency: Dict[str, float] = {}
    for p in paid_rows:
        cur = p.get("currency", "USD")
        by_currency[cur] = by_currency.get(cur, 0.0) + float(p.get("amount") or 0)

    by_status: Dict[str, int] = {}
    for r in reqs:
        by_status[r.get("status", "pending")] = by_status.get(r.get("status", "pending"), 0) + 1
    total_requests = len(reqs)
    completed = by_status.get("completed", 0)
    hours = [(r["completed_at"] - r["accepted_at"]).total_seconds() / 3600 for r in reqs if r.get("completed_at") and r.get("accepted_at")]

    leads_total = len(leads)
    leads_converted = sum(1 for l in leads if l.get("status") == "converted")
    leads_month = sum(1 for l in leads if l.get("created_at") and l["created_at"] >= month_start)

    done = sum(int(a.get("tasks_completed") or 0) for a in agents)
    failed = sum(int(a.get("tasks_failed") or 0) for a in agents)

    return {
        "clients": {
            "total": total_clients,
            "active": active_clients,
            "new_this_month": new_clients_month,
            "note": "active = clients with an open order; drops when the order is completed",
        },
        "revenue": {
            "currency": settings.reporting_currency,
            "note": f"all payments converted to {settings.reporting_currency} at the configured rates",
            "total": round(total_revenue, 2),
            "this_month": round(monthly_revenue, 2),
            "last_month": round(prev_revenue, 2),
            "unpaid": round(unpaid_total, 2),
            "unpaid_count": len(pending_rows),
            "by_currency": by_currency,
            "growth_pct": round(100 * (monthly_revenue - prev_revenue) / prev_revenue, 1) if prev_revenue else None,
        },
        "requests": {
            "total": total_requests,
            "pending": by_status.get("pending", 0),
            "accepted": by_status.get("accepted", 0),
            "in_progress": by_status.get("in_progress", 0),
            "review": by_status.get("review", 0),
            "completed": completed,
            "rejected": by_status.get("rejected", 0),
            "completion_rate": round(100 * completed / total_requests, 1) if total_requests else 0.0,
            "avg_turnaround_hours": round(sum(hours) / len(hours), 1) if hours else None,
        },
        "conversion": {
            "leads": leads_total,
            "converted": leads_converted,
            "rate": round(100 * leads_converted / leads_total, 1) if leads_total else 0.0,
            "leads_this_month": leads_month,
        },
        "agents": {
            "tasks_completed": done,
            "tasks_failed": failed,
            "success_rate": round(100 * done / max(1, done + failed), 1),
            "running": sum(1 for a in agents if a.get("status") == "running"),
        },
    }


@router.get("/revenue")
def revenue(months: int = Query(12, ge=1, le=36), db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    now = _now()
    rows = db.payments.find({"status": "paid"}, projection={"amount": 1, "currency": 1, "paid_at": 1})
    out = []
    cursor = _month_start(now)
    for _ in range(months):
        start = cursor
        end = _month_start(cursor + timedelta(days=32))
        in_month = [p for p in rows if p.get("paid_at") and start <= p["paid_at"] < end]
        out.append(
            {
                "month": start.strftime("%Y-%m"),
                "label": start.strftime("%b %Y"),
                "revenue": round(sum(_rep(p) for p in in_month), 2),
                "payments": len(in_month),
            }
        )
        cursor = _month_start(cursor - timedelta(days=1))
    out.reverse()
    return {"series": out, "currency": settings.reporting_currency}


@router.get("/requests")
def requests_analytics(days: int = Query(30, ge=7, le=365), db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    since = _now() - timedelta(days=days)
    all_rows = db.requests.find({}, projection={"submitted_at": 1, "completed_at": 1, "status": 1, "service_id": 1, "priority": 1})
    recent = [r for r in all_rows if r.get("submitted_at") and r["submitted_at"] >= since]
    services = {s.id: s for s in db.services.find({}, projection={"name": 1, "slug": 1})}
    by_service: Dict[int, Dict] = {}
    for r in all_rows:
        sid = r.get("service_id")
        svc = services.get(sid)
        b = by_service.setdefault(
            sid,
            {"service_id": sid, "name": svc.get("name") if svc else "?", "slug": svc.get("slug") if svc else "", "total": 0, "pending": 0, "completed": 0},
        )
        b["total"] += 1
        if r.get("status") == "pending":
            b["pending"] += 1
        if r.get("status") == "completed":
            b["completed"] += 1
    by_priority: Dict[str, int] = {}
    for r in all_rows:
        pr = r.get("priority") or "normal"
        by_priority[pr] = by_priority.get(pr, 0) + 1
    return {
        "submitted": _daily(recent, lambda r: r.get("submitted_at"), days),
        "completed": _daily([r for r in all_rows if r.get("completed_at") and r["completed_at"] >= since], lambda r: r.get("completed_at"), days),
        "by_service": sorted(by_service.values(), key=lambda x: -x["total"]),
        "by_priority": by_priority,
    }


@router.get("/agents")
def agents_analytics(days: int = Query(30, ge=1, le=365), db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    since = _now() - timedelta(days=days)
    agents = db.agents.find({}, sort=[("sort_order", 1)])
    logs = db.agent_logs.find(
        {"created_at": {"$gte": since}},
        projection={"agent_key": 1, "status": 1, "duration_ms": 1, "tokens_in": 1, "tokens_out": 1, "created_at": 1},
    )
    per: Dict[str, Dict] = {
        a.get("key"): {
            "key": a.get("key"),
            "name": a.get("name"),
            "status": a.get("status"),
            "tasks_completed": int(a.get("tasks_completed") or 0),
            "tasks_failed": int(a.get("tasks_failed") or 0),
            "success_rate": a.get("success_rate", 100.0),
            "runs": 0,
            "failed_runs": 0,
            "avg_duration_ms": 0,
            "tokens": 0,
            "last_run_at": a.get("last_run_at"),
        }
        for a in agents
    }
    durations: Dict[str, List[int]] = {}
    for lg in logs:
        p = per.get(lg.get("agent_key"))
        if not p:
            continue
        if lg.get("status") == "completed":
            p["runs"] += 1
            durations.setdefault(lg["agent_key"], []).append(int(lg.get("duration_ms") or 0))
        elif lg.get("status") == "failed":
            p["failed_runs"] += 1
        p["tokens"] += int(lg.get("tokens_in") or 0) + int(lg.get("tokens_out") or 0)
    for k, ds in durations.items():
        per[k]["avg_duration_ms"] = round(sum(ds) / len(ds)) if ds else 0
    return {
        "agents": list(per.values()),
        "activity": _daily([l for l in logs if l.get("status") == "completed"], lambda l: l.get("created_at"), min(days, 60)),
    }


@router.get("/leads")
def leads_analytics(days: int = Query(30, ge=7, le=365), db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    since = _now() - timedelta(days=days)
    leads = db.leads.find({}, projection={"status": 1, "industry": 1, "source": 1, "score": 1, "created_at": 1})
    recent = [l for l in leads if l.get("created_at") and l["created_at"] >= since]
    by_status: Dict[str, int] = {}
    by_industry: Dict[str, int] = {}
    by_source: Dict[str, int] = {}
    for l in leads:
        st = l.get("status") or "new"
        by_status[st] = by_status.get(st, 0) + 1
        ind = l.get("industry") or "Unknown"
        by_industry[ind] = by_industry.get(ind, 0) + 1
        src = l.get("source") or "agent"
        by_source[src] = by_source.get(src, 0) + 1
    outreach = db.outreach.find({}, projection={"status": 1})
    sent = sum(1 for o in outreach if o.get("status") in ("sent", "replied"))
    replied = sum(1 for o in outreach if o.get("status") == "replied")
    if recent:
        generated = _daily(recent, lambda l: l.get("created_at"), days)
    else:
        snaps = db.analytics.find({"metric": "leads_generated", "date": {"$gte": since.date().isoformat()}}, sort=[("date", 1)])
        generated = [{"date": str(s.get("date")), "value": s.get("value", 0)} for s in snaps]
    return {
        "total": len(leads),
        "by_status": by_status,
        "by_industry": by_industry,
        "by_source": by_source,
        "outreach_sent": sent,
        "replies": replied,
        "reply_rate": round(100 * replied / sent, 1) if sent else 0.0,
        "generated": generated,
        "avg_score": round(sum(float(l.get("score") or 0) for l in leads) / len(leads), 1) if leads else 0,
    }


@router.get("/sales")
def sales_analytics(db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    """Pay-per-request sales: revenue and orders by service and by currency."""
    rates = {"USD": 1.0, "GBP": settings.fx_gbp, "INR": settings.fx_inr}
    payments = db.payments.find({"request_id": {"$ne": None}})
    reqs = db.requests.by_ids({p.get("request_id") for p in payments if p.get("request_id")})
    services = {s.id: s for s in db.services.find({}, projection={"name": 1, "slug": 1})}
    by_service: Dict[int, Dict] = {}
    by_currency: Dict[str, Dict] = {}
    for p in payments:
        r = reqs.get(p.get("request_id"))
        if not r:
            continue
        sid = r.get("service_id")
        svc = services.get(sid)
        b = by_service.setdefault(
            sid,
            {"service_id": sid, "name": svc.get("name") if svc else "?", "slug": svc.get("slug") if svc else "", "orders": 0, "paid": 0, "revenue": 0.0, "revenue_usd": 0.0},
        )
        b["orders"] += 1
        cur = p.get("currency", "USD")
        c = by_currency.setdefault(cur, {"currency": cur, "paid": 0.0, "pending": 0.0, "orders": 0})
        c["orders"] += 1
        amt = float(p.get("amount") or 0)
        if p.get("status") == "paid":
            b["paid"] += 1
            b["revenue_usd"] += amt / rates.get(cur, 1.0)
            b["revenue"] += settings.to_reporting(amt, cur)
            c["paid"] += amt
        elif p.get("status") == "pending":
            c["pending"] += amt
    total_orders = len(payments)
    paid_orders = sum(1 for p in payments if p.get("status") == "paid")
    avg = (sum(b["revenue"] for b in by_service.values()) / paid_orders) if paid_orders else 0.0
    return {
        "currency": settings.reporting_currency,
        "orders": total_orders,
        "paid_orders": paid_orders,
        "unpaid_orders": sum(1 for p in payments if p.get("status") == "pending"),
        "avg_order": round(avg, 2),
        "avg_order_usd": round(avg / rates.get(settings.reporting_currency, 1.0), 2),
        "total_revenue": round(sum(b["revenue"] for b in by_service.values()), 2),
        "by_service": sorted(by_service.values(), key=lambda x: -x["revenue"]),
        "by_currency": list(by_currency.values()),
    }


@router.get("/my-stats")
def my_stats(db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    """Client-side dashboard numbers."""
    client = user.get("client")
    if not client:
        return {}
    rows = db.requests.find(
        {"client_id": client.id},
        projection={"status": 1, "accepted_at": 1, "completed_at": 1, "submitted_at": 1, "is_paid": 1, "price_amount": 1},
    )
    by_status: Dict[str, int] = {}
    for r in rows:
        st = r.get("status") or "pending"
        by_status[st] = by_status.get(st, 0) + 1
    active = by_status.get("accepted", 0) + by_status.get("in_progress", 0) + by_status.get("review", 0)
    hours = [(r["completed_at"] - r["accepted_at"]).total_seconds() / 3600 for r in rows if r.get("completed_at") and r.get("accepted_at")]
    unpaid = [r for r in rows if not r.get("is_paid") and r.get("status") != "rejected"]
    return {
        "requests": {"total": len(rows), **by_status, "active": active},
        "currency": client.get("currency") or "USD",
        "unpaid": {"count": len(unpaid), "amount": sum(float(r.get("price_amount") or 0) for r in unpaid)},
        "spent": sum(float(r.get("price_amount") or 0) for r in rows if r.get("is_paid")),
        "avg_turnaround_hours": round(sum(hours) / len(hours), 1) if hours else None,
        "recent": _daily([r for r in rows if r.get("submitted_at")], lambda r: r.get("submitted_at"), 30),
    }
