"""Shared helpers for agent nodes."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.db.mongo import DB, Doc


def brief_text(service: Doc, req: Doc) -> str:
    """Render the request brief as readable key/value lines using the service form labels."""
    labels = {f["key"]: f.get("label", f["key"]) for f in (service.get("form_schema") or [])}
    lines = []
    for k, v in (req.get("brief") or {}).items():
        if v in (None, "", []):
            continue
        val = ", ".join(map(str, v)) if isinstance(v, list) else str(v)
        lines.append(f"- {labels.get(k, k)}: {val}")
    return "\n".join(lines) or "- (no structured brief fields)"


def brand_context(db: DB, client: Doc) -> str:
    assets = db.assets.find({"client_id": client.id})
    asset_lines = [f"- {a.get('type')}: {a.get('name')}" + (f" = {a['value']}" if a.get("value") else "") for a in assets]
    return (
        f"Company: {client.get('company_name')}\n"
        f"Industry: {client.get('industry') or 'n/a'}\n"
        f"Website: {client.get('website') or 'n/a'}\n"
        f"Brand notes: {client.get('brand_notes') or 'none provided'}\n"
        f"Brand assets:\n" + ("\n".join(asset_lines) if asset_lines else "- none uploaded yet")
    )


def request_context(db: DB, req: Doc) -> str:
    service = db.services.get(req.service_id) or Doc({"name": "?", "category": "", "deliverables": [], "form_schema": []})
    client = db.clients.get(req.client_id) or Doc({"company_name": "?", "id": 0})
    wishes = (req.get("brief") or {}).get("about_and_wishes") or ""
    instruction = f"CLIENT'S OWN DESCRIPTION OF THEIR BUSINESS AND HOW THEY WANT THIS DONE (follow it closely):\n{wishes}\n\n" if wishes else ""
    return (
        instruction
        + f"Service: {service.get('name')} ({service.get('category')})\n"
        f"Title: {req.get('title')}\n"
        f"Priority: {req.get('priority')}\n"
        f"Description: {req.get('description') or 'n/a'}\n"
        f"Deliverables expected: {', '.join(service.get('deliverables') or [])}\n"
        f"Brief:\n{brief_text(service, req)}\n\n{brand_context(db, client)}"
    )


def pretty(data: Optional[Dict[str, Any]], limit: int = 6000) -> str:
    if not data:
        return ""
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)[:limit]


def as_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    if value in (None, ""):
        return []
    return [str(value)]
