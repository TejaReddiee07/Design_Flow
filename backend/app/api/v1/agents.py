from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.agents import control
from app.core.audit import audit
from app.core.deps import require_admin
from app.core.jobs import enqueue_job
from app.db.mongo import DB, Doc, get_db
from app.models.enums import AGENT_KEYS
from app.schemas.misc import AgentConfigIn, AgentLogOut, AgentOut, AgentRunIn

router = APIRouter(prefix="/agents", tags=["agents"])

# Which manual job each agent triggers from the "Run now" button.
MANUAL_JOBS = {
    "lead": "lead_generation",  # payload: industry, location, count, service_slug
    "outreach": "outreach_followups",
    "marketing": "marketing_posts",
    "onboarding": "onboarding",
    "project_manager": "project_manager_triage",
    "strategy": "request_pipeline",
    "content": "request_pipeline",
    "design": "request_pipeline",
    "qa": "request_pipeline",
    "delivery": "request_resume",
    "revision": "revision_pipeline",
}


def _agent_out(a: Doc) -> AgentOut:
    data = a.public()
    data.setdefault("config", {})
    data["config"] = data.get("config") or {}
    data.setdefault("description", None)
    data.setdefault("enabled", True)
    data.setdefault("tasks_completed", 0)
    data.setdefault("tasks_failed", 0)
    data.setdefault("success_rate", 100.0)
    data.setdefault("sort_order", 0)
    data.setdefault("status", "idle")
    return AgentOut.model_validate(data)


def _log_out(l: Doc) -> AgentLogOut:
    data = l.public()
    data.setdefault("level", "info")
    data.setdefault("status", "completed")
    data.setdefault("tokens_in", 0)
    data.setdefault("tokens_out", 0)
    data.setdefault("duration_ms", 0)
    data.setdefault("message", "")
    return AgentLogOut.model_validate(data)


def _get(db: DB, key: str) -> Doc:
    a = control.get_agent(db, key)
    if not a:
        raise HTTPException(status_code=404, detail="Agent not found")
    return a


@router.get("", response_model=List[AgentOut])
def list_agents(db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    return [_agent_out(a) for a in db.agents.find({}, sort=[("sort_order", 1)])]


@router.get("/summary")
def summary(db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    agents = db.agents.find({})
    total_done = sum(int(a.get("tasks_completed", 0)) for a in agents)
    total_failed = sum(int(a.get("tasks_failed", 0)) for a in agents)
    return {
        "agents": len(agents),
        "running": [a.get("key") for a in agents if a.get("status") == "running"],
        "paused": [a.get("key") for a in agents if a.get("status") == "paused"],
        "stopped": [a.get("key") for a in agents if a.get("status") == "stopped"],
        "errors": [a.get("key") for a in agents if a.get("status") == "error"],
        "tasks_completed": total_done,
        "tasks_failed": total_failed,
        "success_rate": round(100 * total_done / max(1, total_done + total_failed), 1),
    }


@router.get("/logs", response_model=List[AgentLogOut])
def all_logs(
    agent_key: Optional[str] = None,
    request_id: Optional[int] = None,
    run_id: Optional[str] = None,
    level: Optional[str] = None,
    limit: int = Query(100, le=500),
    db: DB = Depends(get_db),
    user: Doc = Depends(require_admin),
):
    filt: dict = {}
    if agent_key:
        filt["agent_key"] = agent_key
    if request_id:
        filt["request_id"] = request_id
    if run_id:
        filt["run_id"] = run_id
    if level:
        filt["level"] = level
    rows = db.agent_logs.find(filt, sort=[("created_at", -1), ("_id", -1)], limit=limit)
    return [_log_out(r) for r in rows]


@router.get("/{key}", response_model=AgentOut)
def get_agent(key: str, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    return _agent_out(_get(db, key))


@router.get("/{key}/logs", response_model=List[AgentLogOut])
def agent_logs(key: str, limit: int = Query(50, le=500), db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    _get(db, key)
    rows = db.agent_logs.find({"agent_key": key}, sort=[("created_at", -1), ("_id", -1)], limit=limit)
    return [_log_out(r) for r in rows]


@router.get("/{key}/stats")
def agent_stats(key: str, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    a = _get(db, key)
    by_status: Dict[str, Dict] = {}
    for l in db.agent_logs.find({"agent_key": key}, projection={"status": 1, "duration_ms": 1, "tokens_in": 1, "tokens_out": 1}):
        b = by_status.setdefault(l.get("status", "completed"), {"count": 0, "duration_total": 0, "tokens_in": 0, "tokens_out": 0})
        b["count"] += 1
        b["duration_total"] += int(l.get("duration_ms") or 0)
        b["tokens_in"] += int(l.get("tokens_in") or 0)
        b["tokens_out"] += int(l.get("tokens_out") or 0)
    return {
        "agent": _agent_out(a).model_dump(mode="json"),
        "by_status": {
            s: {"count": b["count"], "avg_duration_ms": round(b["duration_total"] / b["count"]) if b["count"] else 0, "tokens_in": b["tokens_in"], "tokens_out": b["tokens_out"]}
            for s, b in by_status.items()
        },
    }


@router.patch("/{key}", response_model=AgentOut)
def configure(key: str, body: AgentConfigIn, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    a = _get(db, key)
    data = body.model_dump(exclude_unset=True)
    changes: dict = {}
    if "schedule" in data:
        changes["schedule"] = data["schedule"] or None
    if "enabled" in data and data["enabled"] is not None:
        changes["enabled"] = data["enabled"]
    if "config" in data and data["config"] is not None:
        changes["config"] = {**(a.get("config") or {}), **data["config"]}
    if changes:
        a = db.agents.update(a.id, changes)
    audit(db, action="agent.configure", entity="agent", entity_id=a.id, user=user, after=data)
    control.broadcast(a)
    return _agent_out(a)


@router.post("/{key}/{action}", response_model=AgentOut)
def agent_action(
    key: str,
    action: str,
    request: Request,
    body: Optional[AgentRunIn] = None,
    db: DB = Depends(get_db),
    user: Doc = Depends(require_admin),
):
    if key not in AGENT_KEYS:
        raise HTTPException(status_code=404, detail="Agent not found")
    if action in ("start", "pause", "stop", "restart"):
        a = control.command(db, key, action)
        audit(db, action=f"agent.{action}", entity="agent", entity_id=a.id, user=user, request=request)
        return _agent_out(a)
    if action == "run":
        a = _get(db, key)
        if not a.get("enabled", True) or a.get("status") == "stopped":
            raise HTTPException(status_code=409, detail="Agent is stopped. Press Start first.")
        job = MANUAL_JOBS.get(key, key)
        payload = (body.payload if body else {}) or {}
        if job in ("request_pipeline", "request_resume", "revision_pipeline", "project_manager_triage") and not payload.get("request_id"):
            raise HTTPException(status_code=400, detail="payload.request_id is required for this agent")
        enqueue_job(job, payload)
        control.log(db, key, f"Manual run queued ({job})", step="manual", status="started")
        audit(db, action="agent.run", entity="agent", entity_id=a.id, user=user, after={"job": job, "payload": payload}, request=request)
        return _agent_out(_get(db, key))
    raise HTTPException(status_code=400, detail="Unknown action")
