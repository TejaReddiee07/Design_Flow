"""Outreach Agent: writes personalised emails, sends them (when allowed), schedules follow-ups."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List

from app.agents import control
from app.agents.llm import complete
from app.agents.nodes.common import pretty
from app.core.config import settings
from app.db.mongo import DB, Doc, get_db, utcnow
from app.models.enums import NotificationType
from app.services.email import get_email
from app.services.notification_service import notify_admins

KEY = "outreach"
SYSTEM = """You are the Outreach Agent for a premium design studio (fixed price per design, 1-7 day delivery,
unlimited revisions). Write a short, specific, non-salesy cold email (90-140 words) to the lead based on the
analysis. Offer two free concept directions. Return JSON with keys: subject, body (plain text, use \\n for line breaks)."""
FOLLOWUP_SYSTEM = """You are the Outreach Agent. Write a brief, friendly follow-up (40-70 words) to a cold email that
got no reply. Reference the original offer. Return JSON with keys: subject, body."""


def _send(db: DB, outreach: Doc, lead: Doc) -> bool:
    if not lead.get("contact_email"):
        return False
    ok = get_email().send(lead["contact_email"], outreach.get("subject") or "Hello", outreach.get("body") or "")
    if ok:
        now = utcnow()
        db.outreach.update(outreach.id, {"status": "sent", "sent_at": now, "follow_up_at": now + timedelta(days=3)})
        if lead.get("status") == "new":
            db.leads.update(lead.id, {"status": "contacted"})
    return ok


def draft(lead_ids: List[int], tone: str = "friendly", **_: Any) -> Dict[str, Any]:
    db = get_db()
    made: List[int] = []
    with control.running(db, KEY, f"Drafting outreach for {len(lead_ids)} lead(s)", run_id=f"outreach-{utcnow():%Y%m%d%H%M}") as ctx:
        tin = tout = 0
        for lid in lead_ids:
            control.wait_if_paused(db, KEY)
            lead = db.leads.get(lid)
            if not lead:
                continue
            prompt = (f"Company: {lead.get('company_name')}\nContact: {lead.get('contact_name') or 'there'}\nIndustry: {lead.get('industry')}\n"
                      f"Website: {lead.get('website')}\nTone: {tone}\nAnalysis:\n{pretty(lead.get('analysis'), 1500)}")
            res = complete(KEY, SYSTEM, prompt)
            tin += res.tokens_in
            tout += res.tokens_out
            data = res.data or {}
            o = db.outreach.insert(
                {
                    "lead_id": lead.id, "channel": "email", "subject": data.get("subject") or f"Idea for {lead.get('company_name')}",
                    "body": data.get("body") or res.text, "status": "draft", "sent_at": None, "follow_up_at": None,
                    "follow_up_count": 0, "reply_text": None, "generated_by": "agent",
                }
            )
            if settings.outreach_auto_send:
                _send(db, o, lead)
            made.append(o.id)
        notify_admins(db, type=NotificationType.AGENT.value, title=f"{len(made)} outreach draft(s) ready",
                      body="Sent automatically." if settings.outreach_auto_send else "Review and approve in Outreach.", link="/admin#/outreach")
        ctx.update(tokens_in=tin, tokens_out=tout, output=f"drafts: {made}")
    return {"outreach_ids": made}


def followups(**_: Any) -> Dict[str, Any]:
    """Scheduled: draft (and optionally send) follow-ups for sent emails with no reply."""
    db = get_db()
    done: List[int] = []
    now = utcnow()
    due = db.outreach.find({"status": "sent", "follow_up_at": {"$lte": now, "$ne": None}, "follow_up_count": {"$lt": 2}})
    with control.running(db, KEY, f"Follow-ups: {len(due)} due", run_id=f"followups-{now:%Y%m%d}") as ctx:
        tin = tout = 0
        for o in due:
            control.wait_if_paused(db, KEY)
            lead = db.leads.get(o.get("lead_id"))
            if not lead or lead.get("status") in ("replied", "qualified", "converted", "rejected"):
                db.outreach.update(o.id, {"follow_up_at": None})
                continue
            res = complete(KEY, FOLLOWUP_SYSTEM, f"Company: {lead.get('company_name')}\nContact: {lead.get('contact_name') or 'there'}\nOriginal subject: {o.get('subject')}\nOriginal email:\n{(o.get('body') or '')[:800]}")
            tin += res.tokens_in
            tout += res.tokens_out
            data = res.data or {}
            f = db.outreach.insert(
                {
                    "lead_id": lead.id, "channel": "email", "subject": data.get("subject") or f"Re: {o.get('subject')}", "body": data.get("body") or res.text,
                    "status": "draft", "sent_at": None, "follow_up_at": None, "follow_up_count": int(o.get("follow_up_count", 0)) + 1,
                    "reply_text": None, "generated_by": "agent",
                }
            )
            db.outreach.update(o.id, {"follow_up_at": None}, inc={"follow_up_count": 1})
            if settings.outreach_auto_send:
                _send(db, f, lead)
            done.append(f.id)
        ctx.update(tokens_in=tin, tokens_out=tout, output=f"follow-ups: {done}")
    return {"followups": done}
