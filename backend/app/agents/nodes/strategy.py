"""Strategy Agent: competitor + brand research for a request."""
from __future__ import annotations

from typing import Any, Dict

from app.agents import control
from app.agents.llm import complete
from app.agents.nodes.common import pretty, request_context
from app.agents.tools.research import fetch_site_text
from app.db.mongo import get_db

KEY = "strategy"
SYSTEM = """You are the Strategy Agent at a premium design studio. Given a client request and brand
context (and, when available, text from the client's website), produce creative strategy.
Return JSON with keys: positioning (1-2 sentences), audience_insights (list), competitor_notes (list),
creative_direction (2-3 sentences), do (list), dont (list)."""


def node(state: Dict[str, Any]) -> Dict[str, Any]:
    db = get_db()
    req = db.requests.update(state["request_id"], {"pipeline_stage": "strategy"})
    client = db.clients.get(req.client_id)
    with control.running(db, KEY, f"Researching: {req.title}", run_id=state.get("run_id"), request_id=req.id) as ctx:
        site = fetch_site_text(client.get("website") if client else None)
        prompt = request_context(db, req)
        if site:
            prompt += f"\n\nClient website excerpt:\n{site[:2500]}"
        plan = state.get("plan") or {}
        if plan:
            prompt += f"\n\nProject plan summary: {plan.get('summary', '')}"
        res = complete(KEY, SYSTEM, prompt)
        data = res.data or {}
        ctx.update(tokens_in=res.tokens_in, tokens_out=res.tokens_out, output=pretty(data))
    return {"strategy": data, "stage": "strategy"}
