"""Real-time event bridge.

publish(target, type, payload) is callable from sync or async code, from the api
process or the worker. With REDIS_URL set the event goes through a Redis pub/sub
channel and every api process forwards it to the matching WebSocket clients.
Without Redis (tests / tiny dev setups) the event is dispatched in-process.

Targets:  "user:<id>"   one user
          "role:admin"  every admin
          "all"         everyone connected
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Any, Dict, List, Optional, Set

from fastapi import WebSocket

from app.core.config import settings

log = logging.getLogger("events")
CHANNEL = "designflow:events"

_redis_sync = None
_loop: Optional[asyncio.AbstractEventLoop] = None


def _get_redis_sync():
    global _redis_sync
    if not settings.redis_url:
        return None
    if _redis_sync is None:
        import redis

        _redis_sync = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_sync


class ConnectionManager:
    """Tracks open WebSockets per user and per role."""

    def __init__(self) -> None:
        self._by_user: Dict[int, Set[WebSocket]] = {}
        self._roles: Dict[int, str] = {}
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket, user_id: int, role: str) -> None:
        await ws.accept()
        async with self._lock:
            self._by_user.setdefault(user_id, set()).add(ws)
            self._roles[user_id] = role

    async def disconnect(self, ws: WebSocket, user_id: int) -> None:
        async with self._lock:
            conns = self._by_user.get(user_id)
            if conns:
                conns.discard(ws)
                if not conns:
                    self._by_user.pop(user_id, None)
                    self._roles.pop(user_id, None)

    def _targets(self, target: str) -> List[WebSocket]:
        if target == "all":
            return [ws for conns in self._by_user.values() for ws in conns]
        if target.startswith("user:"):
            return list(self._by_user.get(int(target.split(":", 1)[1]), set()))
        if target.startswith("role:"):
            role = target.split(":", 1)[1]
            return [
                ws
                for uid, conns in self._by_user.items()
                if self._roles.get(uid) == role
                for ws in conns
            ]
        return []

    async def dispatch(self, message: Dict[str, Any]) -> None:
        target = message.get("target", "all")
        dead: List[tuple[int, WebSocket]] = []
        text = json.dumps(message, default=str)
        for ws in self._targets(target):
            try:
                await ws.send_text(text)
            except Exception:  # pragma: no cover - network failures
                for uid, conns in self._by_user.items():
                    if ws in conns:
                        dead.append((uid, ws))
        for uid, ws in dead:
            await self.disconnect(ws, uid)

    @property
    def online_user_ids(self) -> List[int]:
        return list(self._by_user.keys())


manager = ConnectionManager()


def set_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop


def publish(target: str, event_type: str, payload: Optional[Dict[str, Any]] = None) -> None:
    """Fire-and-forget. Safe to call from any thread."""
    message = {"target": target, "type": event_type, "payload": payload or {}}
    r = _get_redis_sync()
    if r is not None:
        try:
            r.publish(CHANNEL, json.dumps(message, default=str))
            return
        except Exception as exc:  # pragma: no cover
            log.warning("Redis publish failed (%s); falling back to in-process", exc)
    _dispatch_local(message)


def _dispatch_local(message: Dict[str, Any]) -> None:
    loop = _loop
    if loop is None or loop.is_closed():
        return
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None
    if running is loop:
        loop.create_task(manager.dispatch(message))
    else:
        loop.call_soon_threadsafe(lambda: loop.create_task(manager.dispatch(message)))


async def redis_subscriber(stop: threading.Event) -> None:
    """Runs inside the api process; forwards Redis events to WebSockets."""
    if not settings.redis_url:
        return
    import redis.asyncio as aioredis

    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = client.pubsub()
    await pubsub.subscribe(CHANNEL)
    log.info("Subscribed to %s", CHANNEL)
    try:
        while not stop.is_set():
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if msg and msg.get("type") == "message":
                try:
                    await manager.dispatch(json.loads(msg["data"]))
                except Exception as exc:  # pragma: no cover
                    log.exception("dispatch failed: %s", exc)
            await asyncio.sleep(0.01)
    except asyncio.CancelledError:  # pragma: no cover
        pass
    finally:
        try:
            await pubsub.unsubscribe(CHANNEL)
            await client.aclose()
        except Exception:  # pragma: no cover
            pass
