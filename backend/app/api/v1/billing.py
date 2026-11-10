"""Pay-per-request billing: invoices, payments, manual payments and the Stripe webhook."""
from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request

from app.core.audit import audit
from app.core.config import settings
from app.core.deps import get_current_user, require_admin
from app.db.mongo import DB, Doc, get_db, parallel, utcnow
from app.models.enums import NotificationType
from app.schemas.common import Page
from app.schemas.misc import ManualPaymentIn, PaymentDetailOut, PaymentOut
from app.services import request_service as rs
from app.services.billing import get_billing
from app.services.notification_service import notify

router = APIRouter(prefix="/billing", tags=["billing"])


def _pay_out(db: DB, p: Doc, clients: Optional[Dict[int, Doc]] = None, requests: Optional[Dict[int, Doc]] = None) -> PaymentOut:
    client = (clients or {}).get(p.get("client_id")) if clients is not None else db.clients.get(p.get("client_id"))
    if client is None and clients is not None:
        client = db.clients.get(p.get("client_id"))
    req = None
    if p.get("request_id"):
        req = (requests or {}).get(p["request_id"]) if requests is not None else db.requests.get(p["request_id"])
        if req is None and requests is not None:
            req = db.requests.get(p["request_id"])
    return PaymentOut(
        id=p.id,
        client_id=p.get("client_id"),
        company_name=client.get("company_name", "") if client else "",
        subscription_id=None,
        request_id=p.get("request_id"),
        request_title=req.get("title") if req else None,
        amount=float(p.get("amount") or 0),
        currency=p.get("currency", "USD"),
        settled_amount=float(p["settled_amount"]) if p.get("settled_amount") is not None else None,
        settled_currency=p.get("settled_currency") or settings.reporting_currency,
        provider=p.get("provider", "pending"),
        status=p.get("status", "pending"),
        invoice_number=p.get("invoice_number"),
        invoice_url=p.get("invoice_url"),
        description=p.get("description"),
        paid_at=p.get("paid_at"),
        created_at=p.get("created_at"),
    )


def _pay_outs(db: DB, rows: List[Doc]) -> List[PaymentOut]:
    clients = db.clients.by_ids({p.get("client_id") for p in rows})
    requests = db.requests.by_ids({p.get("request_id") for p in rows if p.get("request_id")})
    return [_pay_out(db, p, clients, requests) for p in rows]


@router.get("/currencies")
def currencies():
    return {
        "currencies": ["USD", "GBP", "INR"],
        "default": settings.default_currency,
        "reporting": settings.reporting_currency,
        "rates": {"USD": 1, "GBP": settings.fx_gbp, "INR": settings.fx_inr},
    }


