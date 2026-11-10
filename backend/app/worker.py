"""Agent worker process: consumes jobs from Redis and runs the LangGraph pipelines.

    python -m app.worker
"""
from __future__ import annotations

import logging
import signal
import sys
import time

from app.agents.runner import run_job
from app.agents.scheduler import start_scheduler
from app.core.config import settings
from app.core.jobs import pop_job

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
log = logging.getLogger("worker")

_running = True


def _stop(*_):
    global _running
    _running = False
    log.info("Shutting down worker...")


def main() -> int:
    if not settings.redis_url:
        log.error("REDIS_URL is required for the worker process (without Redis the api runs jobs inline).")
        return 1
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    scheduler = start_scheduler()
    from app.agents.llm import provider

    log.info("Worker ready. LLM provider=%s model=%s", provider(), settings.llm_model_for("project_manager"))
    while _running:
        try:
            job = pop_job(timeout=5)
        except Exception as exc:
            log.warning("Queue error: %s; retrying in 3s", exc)
            time.sleep(3)
            continue
        if not job:
            continue
        log.info("Job: %s %s", job.get("type"), job.get("payload"))
        try:
            run_job(job)
        except Exception:
            log.exception("Job failed: %s", job)
    scheduler.shutdown(wait=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
