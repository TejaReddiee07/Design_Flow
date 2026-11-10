"""Public endpoints used by the landing page."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.core.config import settings
from app.core.rate_limit import AUTH_LIMIT, limiter
from app.db.mongo import DB, get_db
from app.models.enums import NotificationType
from app.schemas.misc import ContactIn
from app.services.notification_service import notify_admins

router = APIRouter(prefix="/public", tags=["public"])


@router.post("/contact", status_code=201)
@limiter.limit(AUTH_LIMIT)
def contact(request: Request, body: ContactIn, db: DB = Depends(get_db)):
    lead = db.leads.insert(
        {
            "company_name": body.company or body.name,
            "website": body.website,
            "industry": None,
            "location": None,
            "contact_name": body.name,
            "contact_email": body.email,
            "contact_phone": None,
            "score": 60,
            "analysis": {"interested_in": body.service} if body.service else {},
            "status": "new",
            "source": "website",
            "notes": body.message,
            "client_id": None,
        }
    )
    notify_admins(
        db,
        type=NotificationType.LEAD.value,
        title=f"New lead: {lead.company_name}",
        body=f"{body.name} ({body.email}): {body.message[:140]}",
        link=f"/admin#/leads/{lead.id}",
        data={"lead_id": lead.id},
    )
    try:
        from app.core.jobs import enqueue_job

        enqueue_job("outreach_draft", {"lead_ids": [lead.id], "tone": "reply to an inbound enquiry"})
    except Exception:  # pragma: no cover
        pass
    return {"ok": True, "message": "Thanks! We'll reply within one business day."}


@router.get("/services-pricing")
def services_pricing(db: DB = Depends(get_db)):
    """Public price list in all currencies (used by the landing page)."""
    from app.db.seed_data import PRICE_UNITS

    rows = db.services.find({"is_active": True}, sort=[("sort_order", 1)])
    out = []
    for s in rows:
        usd = float(s.get("starting_price") or 0)
        out.append(
            {
                "slug": s.get("slug"),
                "name": s.get("name"),
                "category": s.get("category"),
                "turnaround_days": s.get("turnaround_days"),
                "prices": {"USD": settings.convert_price(usd, "USD"), "GBP": settings.convert_price(usd, "GBP"), "INR": settings.convert_price(usd, "INR")},
                "price_unit": PRICE_UNITS.get(s.get("slug"), "per request"),
            }
        )
    return out
