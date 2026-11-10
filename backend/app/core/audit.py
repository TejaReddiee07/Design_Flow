"""Audit log helper."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import Request

from app.db.mongo import DB, Doc, utcnow


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items() if k != "_id"}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    return str(value)


def audit(
    db: DB,
    *,
    action: str,
    entity: str,
    entity_id: Optional[int] = None,
    user: Optional[Doc] = None,
    actor: Optional[str] = None,
    before: Optional[Dict[str, Any]] = None,
    after: Optional[Dict[str, Any]] = None,
    request: Optional[Request] = None,
) -> Doc:
    return db.audit_logs.insert(
        {
            "user_id": user.id if user else None,
            "actor": actor or (user.get("email") if user else "system"),
            "action": action,
            "entity": entity,
            "entity_id": entity_id,
            "before": _jsonable(before) if before is not None else None,
            "after": _jsonable(after) if after is not None else None,
            "ip": request.client.host if request and request.client else None,
            "user_agent": request.headers.get("user-agent") if request else None,
            "created_at": utcnow(),
        }
    )
