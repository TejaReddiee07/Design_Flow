"""Registers every background job type with the runner."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from app.agents import control
from app.agents.graphs import lead_pipeline, marketing_graph, onboarding_graph, request_pipeline
from app.agents.nodes import outreach, project_manager
from app.agents.runner import handler
from app.db.mongo import get_db

log = logging.getLogger("agents.pipelines")


def _guard(fn):
    def wrapped(payload: Dict[str, Any]):
        try:
            return fn(payload)
        except control.AgentStopped as exc:
            log.warning("Job stopped by admin: %s", exc)
            return {"stopped": str(exc)}
        except Exception:
            log.exception("Job %s failed", fn.__name__)
            raise

    wrapped.__name__ = fn.__name__
    return wrapped


@handler("request_pipeline")
@_guard
def job_request_pipeline(p: Dict[str, Any]):
    return request_pipeline.run_pipeline(int(p["request_id"]))


@handler("revision_pipeline")
@_guard
def job_revision_pipeline(p: Dict[str, Any]):
    return request_pipeline.run_pipeline(int(p["request_id"]), revision_id=int(p["revision_id"]) if p.get("revision_id") else None)


@handler("request_resume")
@_guard
def job_request_resume(p: Dict[str, Any]):
    return request_pipeline.resume_pipeline(int(p["request_id"]), approved=bool(p.get("approved", True)), message=p.get("message") or "")


@handler("project_manager_triage")
@_guard
def job_triage(p: Dict[str, Any]):
    return project_manager.triage(int(p["request_id"]))


@handler("onboarding")
@_guard
def job_onboarding(p: Dict[str, Any]):
    return onboarding_graph.run(int(p["client_id"]))


@handler("lead_generation")
@_guard
def job_leads(p: Dict[str, Any]):
    if p.get("scheduled") and not p.get("service_slug"):
        # scheduled run: rotate through the services that generate most leads
        import random

        from app.agents.tools.leads_provider import SERVICE_QUERIES

        p["service_slug"] = random.choice(list(SERVICE_QUERIES))
    return lead_pipeline.run(industry=p.get("industry"), location=p.get("location"), count=int(p.get("count") or 5), service_slug=p.get("service_slug"))


@handler("outreach_draft")
@_guard
def job_outreach_draft(p: Dict[str, Any]):
    return outreach.draft([int(i) for i in p.get("lead_ids", [])], tone=p.get("tone") or "friendly")


@handler("outreach_followups")
@_guard
def job_outreach_followups(p: Dict[str, Any]):
    return outreach.followups()


@handler("marketing_posts")
@_guard
def job_marketing(p: Dict[str, Any]):
    return marketing_graph.run()


def _sum(db, repo, filter: Dict[str, Any], field: str) -> float:
    rows = repo.aggregate([{"$match": filter}, {"$group": {"_id": None, "total": {"$sum": f"${field}"}}}])
    return float(rows[0]["total"]) if rows else 0.0


@handler("analytics_snapshot")
@_guard
def job_snapshot(p: Dict[str, Any]):
    """Daily rollup into the analytics collection (requests, leads, revenue for yesterday).

    Revenue is summed in the reporting currency (settled_amount, REPORTING_CURRENCY)."""
    db = get_db()
    day = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    window = {"$gte": start, "$lt": end}
    metrics = {
        "requests_submitted": db.requests.count({"submitted_at": window}),
        "requests_completed": db.requests.count({"completed_at": window}),
        "leads_generated": db.leads.count({"created_at": window}),
        "revenue": _sum(db, db.payments, {"status": "paid", "paid_at": window, "settled_amount": {"$ne": None}}, "settled_amount"),
    }
    for metric, value in metrics.items():
        key = {"metric": metric, "dimension": "", "date": start}
        row = db.analytics.find_one(key)
        if row:
            db.analytics.update(row.id, {"value": float(value)})
        else:
            db.analytics.insert({**key, "value": float(value)})
    return {"date": day.isoformat(), **metrics}
