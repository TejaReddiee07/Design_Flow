"""Cron-style schedules for the Lead, Outreach follow-up and Marketing agents.

Runs inside the worker container (or inside the api process when there is no Redis).
Schedules come from the agents collection (editable in the Control Center) with .env defaults.
"""
from __future__ import annotations

import logging
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.core.jobs import enqueue_job
from app.db.mongo import get_db

log = logging.getLogger("scheduler")

SCHEDULED = {
    "lead": ("lead_generation", settings.lead_agent_cron),
    "outreach": ("outreach_followups", settings.outreach_followup_cron),
    "marketing": ("marketing_posts", settings.marketing_agent_cron),
}

_scheduler: Optional[BackgroundScheduler] = None


def _cron(expr: str) -> Optional[CronTrigger]:
    try:
        return CronTrigger.from_crontab(expr, timezone="UTC")
    except Exception as exc:
        log.warning("Invalid cron '%s': %s", expr, exc)
        return None


def _enqueue(job_type: str, agent_key: str) -> None:
    agent = get_db().agents.find_one({"key": agent_key})
    if not agent or not agent.get("enabled", True) or agent.get("status") == "stopped":
        log.info("Skipping scheduled %s: agent disabled/stopped", agent_key)
        return
    log.info("Scheduled run: %s", job_type)
    enqueue_job(job_type, {"scheduled": True})


def refresh_jobs() -> None:
    """(Re)load schedules from the DB; called at start and every 10 minutes."""
    if _scheduler is None:
        return
    db = get_db()
    for key, (job_type, default_cron) in SCHEDULED.items():
        agent = db.agents.find_one({"key": key})
        expr = (agent.get("schedule") if agent and agent.get("schedule") else default_cron) or ""
        job_id = f"agent-{key}"
        if _scheduler.get_job(job_id):
            _scheduler.remove_job(job_id)
        trigger = _cron(expr) if expr else None
        if trigger:
            _scheduler.add_job(_enqueue, trigger, id=job_id, args=[job_type, key], replace_existing=True)
    try:
        _scheduler.add_job(_daily_snapshot, CronTrigger.from_crontab("5 0 * * *", timezone="UTC"), id="analytics-snapshot", replace_existing=True)
    except Exception:  # pragma: no cover
        pass


def _daily_snapshot() -> None:
    enqueue_job("analytics_snapshot", {})


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.start()
    refresh_jobs()
    _scheduler.add_job(refresh_jobs, "interval", minutes=10, id="refresh-schedules", replace_existing=True)
    log.info("Scheduler started with jobs: %s", [j.id for j in _scheduler.get_jobs()])
    return _scheduler
