"""QA Agent: checks the draft against the brief and brand; scores it."""
from __future__ import annotations

from typing import Any, Dict

from app.agents import control, live
from app.agents.llm import complete
from app.agents.nodes.common import as_list, pretty, request_context
from app.db.mongo import get_db

KEY = "qa"
PASS_SCORE = 80
SYSTEM = """You are the QA Agent at a premium design studio. Audit a design concept against the client's
brief, brand assets and strategy. Be strict but fair.
Return JSON with keys: score (0-100), pass (true if score >= 80 and no blocking issue), strengths (list),
issues (list of blocking or important problems; empty if none), suggestions (list), notes (1-2 sentences)."""


def node(state: Dict[str, Any]) -> Dict[str, Any]:
    db = get_db()
    req = db.requests.update(state["request_id"], {"pipeline_stage": "qa"})
    design = db.designs.get(state.get("design_id")) if state.get("design_id") else None
    with control.running(db, KEY, f"QA check: {req.title}", run_id=state.get("run_id"), request_id=req.id) as ctx:
        prompt = request_context(db, req)
        if state.get("strategy"):
            prompt += f"\n\nStrategy:\n{pretty(state['strategy'], 1200)}"
        prompt += f"\n\nDesign concept to audit:\n{pretty(state.get('design'), 2500) or (design.get('concept') if design else '')}"
        res = complete(KEY, SYSTEM, prompt)
        data = res.data or {"score": 0, "pass": False, "issues": ["QA model returned no result"]}
        try:
            score = float(data.get("score", 0))
        except (TypeError, ValueError):
            score = 0.0
        passed = bool(data.get("pass", score >= PASS_SCORE)) and score >= PASS_SCORE
        data["pass"] = passed
        if design:
            notes = (data.get("notes") or "") + ("\nIssues: " + "; ".join(map(str, data.get("issues") or [])) if data.get("issues") else "")
            db.designs.update(design.id, {"qa_score": score, "qa_notes": notes})
        ctx.update(tokens_in=res.tokens_in, tokens_out=res.tokens_out, output=pretty(data), model=res.model)
        live.emit(
            db, req.id, "qa_scored", agent_key=KEY, run_id=state.get("run_id"), level="info" if passed else "warn",
            title=f"QA score {int(score)}/100 - {'passed' if passed else 'needs rework'}", body=str(data.get("notes") or ""),
            data={
                "score": score, "pass": passed, "design_id": design.id if design else None, "attempt": int(state.get("qa_attempts") or 0) + 1,
                "strengths": as_list(data.get("strengths")), "issues": as_list(data.get("issues")), "suggestions": as_list(data.get("suggestions")),
            },
        )
    return {"qa": data, "qa_attempts": int(state.get("qa_attempts") or 0) + 1, "stage": "qa"}