@router.get("/invoices", response_model=List[PaymentOut])
def my_invoices(db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    client = user.get("client")
    if not client:
        return []
    rows = db.payments.find({"client_id": client.id}, sort=[("created_at", -1), ("_id", -1)])
    return _pay_outs(db, rows)


@router.get("/summary")
def summary(db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    """Totals for the dashboards (client: own; admin: everything)."""
    filt: dict = {}
    if not user.get("is_admin"):
        filt["client_id"] = user["client"].id if user.get("client") else -1
    rows = db.payments.find(filt)
    by_cur: dict = {}
    for p in rows:
        b = by_cur.setdefault(p.get("currency", "USD"), {"paid": 0.0, "pending": 0.0, "count_paid": 0, "count_pending": 0})
        amt = float(p.get("amount") or 0)
        if p.get("status") == "paid":
            b["paid"] += amt
            b["count_paid"] += 1
        elif p.get("status") == "pending":
            b["pending"] += amt
            b["count_pending"] += 1
    rc = settings.reporting_currency
    settled_paid = sum(settings.to_reporting(float(p.get("amount") or 0), p.get("currency", "USD")) for p in rows if p.get("status") == "paid")
    settled_pending = sum(settings.to_reporting(float(p.get("amount") or 0), p.get("currency", "USD")) for p in rows if p.get("status") == "pending")
    return {
        "by_currency": by_cur,
        "unpaid_requests": sum(b["count_pending"] for b in by_cur.values()),
        "settled": {
            "currency": rc,
            "paid": round(settled_paid, 2),
            "pending": round(settled_pending, 2),
            "note": f"All payments are converted to {rc} at the configured rates; Stripe pays out to your {rc} account.",
        },
    }


# ---- Admin ---------------------------------------------------------------
@router.get("/payments", response_model=Page[PaymentOut])
def list_payments(
    client_id: Optional[int] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, le=200),
    db: DB = Depends(get_db),
    user: Doc = Depends(require_admin),
):
    filt: dict = {}
    if client_id:
        filt["client_id"] = client_id
    if status:
        filt["status"] = status
    rows, total = db.payments.paginate(filt, [("created_at", -1), ("_id", -1)], page, page_size)
    return Page(items=_pay_outs(db, rows), total=total, page=page, page_size=page_size)


HISTORY_LABELS = {
    "request.checkout": "Checkout opened",
    "request.paid": "Payment settled",
    "billing.manual_payment": "Payment recorded manually",
}


def _method_summary(provider: str, status: str, details: Dict, reference: Optional[str], recorded_by: Optional[str]) -> Dict:
    if status != "paid" and provider in ("pending", "", None):
        return {"provider": "pending", "kind": "none", "summary": "Not paid yet"}
    if provider == "stripe":
        card = details.get("card") or {}
        kind = details.get("method_type") or "card"
        if card:
            brand = (card.get("brand") or "card").title()
            wallet = f" via {str(card['wallet']).replace('_', ' ').title()}" if card.get("wallet") else ""
            summary = f"{brand} •••• {card.get('last4') or '????'}{wallet}"
        else:
            summary = str(kind).replace("_", " ").title() if details else "Stripe Checkout"
        return {"provider": "stripe", "kind": kind, "summary": summary}
    if provider == "manual":
        return {"provider": "manual", "kind": "manual", "summary": "Recorded by the studio" + (f" ({recorded_by})" if recorded_by else ""), "reference": reference}
    if provider == "mock":
        return {"provider": "mock", "kind": "test", "summary": "Test payment (mock provider, no money moved)"}
    if provider == "free":
        return {"provider": "free", "kind": "free", "summary": "No charge"}
    return {"provider": provider, "kind": provider, "summary": str(provider).title()}


@router.get("/payments/{payment_id}", response_model=PaymentDetailOut)
def payment_detail(payment_id: int, refresh: bool = False, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    """Everything about one invoice: who paid, how (card brand/last 4, wallet, receipt), transaction ids, fees, history."""
    p = db.payments.get(payment_id)
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")
    client = db.clients.get(p.get("client_id")) if p.get("client_id") else None
    req = db.requests.get(p["request_id"]) if p.get("request_id") else None
    cuser, service = parallel(
        lambda: db.users.get(client.get("user_id")) if client and client.get("user_id") else None,
        lambda: db.services.get(req.get("service_id")) if req else None,
    )
    log_filter: dict = {"entity": "service_request", "entity_id": req.id} if req else {"entity": "payment", "after.client_id": p.get("client_id")}
    logs = [a for a in db.audit_logs.find(log_filter, sort=[("created_at", 1)]) if a.get("action") in HISTORY_LABELS]
    actors = db.users.by_ids({a.get("user_id") for a in logs if a.get("user_id")})

    provider = p.get("provider") or "pending"
    pid = p.get("provider_payment_id")
    details: Dict = dict(p.get("payment_details") or {}) if not refresh else {}
    error = None
    if provider == "stripe" and pid and not details:
        try:
            from app.services.billing.stripe_provider import StripeBilling

            billing = get_billing()
            details = (billing if billing.name == "stripe" else StripeBilling()).payment_details(pid)
            db.payments.update(p.id, {"payment_details": details, "payment_details_at": utcnow()})
        except Exception as exc:  # network down, key removed, test object deleted
            error = f"Could not load the payment from Stripe: {str(exc)[:180]}"
    paid_log = next((a for a in reversed(logs) if a.get("action") in ("request.paid", "billing.manual_payment")), None)
    recorded_by = (actors.get(paid_log.get("user_id")) or {}).get("full_name") if paid_log and paid_log.get("user_id") else None
    reference = pid if provider == "manual" else None

    history: List[Dict] = [{"at": p.get("created_at"), "title": "Invoice created", "body": p.get("invoice_number") or ""}]
    for a in logs:
        who = (actors.get(a.get("user_id")) or {}).get("full_name") if a.get("user_id") else (a.get("actor") or "")
        after = a.get("after") or {}
        body = who or ""
        if a.get("action") == "request.paid" and after.get("provider"):
            body = f"via {after['provider']}" + (f" · {who}" if who else "")
        history.append({"at": a.get("created_at"), "title": HISTORY_LABELS[a["action"]], "body": body})
    if p.get("paid_at") and not any(h["title"] in ("Payment settled", "Payment recorded manually") for h in history):
        history.append({"at": p.get("paid_at"), "title": "Payment settled", "body": f"via {provider}"})

    base = _pay_out(db, p).model_dump()
    return PaymentDetailOut(
        **base,
        provider_payment_id=pid,
        client_name=(cuser or {}).get("full_name") or "",
        client_email=(cuser or {}).get("email") or "",
        service_name=(service or {}).get("name"),
        request_status=req.get("status") if req else None,
        method=_method_summary(provider, p.get("status", "pending"), details, reference, recorded_by),
        details=details,
        details_error=error,
        history=sorted(history, key=lambda h: str(h.get("at") or "")),
    )


@router.post("/payments", response_model=PaymentOut, status_code=201)
def manual_payment(body: ManualPaymentIn, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    client = db.clients.get(body.client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if body.request_id:
        req = db.requests.get(body.request_id)
        if not req or req.get("client_id") != client.id:
            raise HTTPException(status_code=404, detail="Request not found for this client")
        rs.mark_paid(db, req, provider="manual", provider_payment_id=body.description, user=user, amount=body.amount)
        pay = db.payments.find_one({"request_id": req.id}, sort=[("_id", -1)])
        return _pay_out(db, pay)
    now = utcnow()
    currency = (body.currency or client.get("currency") or settings.default_currency).upper()
    p = db.payments.insert(
        {
            "client_id": client.id,
            "request_id": None,
            "amount": float(body.amount),
            "currency": currency,
            "settled_amount": settings.to_reporting(body.amount, currency),
            "settled_currency": settings.reporting_currency,
            "provider": "manual",
            "provider_payment_id": None,
            "status": body.status,
            "invoice_number": f"INV-{now:%Y%m%d}-M{client.id:03d}{int(now.timestamp()) % 1000:03d}",
            "invoice_url": None,
            "description": body.description or "Manual payment",
            "paid_at": now if body.status == "paid" else None,
        }
    )
    audit(db, action="billing.manual_payment", entity="payment", user=user, after={"client_id": client.id, "amount": body.amount})
    notify(
        db,
        [client.get("user_id")],
        type=NotificationType.PAYMENT.value,
        title="Payment recorded",
        body=f"{currency} {body.amount:,.2f} - {p.get('description')}",
        link="/portal#/invoices",
    )
    return _pay_out(db, p)


@router.post("/payments/{payment_id}/mark-paid", response_model=PaymentOut)
def mark_payment_paid(payment_id: int, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    p = db.payments.get(payment_id)
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")
    if p.get("request_id"):
        req = db.requests.get(p["request_id"])
        if req:
            rs.mark_paid(db, req, provider="manual", user=user)
            p = db.payments.get(payment_id)
    else:
        p = db.payments.update(
            p.id,
            {
                "status": "paid",
                "paid_at": utcnow(),
                "settled_currency": settings.reporting_currency,
                "settled_amount": settings.to_reporting(float(p.get("amount") or 0), p.get("currency", "USD")),
            },
        )
    return _pay_out(db, p)


# ---- Webhook (Stripe) ----------------------------------------------------
@router.post("/webhook")
async def webhook(request: Request, stripe_signature: str = Header(default="", alias="Stripe-Signature"), db: DB = Depends(get_db)):
    provider = get_billing()
    payload = await request.body()
    try:
        event = provider.handle_webhook(payload, stripe_signature)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid webhook: {exc}")
    etype = event.get("type")
    if etype == "checkout.session.completed" and event.get("request_id"):
        req = db.requests.get(int(event["request_id"]))
        if req and not req.get("is_paid"):
            rs.mark_paid(
                db,
                req,
                provider=provider.name,
                provider_payment_id=event.get("payment_id"),
                invoice_url=event.get("invoice_url"),
                amount=float(event.get("amount") or 0) or None,
            )
    audit(db, action=f"billing.webhook.{etype}", entity="billing", actor="stripe", after={k: v for k, v in event.items() if k != "raw"})
    return {"received": True}
