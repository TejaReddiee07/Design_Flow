"""Marketing Agent: writes LinkedIn, Instagram and X posts promoting the studio."""
from __future__ import annotations

from collections import Counter
from datetime import timedelta
from typing import Any, Dict

from app.agents import control
from app.agents.llm import complete
from app.agents.nodes.common import pretty
from app.db.mongo import get_db, utcnow
from app.models.enums import NotificationType
from app.services.notification_service import notify_admins

KEY = "marketing"
SYSTEM = """You are the Marketing Agent for Designflow, a fixed-price design studio (19 services, pay per request in
USD/GBP/INR, AI-assisted, human-approved, 1-7 day delivery). Using this week's real numbers, write
three posts. Return JSON with keys: linkedin (120-180 words, line breaks with \\n, 3 hashtags),
instagram (caption <= 60 words + 5 hashtags), x (<= 260 characters)."""


def run(**_: Any) -> Dict[str, Any]:
    db = get_db()
    since = utcnow() - timedelta(days=7)
    done = db.requests.find({"completed_at": {"$gte": since}}, projection={"client_id": 1, "service_id": 1})
    shipped = len(done)
    clients = len({r.get("client_id") for r in done})
    top_service = ""
    if done:
        top_id, _ = Counter(r.get("service_id") for r in done).most_common(1)[0]
        svc = db.services.get(top_id)
        top_service = svc.get("name", "") if svc else ""
    with control.running(db, KEY, "Writing weekly social posts", run_id=f"marketing-{utcnow():%Y%m%d}") as ctx:
        res = complete(KEY, SYSTEM, f"This week: {shipped} requests shipped for {clients} client(s). Most requested: {top_service or 'Social Media Design'}. Average turnaround under 48h.")
        data = res.data or {}
        agent = db.agents.find_one({"key": KEY})
        if agent:
            config = dict(agent.get("config") or {})
            posts = list(config.get("posts") or [])
            posts.insert(0, {"at": utcnow().isoformat(), **{k: data.get(k) for k in ("linkedin", "instagram", "x")}})
            config["posts"] = posts[:20]
            db.agents.update(agent.id, {"config": config})
        notify_admins(db, type=NotificationType.AGENT.value, title="Weekly social posts ready",
                      body=(data.get("x") or "")[:140], link="/admin#/agents", data={"posts": data})
        ctx.update(tokens_in=res.tokens_in, tokens_out=res.tokens_out, output=pretty(data))
    return data
