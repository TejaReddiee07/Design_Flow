"""Revision Agent: turns client feedback into a concrete change list."""
from __future__ import annotations

from typing import Any, Dict

from app.agents import control
from app.agents.llm import complete
from app.agents.nodes.common import as_list, pretty, request_context
from app.db.mongo import get_db
from app.services import request_service as rs

KEY = "revision"
SYSTEM = """You are the Revision Agent at a premium design studio. The client left feedback on a delivered
design. Turn it into an unambiguous change list for the designer.
Return JSON with keys: summary (1 sentence), change_items (list of concrete, checkable changes),
impact (minor|moderate|major)."""


def node(state: Dict[str, Any]) -> Dict[str, Any]:
    db = get_db()
    req = db.requests.get(state["request_id"])
    rev = db.revisions.get(state.get("revision_id")) if state.get("revision_id") else None
    if req.get("status") != "in_progress":
        req = rs.transition(db, req, "in_progress", actor=f"agent:{KEY}", note="Revision pipeline started", force=True)
    req = db.requests.update(req.id, {"pipeline_stage": "revision", "current_run_id": state.get("run_id")})
    if rev:
        rev = db.revisions.update(rev.id, {"status": "in_progress"})
    with control.running(db, KEY, f"Revision round {rev.get('round') if rev else '?'}: {req.title}", run_id=state.get("run_id"), request_id=req.id) as ctx:
        prev = None
        if rev and rev.get("design_id"):
            prev = db.designs.get(rev["design_id"])
        if prev is None:
            latest = db.designs.find({"request_id": req.id}, sort=[("version", -1)], limit=1)
            prev = latest[0] if latest else None
        prompt = request_context(db, req)
        prompt += f"\n\nFeedback: {rev.get('feedback') if rev else state.get('feedback', '')}"
        if prev:
            prompt += f"\n\nPrevious design concept:\n{(prev.get('concept') or '')[:2500]}"
        res = complete(KEY, SYSTEM, prompt)
        data = res.data or {"summary": rev.get("feedback") if rev else "", "change_items": [rev.get("feedback")] if rev else []}
        if rev:
            db.revisions.update(rev.id, {"change_items": as_list(data.get("change_items"))})
        ctx.update(tokens_in=res.tokens_in, tokens_out=res.tokens_out, output=pretty(data))
    return {"revision": data, "stage": "revision"}
