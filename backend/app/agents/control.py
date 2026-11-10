"""Agent control plane: status changes, metrics, logging. Used by the API and the runner."""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional

from app.agents import live
from app.core.events import publish
from app.db.mongo import DB, Doc, utcnow
from app.models.enums import AgentStatus


class AgentStopped(Exception):
    """Raised inside a run when the admin pressed Stop."""


def agent_dict(a: Doc) -> Dict[str, Any]:
    return {
        "id": a.id,
        "key": a.get("key"),
        "name": a.get("name"),
        "status": a.get("status"),
        "enabled": a.get("enabled", True),
        "tasks_completed": a.get("tasks_completed", 0),
        "tasks_failed": a.get("tasks_failed", 0),
        "success_rate": a.get("success_rate", 100.0),
        "last_run_at": a["last_run_at"].isoformat() if a.get("last_run_at") else None,
        "current_activity": a.get("current_activity"),
        "last_error": a.get("last_error"),
        "schedule": a.get("schedule"),
    }


def get_agent(db: DB, key: str) -> Optional[Doc]:
    return db.agents.find_one({"key": key})


def broadcast(agent: Doc) -> None:
    publish("role:admin", "agent_status", {"agent": agent_dict(agent)})


def set_status(db: DB, key: str, status: str, activity: Optional[str] = None, error: Optional[str] = None) -> Doc:
    agent = get_agent(db, key)
    if not agent:
        raise ValueError(f"Unknown agent {key}")
    changes: Dict[str, Any] = {"status": status}
    if activity is not None:
        changes["current_activity"] = activity
    if error is not None:
        changes["last_error"] = error
    if status == AgentStatus.RUNNING.value:
        changes["last_run_at"] = utcnow()
    agent = db.agents.update(agent.id, changes)
    broadcast(agent)
    return agent


def command(db: DB, key: str, action: str) -> Doc:
    """start | pause | stop | restart from the Control Center buttons."""
    agent = get_agent(db, key)
    if not agent:
        raise ValueError(f"Unknown agent {key}")
    if action == "start":
        changes = {"enabled": True, "current_activity": "Ready", "last_error": None,
                   "status": AgentStatus.IDLE.value if agent.get("status") in ("stopped", "paused", "error") else agent.get("status")}
    elif action == "pause":
        changes = {"status": AgentStatus.PAUSED.value, "current_activity": "Paused by admin"}
    elif action == "stop":
        changes = {"status": AgentStatus.STOPPED.value, "enabled": False, "current_activity": "Stopped by admin"}
    elif action == "restart":
        changes = {"status": AgentStatus.IDLE.value, "enabled": True, "current_activity": "Restarted", "last_error": None}
    else:
        raise ValueError("Unknown action")
    agent = db.agents.update(agent.id, changes)
    broadcast(agent)
    log(db, key, f"Admin: {action}", step="control", status="completed")
    return agent


def wait_if_paused(db: DB, key: str, poll_seconds: float = 2.0, max_wait: float = 3600) -> None:
    """Block while the agent is paused; raise AgentStopped if stopped/disabled."""
    waited = 0.0
    while True:
        agent = get_agent(db, key)
        if not agent or not agent.get("enabled", True) or agent.get("status") == AgentStatus.STOPPED.value:
            raise AgentStopped(key)
        if agent.get("status") != AgentStatus.PAUSED.value:
            return
        time.sleep(poll_seconds)
        waited += poll_seconds
        if waited >= max_wait:
            raise AgentStopped(f"{key} paused too long")


def log(
    db: DB,
    key: str,
    message: str,
    *,
    step: Optional[str] = None,
    status: str = "completed",
    level: str = "info",
    run_id: Optional[str] = None,
    request_id: Optional[int] = None,
    input_summary: Optional[str] = None,
    output_summary: Optional[str] = None,
    tokens_in: int = 0,
    tokens_out: int = 0,
    duration_ms: int = 0,
) -> Doc:
    row = db.agent_logs.insert(
        {
            "agent_key": key, "run_id": run_id, "request_id": request_id, "level": level, "status": status, "step": step,
            "message": message[:4000], "input_summary": (input_summary or "")[:4000] or None,
            "output_summary": (output_summary or "")[:8000] or None, "tokens_in": tokens_in, "tokens_out": tokens_out,
            "duration_ms": duration_ms, "created_at": utcnow(),
        }
    )
    publish("role:admin", "agent_log", {"agent_key": key, "run_id": run_id, "request_id": request_id, "step": step, "status": status,
                                        "message": row.message, "created_at": row.created_at.isoformat()})
    return row


