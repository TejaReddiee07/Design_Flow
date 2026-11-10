"""Background job queue for agent work.

With Redis: jobs are pushed to a list and consumed by the worker container.
Without Redis: jobs run in a daemon thread inside the current process.
"""
from __future__ import annotations

import json
import logging
import threading
from typing import Any, Dict, Optional

from app.core.config import settings

log = logging.getLogger("jobs")
QUEUE_KEY = "designflow:jobs"

_inline_runner = None  # set by the agents runner to avoid circular imports


def register_inline_runner(fn) -> None:
    global _inline_runner
    _inline_runner = fn


def enqueue_job(job_type: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    job = {"type": job_type, "payload": payload or {}}
    if not settings.agents_enabled:
        log.info("Agents disabled; job %s dropped", job_type)
        return job
    if settings.redis_url:
        try:
            import redis

            r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
            r.lpush(QUEUE_KEY, json.dumps(job, default=str))
            return job
        except Exception as exc:  # pragma: no cover
            log.warning("Redis enqueue failed (%s); running inline", exc)
    _run_inline(job)
    return job


def _run_inline(job: Dict[str, Any]) -> None:
    runner = _inline_runner
    if runner is None:
        try:
            from app.agents.runner import run_job as runner  # lazy import
        except Exception as exc:  # pragma: no cover
            log.error("No job runner available: %s", exc)
            return
    t = threading.Thread(target=runner, args=(job,), daemon=True, name=f"job-{job['type']}")
    t.start()


def pop_job(timeout: int = 5) -> Optional[Dict[str, Any]]:
    """Blocking pop used by the worker process."""
    import redis

    r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    item = r.brpop(QUEUE_KEY, timeout=timeout)
    if not item:
        return None
    return json.loads(item[1])
