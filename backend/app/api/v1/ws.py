"""WebSocket endpoint: /ws?token=<access token>"""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.core.deps import get_user_from_token
from app.core.events import manager
from app.db.mongo import get_db
from app.services.notification_service import unread_count

log = logging.getLogger("ws")
router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    token = ws.query_params.get("token")
    if not token:
        await ws.close(code=4401)
        return
    try:
        db = get_db()
        user = await asyncio.to_thread(get_user_from_token, db, token)
        uid, role = user.id, user.get("role", "")
        count = await asyncio.to_thread(unread_count, db, uid)
    except Exception:
        await ws.close(code=4401)
        return

    await manager.connect(ws, uid, role)
    try:
        await ws.send_text(json.dumps({"type": "hello", "payload": {"user_id": uid, "role": role, "unread_count": count}}))
        while True:
            try:
                raw = await asyncio.wait_for(ws.receive_text(), timeout=45)
            except asyncio.TimeoutError:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_text(json.dumps({"type": "ping"}))
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if msg.get("type") == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # pragma: no cover
        log.debug("ws closed: %s", exc)
    finally:
        await manager.disconnect(ws, uid)
