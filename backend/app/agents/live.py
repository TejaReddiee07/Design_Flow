"""Live pipeline feed: what every agent is doing on a request, pushed to the admin in real time.

emit()   stores an event in `pipeline_events` and publishes it over the WebSocket as `pipeline_event`
         (to every admin and to the client who owns the request).
stream() publishes the model's partial output while an agent is writing (`agent_stream`, admins only).
         Nothing is stored for streams; the finished output arrives as an `agent_completed` event.

The "See in live" page (/admin/live/<request id>) loads the stored events, then follows the socket.
"""
from __future__ import annotations

import contextvars
from typing import Any, Dict, List, Optional

from app.core.events import publish
from app.db.mongo import DB, Doc, utcnow

# Set by control.running() so the LLM layer knows which request/agent is talking right now.
current: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar("live_ctx", default=None)

PIPELINE_AGENTS = ["project_manager", "strategy", "content", "design", "qa", "revision", "delivery"]

EVENT_TYPES = [
    "pipeline_started", "pipeline_resumed", "agent_started", "agent_completed", "agent_failed", "agent_stopped", "agent_skipped",
    "design_rendered", "qa_scored", "awaiting_approval", "approved", "rework", "delivered", "completed", "stopped", "failed",
]


def set_context(request_id: Optional[int], agent_key: str, run_id: Optional[str]):
    if not request_id:
        return None
    return current.set({"request_id": int(request_id), "agent_key": agent_key, "run_id": run_id})


def clear(token) -> None:
    if token is not None:
        try:
            current.reset(token)
        except ValueError:  # pragma: no cover - reset from another context
            current.set(None)


def _targets(db: DB, request_id: int) -> List[str]:
    targets = ["role:admin"]
    req = db.requests.get(request_id)
    client = db.clients.get(req.get("client_id")) if req else None
    if client and client.get("user_id"):
        targets.append(f"user:{client.user_id}")
    return targets


def serialize(e: Doc) -> Dict[str, Any]:
    created = e.get("created_at")
    return {
        "id": e.get("id") or e.get("_id"),
        "request_id": e.get("request_id"),
        "run_id": e.get("run_id"),
        "type": e.get("type"),
        "agent_key": e.get("agent_key"),
        "title": e.get("title") or "",
        "body": e.get("body"),
        "data": e.get("data") or {},
        "level": e.get("level") or "info",
        "created_at": created.isoformat() if created else None,
    }


def emit(
    db: DB,
    request_id: Optional[int],
    type: str,
    *,
    agent_key: Optional[str] = None,
    title: str = "",
    body: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    run_id: Optional[str] = None,
    level: str = "info",
) -> Optional[Doc]:
    """Store + broadcast one step of the story. Never raises (the pipeline must not fail because of the feed)."""
    if not request_id:
        return None
    try:
        row = db.pipeline_events.insert(
            {
                "request_id": int(request_id), "run_id": run_id, "type": type, "agent_key": agent_key,
                "title": (title or "")[:300], "body": (body or "")[:8000] or None, "data": data or {}, "level": level,
                "created_at": utcnow(),
            }
        )
        payload = serialize(row)
        for target in _targets(db, int(request_id)):
            publish(target, "pipeline_event", payload)
        return row
    except Exception:  # pragma: no cover - feed problems must not break agents
        return None


def stream(request_id: int, agent_key: str, text: str, *, done: bool = False, run_id: Optional[str] = None, model: str = "") -> None:
    """Partial model output for the live page's "writing now" box."""
    publish(
        "role:admin",
        "agent_stream",
        {"request_id": int(request_id), "agent_key": agent_key, "run_id": run_id, "text": text[-12000:], "done": done, "model": model, "chars": len(text)},
    )


def stream_from_context(text: str, *, done: bool = False, model: str = "") -> None:
    ctx = current.get()
    if ctx:
        stream(ctx["request_id"], ctx["agent_key"], text, done=done, run_id=ctx.get("run_id"), model=model)


def events_for(db: DB, request_id: int, *, since_id: Optional[int] = None, limit: int = 500) -> List[Dict[str, Any]]:
    filt: Dict[str, Any] = {"request_id": int(request_id)}
    if since_id:
        filt["_id"] = {"$gt": int(since_id)}
    return [serialize(e) for e in db.pipeline_events.find(filt, sort=[("_id", 1)], limit=limit)]
