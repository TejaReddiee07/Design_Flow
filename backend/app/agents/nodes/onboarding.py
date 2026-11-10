"""Onboarding Agent: sets up a new client (folder, welcome message, asset checklist)."""
from __future__ import annotations

from typing import Any, Dict

from app.agents import control
from app.agents.llm import complete
from app.agents.nodes.common import pretty
from app.core.events import publish
from app.db.mongo import get_db, utcnow
from app.models.enums import NotificationType
from app.services.notification_service import admin_user_ids, notify, notify_admins
from app.services.storage import get_storage

KEY = "onboarding"
SYSTEM = """You are the Onboarding Agent at a premium design studio. A new client just signed up.
Write a warm welcome message (3-5 sentences) that explains how to submit requests and asks for
brand assets. Return JSON with keys: welcome_message, asset_checklist (list of 4-6 items)."""


def run(client_id: int) -> Dict[str, Any]:
    db = get_db()
    client = db.clients.get(client_id)
    if not client:
        return {}
    user = db.users.get(client.get("user_id"))
    with control.running(db, KEY, f"Onboarding: {client.get('company_name')}", run_id=f"onboard-{client_id}") as ctx:
        # 1. Workspace folder (local path or Drive folder id)
        storage = get_storage()
        try:
            folder = storage.create_folder(f"{client.id}-{client.get('company_name', '')}"[:80].replace("/", "-"), "clients")
            db.clients.update(client.id, {"drive_folder_id": folder})
        except Exception as exc:  # pragma: no cover
            control.log(db, KEY, f"Folder creation failed: {exc}", step="folder", status="failed", level="warn")
        # 2. Welcome copy
        res = complete(
            KEY, SYSTEM,
            f"Company: {client.get('company_name')}\nContact: {user.get('full_name') if user else ''}\nIndustry: {client.get('industry') or 'n/a'}\nWebsite: {client.get('website') or 'n/a'}",
        )
        data = res.data or {}
        welcome = data.get("welcome_message") or f"Welcome to Designflow, {client.get('company_name')}! Upload your brand assets and submit your first request whenever you're ready."
        checklist = data.get("asset_checklist") or ["Logo", "Brand colours", "Fonts", "Guidelines"]
        # 3. Chat message from the admin account
        admins = admin_user_ids(db)
        conv = db.conversations.find_one({"client_id": client.id})
        if not conv:
            conv = db.conversations.insert({"client_id": client.id, "last_message_at": None, "last_message_preview": None, "admin_unread": 0, "client_unread": 0})
        if admins:
            body = welcome + "\n\nTo get started, please share:\n" + "\n".join(f"• {item}" for item in checklist)
            now = utcnow()
            db.messages.insert({"conversation_id": conv.id, "sender_id": admins[0], "body": body, "file_id": None, "read_at": None, "created_at": now})
            db.conversations.update(conv.id, {"last_message_at": now, "last_message_preview": body[:120]}, inc={"client_unread": 1})
        # 4. Asset request ticket + stage
        db.tickets.insert(
            {
                "client_id": client.id, "subject": "Brand assets needed", "status": "open", "priority": "normal", "category": "onboarding",
                "messages": [{"sender": "admin", "name": "Onboarding Agent", "body": "Please upload: " + ", ".join(checklist), "at": utcnow().isoformat()}],
                "resolved_at": None,
            }
        )
        if client.get("onboarding_stage", "new") == "new":
            db.clients.update(client.id, {"onboarding_stage": "assets_requested"})
        if client.get("user_id"):
            notify(db, [client.user_id], type=NotificationType.SYSTEM.value, title="Welcome to Designflow",
                   body="Your workspace is ready. Please upload your brand assets.", link="/portal#/files")
        notify_admins(db, type=NotificationType.AGENT.value, title=f"Client onboarded: {client.get('company_name')}",
                      body="Workspace created, welcome message sent, assets requested.", link=f"/admin#/clients/{client.id}")
        if client.get("user_id"):
            publish(f"user:{client.user_id}", "chat_message", {"conversation_id": conv.id})
        ctx.update(tokens_in=res.tokens_in, tokens_out=res.tokens_out, output=pretty(data))
        return data
