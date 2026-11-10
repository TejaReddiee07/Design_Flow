"""Job dispatcher: maps queue job types to agent pipelines.

Phase 7 fills in the graphs; this module is the single entry point used by both
the worker process and the in-process fallback.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict

from app.core.jobs import register_inline_runner

log = logging.getLogger("runner")

HANDLERS: Dict[str, Callable[[Dict[str, Any]], Any]] = {}


def handler(job_type: str):
    def deco(fn):
        HANDLERS[job_type] = fn
        return fn

    return deco


def run_job(job: Dict[str, Any]) -> Any:
    job_type = job.get("type", "")
    payload = job.get("payload") or {}
    fn = HANDLERS.get(job_type)
    if fn is None:
        # Lazy-load pipelines so importing the API never pulls LangGraph unless needed.
        try:
            import app.agents.pipelines  # noqa: F401
        except Exception as exc:
            log.error("Could not import pipelines: %s", exc)
            return None
        fn = HANDLERS.get(job_type)
    if fn is None:
        log.warning("No handler for job type %s", job_type)
        return None
    return fn(payload)


register_inline_runner(run_job)