def record_result(db: DB, key: str, success: bool, error: Optional[str] = None) -> None:
    agent = get_agent(db, key)
    if not agent:
        return
    done = int(agent.get("tasks_completed", 0)) + (1 if success else 0)
    failed = int(agent.get("tasks_failed", 0)) + (0 if success else 1)
    total = done + failed
    changes: Dict[str, Any] = {
        "tasks_completed": done, "tasks_failed": failed,
        "success_rate": round(100.0 * done / total, 1) if total else 100.0,
        "last_run_at": utcnow(),
    }
    if not success:
        changes["last_error"] = (error or "")[:2000]
    if agent.get("status") == AgentStatus.RUNNING.value:
        changes["status"] = AgentStatus.IDLE.value if success else AgentStatus.ERROR.value
        changes["current_activity"] = "Idle" if success else f"Error: {(error or '')[:80]}"
    agent = db.agents.update(agent.id, changes)
    broadcast(agent)


@contextmanager
def running(db: DB, key: str, activity: str, *, run_id: Optional[str] = None, request_id: Optional[int] = None) -> Iterator[Dict[str, Any]]:
    """Wrap one unit of agent work: handles pause/stop, status, metrics and timing."""
    try:
        wait_if_paused(db, key)
    except AgentStopped:
        log(db, key, f"Skipped (agent stopped): {activity}", step=activity[:80], status="skipped", level="warn", run_id=run_id, request_id=request_id)
        live.emit(db, request_id, "agent_skipped", agent_key=key, title=f"Skipped (agent stopped): {activity}", run_id=run_id, level="warn")
        raise
    set_status(db, key, AgentStatus.RUNNING.value, activity)
    log(db, key, f"Started: {activity}", step=activity[:80], status="started", run_id=run_id, request_id=request_id)
    live.emit(db, request_id, "agent_started", agent_key=key, title=activity, run_id=run_id)
    live_token = live.set_context(request_id, key, run_id)
    ctx: Dict[str, Any] = {"tokens_in": 0, "tokens_out": 0, "output": None}
    started = time.perf_counter()
    try:
        yield ctx
    except AgentStopped:
        set_status(db, key, AgentStatus.STOPPED.value, "Stopped")
        log(db, key, f"Stopped during: {activity}", step=activity[:80], status="skipped", level="warn", run_id=run_id, request_id=request_id)
        live.emit(db, request_id, "agent_stopped", agent_key=key, title=f"Stopped during: {activity}", run_id=run_id, level="warn")
        raise
    except Exception as exc:
        duration = int((time.perf_counter() - started) * 1000)
        log(db, key, f"Failed: {activity} - {exc}", step=activity[:80], status="failed", level="error", run_id=run_id, request_id=request_id, duration_ms=duration)
        record_result(db, key, False, str(exc))
        live.emit(db, request_id, "agent_failed", agent_key=key, title=f"Failed: {activity}", body=str(exc)[:2000], run_id=run_id, level="error",
                  data={"duration_ms": duration})
        raise
    else:
        duration = int((time.perf_counter() - started) * 1000)
        log(db, key, f"Completed: {activity}", step=activity[:80], status="completed", run_id=run_id, request_id=request_id,
            output_summary=str(ctx.get("output") or "")[:8000], tokens_in=ctx.get("tokens_in", 0), tokens_out=ctx.get("tokens_out", 0), duration_ms=duration)
        record_result(db, key, True)
        live.emit(db, request_id, "agent_completed", agent_key=key, title=activity, body=str(ctx.get("output") or "")[:8000], run_id=run_id,
                  data={"duration_ms": duration, "tokens_in": ctx.get("tokens_in", 0), "tokens_out": ctx.get("tokens_out", 0), "model": ctx.get("model") or ""})
    finally:
        live.clear(live_token)
