"""Project Manager Agent: organises requests, sets priorities, plans the work."""
from __future__ import annotations

from typing import Any, Dict

from app.agents import control
from app.agents.llm import complete
from app.agents.nodes.common import pretty, request_context
from app.db.mongo import get_db
from app.services import request_service as rs

KEY = "project_manager"
SYSTEM = """You are the Project Manager Agent at a premium design studio.
Read the client's request and produce a short work plan. Be concrete and practical.
Return JSON with keys: summary (2 sentences), suggested_priority (low|normal|high|urgent),
complexity (low|medium|high), estimated_hours (number), tasks (list of 4-7 short steps),
questions_for_client (list, empty if the brief is sufficient)."""

PRIORITY_RANK = {"low": 0, "normal": 1, "high": 2, "urgent": 3}


def triage(request_id: int) -> Dict[str, Any]:
    """Runs right after submission: summary + priority suggestion, no status change."""
    db = get_db()
    req = db.requests.get(request_id)
    if not req:
        return {}
    with control.running(db, KEY, f"Triage: {req.title}", run_id=f"triage-{request_id}", request_id=request_id) as ctx:
        res = complete(KEY, SYSTEM, request_context(db, req))
        data = res.data or {}
        ctx.update(tokens_in=res.tokens_in, tokens_out=res.tokens_out, output=pretty(data))
        changes: Dict[str, Any] = {}
        if data.get("summary"):
            changes["ai_summary"] = data["summary"]
        suggested = str(data.get("suggested_priority") or "").lower()
        if suggested in PRIORITY_RANK and PRIORITY_RANK[suggested] > PRIORITY_RANK.get(req.get("priority", "normal"), 1):
            changes["priority"] = suggested
        if changes:
            db.requests.update(req.id, changes)
        return data


def node(state: Dict[str, Any]) -> Dict[str, Any]:
    db = get_db()
    req = db.requests.get(state["request_id"])
    if req.get("status") != "in_progress":
        req = rs.transition(db, req, "in_progress", actor=f"agent:{KEY}", note="Pipeline started", force=True)
    req = db.requests.update(req.id, {"pipeline_stage": "project_manager", "current_run_id": state.get("run_id")})
    with control.running(db, KEY, f"Planning: {req.title}", run_id=state.get("run_id"), request_id=req.id) as ctx:
        res = complete(KEY, SYSTEM, request_context(db, req))
        data = res.data or {}
        ctx.update(tokens_in=res.tokens_in, tokens_out=res.tokens_out, output=pretty(data))
        if data.get("summary"):
            db.requests.update(req.id, {"ai_summary": data["summary"]})
    return {"plan": data, "stage": "project_manager"}
