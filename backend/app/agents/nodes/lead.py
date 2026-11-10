"""Lead Generation Agent nodes: discover businesses on the web -> analyse -> store + notify.

The agent searches for the kinds of businesses that buy our services (restaurants, startups,
e-commerce stores, creators...), opens their websites, extracts a contact email and scores each one.
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.agents import control
from app.agents.llm import complete
from app.agents.nodes.common import pretty
from app.agents.tools.leads_provider import find_businesses
from app.db.mongo import get_db
from app.models.enums import NotificationType
from app.services.notification_service import notify_admins

KEY = "lead"
SYSTEM = """You are the Lead Generation Agent for Designflow, a pay-per-design studio offering 19 services
(logos, social media posts, YouTube thumbnails, ads, pitch decks, brochures, e-commerce creatives...).
Analyse a business as a potential client from its website text. Return JSON with keys: score (0-100 fit),
website_quality (dated|average|good), social_presence (weak|moderate|strong), opportunity (1 sentence on what
design work would help them most), pain_points (list), recommended_services (list of our service names)."""


def discover(state: Dict[str, Any]) -> Dict[str, Any]:
    db = get_db()
    slug = state.get("service_slug")
    label = f" for {slug.replace('-', ' ')}" if slug else ""
    with control.running(db, KEY, f"Searching the web for {state.get('count', 5)} businesses{label}", run_id=state.get("run_id")) as ctx:
        candidates = find_businesses(state.get("industry"), state.get("location"), int(state.get("count") or 5), service_slug=slug)
        fresh: List[Dict[str, Any]] = []
        for cand in candidates:
            exists = False
            if cand.get("contact_email"):
                exists = db.leads.exists({"contact_email": cand["contact_email"]})
            if not exists and cand.get("website"):
                exists = db.leads.exists({"website": cand["website"]})
            if not exists:
                fresh.append(cand)
        ctx.update(output=f"{len(candidates)} found, {len(fresh)} new: " + ", ".join(c["company_name"] for c in fresh))
    return {"candidates": fresh}


def analyse(state: Dict[str, Any]) -> Dict[str, Any]:
    db = get_db()
    created: List[int] = []
    cands = state.get("candidates") or []
    services = {s.get("slug"): s.get("name") for s in db.services.find({})}
    with control.running(db, KEY, f"Analysing {len(cands)} website(s)", run_id=state.get("run_id")) as ctx:
        tin = tout = 0
        for cand in cands:
            control.wait_if_paused(db, KEY)
            prompt = (f"Company: {cand['company_name']}\nIndustry: {cand.get('industry')}\nLocation: {cand.get('location')}\n"
                      f"Website: {cand.get('website')}\nContact email found: {cand.get('contact_email') or 'none'}\n"
                      f"Website text: {(cand.get('site_text') or '')[:2500] or '(not reachable)'}")
            res = complete(KEY, SYSTEM, prompt)
            tin += res.tokens_in
            tout += res.tokens_out
            analysis = res.data or {}
            try:
                score = int(analysis.get("score", 50))
            except (TypeError, ValueError):
                score = 50
            if cand.get("service_slug"):
                analysis["interested_in"] = cand["service_slug"]
                analysis.setdefault("recommended_services", [services.get(cand["service_slug"], cand["service_slug"])])
            lead = db.leads.insert(
                {
                    "company_name": cand["company_name"], "website": cand.get("website"), "industry": cand.get("industry"),
                    "location": cand.get("location"), "contact_name": cand.get("contact_name"), "contact_email": cand.get("contact_email"),
                    "contact_phone": cand.get("contact_phone"), "score": max(0, min(100, score)), "analysis": analysis,
                    "status": "new", "source": cand.get("source", "agent"),
                    "notes": f"Found via: {cand.get('query', '')}" if cand.get("query") else None, "client_id": None,
                }
            )
            created.append(lead.id)
            control.log(db, KEY, f"Lead stored: {lead.company_name} (score {lead.score}, email {'yes' if lead.get('contact_email') else 'no'})",
                        step="analyse", run_id=state.get("run_id"), output_summary=pretty(analysis, 1500))
        ctx.update(tokens_in=tin, tokens_out=tout, output=f"{len(created)} leads stored")
    return {"lead_ids": created}


def notify(state: Dict[str, Any]) -> Dict[str, Any]:
    ids = state.get("lead_ids") or []
    if not ids:
        return {"notified": False}
    db = get_db()
    top = db.leads.find_one({"_id": {"$in": ids}}, sort=[("score", -1)])
    with_email = [l.id for l in db.leads.find({"_id": {"$in": ids}, "contact_email": {"$nin": [None, ""]}})]
    notify_admins(db, type=NotificationType.LEAD.value, title=f"{len(ids)} new lead(s) found",
                  body=(f"Top: {top.company_name} scored {top.score}/100. " if top else "") + ("Outreach drafts are being prepared." if with_email else ""),
                  link="/admin#/leads")
    if with_email:
        from app.core.jobs import enqueue_job

        enqueue_job("outreach_draft", {"lead_ids": with_email, "tone": "friendly"})
    return {"notified": True}
