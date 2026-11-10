"""The main LangGraph workflow for a client request.

Client Request -> Project Manager -> Strategy -> Content -> Design -> QA
    -> (QA fail: back to Design, max 2 attempts)
    -> Request review (status=review, admin notified)
    -> [interrupt] Admin Approval
    -> approved: Delivery -> Complete
    -> rejected: Design (rework) -> QA -> review again
Revision entry: Revision -> Design -> QA -> review -> approval -> Delivery

Human-in-the-loop is implemented with LangGraph's interrupt_before on the admin_approval
node and a checkpointer keyed by thread_id = request.current_run_id.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents import control, live
from app.agents.graphs.checkpoint import get_checkpointer
from app.agents.nodes import content, delivery, design, project_manager, qa, revision, strategy
from app.core.config import settings
from app.db.mongo import get_db
from app.models.enums import NotificationType
from app.services import request_service as rs
from app.services.notification_service import notify_admins

log = logging.getLogger("agents.pipeline")
MAX_QA_ATTEMPTS = 2


class PipelineState(TypedDict, total=False):
    request_id: int
    run_id: str
    revision_id: Optional[int]
    plan: Dict[str, Any]
    strategy: Dict[str, Any]
    content: Dict[str, Any]
    design: Dict[str, Any]
    design_id: int
    design_version: int
    qa: Dict[str, Any]
    qa_attempts: int
    revision: Dict[str, Any]
    approved: bool
    approval_message: str
    delivery_id: int
    stage: str


# ---- extra nodes ----------------------------------------------------------
def request_review(state: PipelineState) -> Dict[str, Any]:
    db = get_db()
    req = db.requests.get(state["request_id"])
    score = (state.get("qa") or {}).get("score")
    req = rs.transition(db, req, "review", actor="agent:qa", note=f"QA score {score}/100. Draft ready for approval.", force=True)
    db.requests.update(req.id, {"pipeline_stage": "admin_approval"})
    control.log(db, "qa", "Waiting for admin approval", step="await_approval", status="started", run_id=state.get("run_id"), request_id=req.id)
    live.emit(db, req.id, "awaiting_approval", agent_key="qa", run_id=state.get("run_id"), title="Waiting for your approval",
              body=f"QA scored the draft {score}/100. Approve to deliver it to the client, or send it back with a note for rework.",
              data={"score": score, "design_id": state.get("design_id"), "design_version": state.get("design_version")})
    return {"stage": "awaiting_approval"}


def admin_approval(state: PipelineState) -> Dict[str, Any]:
    """Runs after the admin resumes the graph (approved or sent back for rework)."""
    db = get_db()
    req = db.requests.get(state["request_id"])
    approved = bool(state.get("approved", True))
    req = db.requests.update(req.id, {"pipeline_stage": "approved" if approved else "rework"})
    control.log(db, "project_manager", "Admin approved the draft" if approved else f"Admin requested rework: {state.get('approval_message') or ''}",
                step="admin_approval", run_id=state.get("run_id"), request_id=req.id)
    live.emit(db, req.id, "approved" if approved else "rework", agent_key="project_manager", run_id=state.get("run_id"),
              title="You approved the draft - handing over to Delivery" if approved else "You sent the draft back - Design is reworking it",
              body=state.get("approval_message") or None, data={"approved": approved})
    if not approved:
        rs.transition(db, req, "in_progress", actor="agent:project_manager", note="Rework requested by admin", force=True)
    return {"stage": "approved" if approved else "rework", "qa_attempts": 0}


# ---- routing ---------------------------------------------------------------
def entry(state: PipelineState) -> str:
    return "revision" if state.get("revision_id") else "project_manager"


def after_qa(state: PipelineState) -> str:
    qa_result = state.get("qa") or {}
    if not qa_result.get("pass") and int(state.get("qa_attempts") or 0) < MAX_QA_ATTEMPTS:
        return "design"
    return "request_review"


def after_approval(state: PipelineState) -> str:
    return "delivery" if state.get("approved", True) else "design"


def build_graph():
    g = StateGraph(PipelineState)
    g.add_node("project_manager", project_manager.node)
    g.add_node("strategy", strategy.node)
    g.add_node("content", content.node)
    g.add_node("design", design.node)
    g.add_node("qa", qa.node)
    g.add_node("revision", revision.node)
    g.add_node("request_review", request_review)
    g.add_node("admin_approval", admin_approval)
    g.add_node("delivery", delivery.node)

    g.add_conditional_edges(START, entry, {"revision": "revision", "project_manager": "project_manager"})
    g.add_edge("project_manager", "strategy")
    g.add_edge("strategy", "content")
    g.add_edge("content", "design")
    g.add_edge("design", "qa")
    g.add_conditional_edges("qa", after_qa, {"design": "design", "request_review": "request_review"})
    g.add_edge("revision", "design")
    g.add_edge("request_review", "admin_approval")
    g.add_conditional_edges("admin_approval", after_approval, {"delivery": "delivery", "design": "design"})
    g.add_edge("delivery", END)
    return g.compile(checkpointer=get_checkpointer(), interrupt_before=["admin_approval"])


def build_resume_graph():
    """Fallback used when no checkpoint exists (e.g. api restarted with MemorySaver)."""
    g = StateGraph(PipelineState)
    g.add_node("admin_approval", admin_approval)
    g.add_node("design", design.node)
    g.add_node("qa", qa.node)
    g.add_node("request_review", request_review)
    g.add_node("delivery", delivery.node)
    g.add_edge(START, "admin_approval")
    g.add_conditional_edges("admin_approval", after_approval, {"delivery": "delivery", "design": "design"})
    g.add_edge("design", "qa")
    g.add_conditional_edges("qa", after_qa, {"design": "design", "request_review": "request_review"})
    g.add_edge("request_review", END)
    g.add_edge("delivery", END)
    return g.compile()


graph = build_graph()
_resume_graph = build_resume_graph()


def _config(run_id: str) -> Dict[str, Any]:
    return {"configurable": {"thread_id": run_id}, "recursion_limit": 40}


def _fail(request_id: int, run_id: str, exc: Exception) -> None:
    db = get_db()
    req = db.requests.get(request_id)
    if req:
        req = db.requests.update(req.id, {"pipeline_stage": "error"})
        notify_admins(db, type=NotificationType.AGENT.value, title=f"Pipeline error: {req.title}",
                      body=str(exc)[:200], link=f"/admin#/requests/{req.id}", request_id=req.id, service_id=req.service_id, commit=True)
        live.emit(db, req.id, "failed", run_id=run_id, level="error", title="Pipeline stopped with an error", body=str(exc)[:1000])


def run_pipeline(request_id: int, revision_id: Optional[int] = None) -> Dict[str, Any]:
    if not settings.agents_enabled:
        return {"skipped": "agents disabled"}
    db = get_db()
    req = db.requests.get(request_id)
    if not req:
        return {"error": "request not found"}
    if req.get("status") in ("rejected", "pending"):
        return {"skipped": f"request is {req.status}"}
    run_id = f"req{request_id}-r{int(req.get('revision_count') or 0)}-{uuid.uuid4().hex[:6]}"
    db.requests.update(req.id, {"current_run_id": run_id})
    state: PipelineState = {"request_id": request_id, "run_id": run_id, "revision_id": revision_id, "qa_attempts": 0}
    live.emit(db, request_id, "pipeline_started", run_id=run_id,
              title="Revision pipeline started" if revision_id else "Agent pipeline started",
              body="Revision -> Design -> QA -> your approval -> Delivery" if revision_id else "Project Manager -> Strategy -> Content -> Design -> QA -> your approval -> Delivery",
              data={"revision_id": revision_id})
    try:
        result = graph.invoke(state, _config(run_id))
        return {"run_id": run_id, "stage": result.get("stage")}
    except control.AgentStopped as exc:
        log.warning("Pipeline %s stopped by admin: %s", run_id, exc)
        db.requests.update(request_id, {"pipeline_stage": "stopped"})
        live.emit(db, request_id, "stopped", run_id=run_id, level="warn", title="Pipeline stopped by admin", body=str(exc))
        return {"run_id": run_id, "stage": "stopped"}
    except Exception as exc:
        log.exception("Pipeline %s failed", run_id)
        _fail(request_id, run_id, exc)
        return {"run_id": run_id, "stage": "error", "error": str(exc)}


def resume_pipeline(request_id: int, approved: bool = True, message: str = "") -> Dict[str, Any]:
    if not settings.agents_enabled:
        return {"skipped": "agents disabled"}
    db = get_db()
    req = db.requests.get(request_id)
    if not req:
        return {"error": "request not found"}
    run_id = req.get("current_run_id") or f"req{request_id}-resume-{uuid.uuid4().hex[:6]}"
    db.requests.update(req.id, {"current_run_id": run_id})
    config = _config(run_id)
    live.emit(db, request_id, "pipeline_resumed", run_id=run_id, title="Resuming after your decision",
              body=("Approved: Delivery Agent is packaging the files." if approved else "Sent back: Design Agent is reworking the draft.") + (f" Note: {message}" if message else ""),
              data={"approved": approved, "message": message or ""})
    try:
        snapshot = None
        try:
            snapshot = graph.get_state(config)
        except Exception:  # pragma: no cover - checkpointer edge cases
            snapshot = None
        if snapshot and snapshot.next and "admin_approval" in snapshot.next:
            graph.update_state(config, {"approved": approved, "approval_message": message or ""})
            result = graph.invoke(None, config)
        else:
            log.info("No pending checkpoint for %s; running resume graph", run_id)
            result = _resume_graph.invoke({"request_id": request_id, "run_id": run_id, "approved": approved, "approval_message": message or "", "qa_attempts": 0}, {"recursion_limit": 40})
        return {"run_id": run_id, "stage": result.get("stage")}
    except control.AgentStopped as exc:
        log.warning("Resume %s stopped by admin: %s", run_id, exc)
        live.emit(db, request_id, "stopped", run_id=run_id, level="warn", title="Pipeline stopped by admin", body=str(exc))
        return {"run_id": run_id, "stage": "stopped"}
    except Exception as exc:
        log.exception("Resume %s failed", run_id)
        _fail(request_id, run_id, exc)
        return {"run_id": run_id, "stage": "error", "error": str(exc)}
