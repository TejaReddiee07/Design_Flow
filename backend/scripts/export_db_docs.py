"""Render docs/DATABASE.md from the MongoDB collection registry (app/db/mongo.py).

    python scripts/export_db_docs.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("MONGO_URI", "mongomock://")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.mongo import COLLECTIONS, INDEXES, NO_TIMESTAMP_UPDATE  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "docs" / "DATABASE.md"

NOTES = {
    "users": "Passwords are bcrypt hashes. `role` is one of admin, staff, client (there is no separate roles collection). The primary admin is re-applied from `.env` on every start.",
    "services": "The 19 design services. `form_schema` drives each service's request form; `starting_price` is the fixed price in USD and is converted to GBP/INR with the `FX_*` rates.",
    "service_requests": "`status` is the lifecycle (pending → accepted → in_progress → review → completed, or rejected); `pipeline_stage` is the agent step; `current_run_id` is the LangGraph thread id used to resume after admin approval. `brief.about_and_wishes` holds the client's own description.",
    "payments": "One invoice per request. `amount`/`currency` is what the client paid; `settled_amount`/`settled_currency` is the same amount converted to the reporting currency (INR).",
    "support_tickets": "The thread is stored as a list of `{sender, name, body, at}` objects in `messages`.",
    "agents": "The 11 AI agents. `config.posts` keeps the Marketing Agent's last 20 drafts.",
    "agent_logs": "Shown in request timelines and the Control Center; pushed live over the WebSocket.",
    "lead_database": "Leads found by the Lead Agent (source `agent`) or the contact form (source `website`). `analysis` is the agent's JSON assessment; `client_id` is set when a lead is converted.",
    "analytics": "Daily rollups written by the `analytics_snapshot` job. `date` is the UTC midnight of the day being summarised.",
    "counters": "`{_id: <collection>, seq: <int>}` — the source of every integer id.",
}


def _index_lines(name: str) -> list[str]:
    specs = INDEXES.get(name) or []
    if not specs:
        return ["Indexes: `_id` only."]
    parts = []
    for keys, opts in specs:
        key = ", ".join(f"{k} {'asc' if d == 1 else 'desc'}" for k, d in keys)
        parts.append(f"`{key}`" + (" (unique)" if opts.get("unique") else ""))
    return ["Indexes: " + "; ".join(parts) + "."]


def main() -> None:
    lines = [
        "# Designflow database (MongoDB)",
        "",
        "Generated from `backend/app/db/mongo.py` by `backend/scripts/export_db_docs.py`.",
        "",
        f"{len(COLLECTIONS)} collections in the `designflow` database (name from `MONGO_DB`). Connection string from `MONGO_URI` "
        "(a MongoDB Atlas `mongodb+srv://` URI in production, `mongomock://` in the tests).",
        "",
        "Conventions:",
        "",
        "- Every document has an integer `_id` taken from the `counters` collection, so the API keeps the same numeric ids the frontend expects.",
        "- `created_at` is set on insert; `updated_at` is set on insert and on every update, except in the append-only collections "
        + ", ".join(f"`{c}`" for c in sorted(NO_TIMESTAMP_UPDATE)) + ".",
        "- All datetimes are stored in UTC and read back timezone-aware.",
        "- Nested data (`brief`, `form_schema`, `analysis`, `messages`, `download_links`, `meta`, ...) is stored as embedded documents/arrays, not JSON strings.",
        "- LangGraph checkpoints live in two extra collections, `langgraph_checkpoints` and `langgraph_writes`, managed by `langgraph-checkpoint-mongodb`.",
        "",
        "## Relationships",
        "",
        "```",
        "users 1─1 clients (clients.user_id) 1─* projects",
        "clients 1─* service_requests *─1 services",
        "service_requests 1─* designs / revisions / deliveries / files / agent_logs / payments",
        "clients 1─1 conversations 1─* chat_messages",
        "clients 1─* brand_assets, support_tickets",
        "lead_database 1─* outreach_history; lead_database.client_id → clients (after conversion)",
        "users 1─* notifications, refresh_tokens, audit_logs",
        "```",
        "",
    ]
    for name, description in COLLECTIONS.items():
        lines.append(f"## {name}")
        lines.append("")
        lines.append(description)
        lines.append("")
        if name in NOTES:
            lines.append(NOTES[name])
            lines.append("")
        lines.extend(_index_lines(name))
        lines.append("")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT} ({len(COLLECTIONS)} collections)")


if __name__ == "__main__":
    main()
