"""Render docs/API.md from the live OpenAPI schema so the docs never drift from the code.

    python scripts/export_api_docs.py
"""
from __future__ import annotations

import os
import sys
from collections import OrderedDict
from pathlib import Path

os.environ.setdefault("MONGO_URI", "mongomock://")
os.environ.setdefault("MONGO_DB", "designflow_docs")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("REDIS_URL", "")
os.environ.setdefault("LLM_PROVIDER", "mock")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "docs" / "API.md"

TAG_INTRO = {
    "auth": "Register, log in, refresh and manage the current user. Access tokens last 15 minutes; refresh tokens are rotated on every refresh and revoked on logout.",
    "clients": "Admin management of client accounts. Clients may read their own profile via `/clients/me`.",
    "projects": "Optional grouping of requests. Clients see only their own projects.",
    "services": "The 19 design services, their request forms (`form_schema`), fixed prices in USD/GBP/INR, pending-count badges and per-service analytics.",
    "requests": "The core object. Includes the action buttons (accept / reject / complete), pipeline triggers, designs, revisions and deliveries.",
    "files": "Secure uploads (type whitelist, size limit, content sniffing), downloads, version chains and brand assets.",
    "notifications": "Per-user notification stream with unread counts; pushed live over the WebSocket as well.",
    "chat": "Client to admin messaging with file attachments and live delivery.",
    "support": "Support tickets with threaded replies.",
    "public": "Unauthenticated endpoints used by the landing page.",
    "billing": "Pay-per-request checkout (Stripe or mock), payment confirmation, invoices, manual payments and the Stripe webhook. Amounts are settled in the reporting currency (INR).",
    "leads": "Lead database and outreach history, including Lead Agent triggers and email sending.",
    "agents": "AI Agent Control Center: status, metrics, logs, Start / Pause / Stop / Restart / Run.",
    "analytics": "Dashboard numbers for admins (overview, revenue, requests, agents, leads) and clients (my-stats).",
    "admin": "Users, roles, audit log and system settings.",
    "system": "Health check.",
}


def _schema_name(ref_or_schema) -> str:
    if not ref_or_schema:
        return ""
    if "$ref" in ref_or_schema:
        return ref_or_schema["$ref"].split("/")[-1]
    if ref_or_schema.get("type") == "array" and "items" in ref_or_schema:
        return f"list[{_schema_name(ref_or_schema['items'])}]"
    return ref_or_schema.get("type", "object")


def main() -> None:
    spec = app.openapi()
    paths = spec["paths"]
    components = spec.get("components", {}).get("schemas", {})
    by_tag: "OrderedDict[str, list]" = OrderedDict()
    for path, ops in paths.items():
        for method, op in ops.items():
            if method.lower() not in ("get", "post", "patch", "put", "delete"):
                continue
            tag = (op.get("tags") or ["other"])[0]
            by_tag.setdefault(tag, []).append((method.upper(), path, op))

    lines = [
        "# Designflow API reference",
        "",
        "Generated from the OpenAPI schema by `backend/scripts/export_api_docs.py`. Interactive docs: `/docs` (Swagger UI) and `/redoc`.",
        "",
        "Base URL: `/api/v1`. Authentication: `Authorization: Bearer <access_token>` (obtain via `POST /auth/login`).",
        "Errors use `{ \"detail\": \"message\" }`; validation errors return HTTP 422 with a list of field errors.",
        "",
        "## Real-time WebSocket",
        "",
        "`GET /ws?token=<access_token>` upgrades to a WebSocket. Messages are JSON `{type, payload}`:",
        "",
        "| type | audience | payload |",
        "|---|---|---|",
        "| `hello` | the connecting user | `{user_id, role, unread_count}` |",
        "| `notification` | one user | `{notification, unread_count}` |",
        "| `unread_count` | one user | `{unread_count}` |",
        "| `badge_counts` | admins | `{services: [{id, slug, name, pending}], total_pending, highlight_service_id}` |",
        "| `request_update` | admins + the request's client | `{request_id, status, service_id, client_id, pipeline_stage, title, event}` |",
        "| `chat_message` | both parties | `{conversation_id, message}` |",
        "| `agent_status` | admins | `{agent}` |",
        "| `agent_log` | admins | `{agent_key, run_id, request_id, step, status, message, created_at}` |",
        "",
        "Send `{\"type\": \"ping\"}` to keep the connection alive; the server also pings idle connections every 45 s.",
        "",
    ]
    order = list(TAG_INTRO.keys()) + [t for t in by_tag if t not in TAG_INTRO]
    for tag in order:
        ops = by_tag.get(tag)
        if not ops:
            continue
        lines.append(f"## {tag.capitalize()}")
        lines.append("")
        if tag in TAG_INTRO:
            lines.append(TAG_INTRO[tag])
            lines.append("")
        lines.append("| Method | Path | Description | Body | Response |")
        lines.append("|---|---|---|---|---|")
        for method, path, op in ops:
            summary = op.get("summary") or op.get("operationId", "").replace("_", " ")
            body = ""
            rb = op.get("requestBody", {}).get("content", {})
            if "application/json" in rb:
                body = f"`{_schema_name(rb['application/json'].get('schema'))}`"
            elif "multipart/form-data" in rb:
                body = "multipart form"
            resp = ""
            ok = op.get("responses", {}).get("200") or op.get("responses", {}).get("201")
            if ok:
                content = ok.get("content", {}).get("application/json", {})
                resp = f"`{_schema_name(content.get('schema'))}`" if content.get("schema") else ""
            params = [p["name"] for p in op.get("parameters", []) if p.get("in") == "query"]
            if params:
                summary += f" (query: {', '.join(params)})"
            lines.append(f"| `{method}` | `{path.replace('/api/v1', '')}` | {summary} | {body} | {resp} |")
        lines.append("")

    lines.append("## Schemas")
    lines.append("")
    lines.append("Request and response models (field: type). Optional fields are marked with `?`.")
    lines.append("")
    for name, schema in sorted(components.items()):
        props = schema.get("properties") or {}
        if not props:
            continue
        required = set(schema.get("required") or [])
        fields = []
        for fname, fschema in props.items():
            t = fschema.get("type") or ("ref" if "$ref" in fschema else "any")
            if "anyOf" in fschema:
                t = "/".join(x.get("type", "ref") for x in fschema["anyOf"] if x.get("type") != "null") or "any"
            if t == "array":
                t = f"list[{_schema_name(fschema.get('items', {}))}]"
            fields.append(f"{fname}{'' if fname in required else '?'}: {t}")
        lines.append(f"**{name}** - " + ", ".join(fields))
        lines.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    total = sum(len(v) for v in by_tag.values())
    print(f"wrote {OUT} ({total} endpoints, {len(components)} schemas)")


if __name__ == "__main__":
    main()
