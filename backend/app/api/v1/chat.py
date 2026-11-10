from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.deps import get_current_user
from app.core.events import publish
from app.db.mongo import DB, Doc, get_db, utcnow
from app.models.enums import NotificationType
from app.schemas.misc import ChatMessageIn, ChatMessageOut, ConversationOut
from app.services.notification_service import admin_user_ids, notify

router = APIRouter(prefix="/chat", tags=["chat"])


def _new_conversation(db: DB, client_id: int) -> Doc:
    return db.conversations.insert(
        {"client_id": client_id, "last_message_at": None, "last_message_preview": None, "admin_unread": 0, "client_unread": 0}
    )


def _conversation_for(db: DB, user: Doc, conversation_id: Optional[int] = None, client_id: Optional[int] = None) -> Doc:
    if user.get("is_admin"):
        conv = None
        if conversation_id:
            conv = db.conversations.get(conversation_id)
        elif client_id:
            conv = db.conversations.find_one({"client_id": client_id})
            if not conv and db.clients.get(client_id):
                conv = _new_conversation(db, client_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return conv
    client = user.get("client")
    if not client:
        raise HTTPException(status_code=403, detail="Client account required")
    conv = db.conversations.find_one({"client_id": client.id})
    if not conv:
        conv = _new_conversation(db, client.id)
    return conv


def _msg_out(db: DB, m: Doc, users: Dict[int, Optional[Doc]]) -> ChatMessageOut:
    sid = m.get("sender_id")
    if sid not in users:
        users[sid] = db.users.get(sid)
    sender = users[sid]
    fname = None
    if m.get("file_id"):
        f = db.files.get(m["file_id"])
        fname = f.get("original_name") if f else None
    return ChatMessageOut(
        id=m.id,
        conversation_id=m.get("conversation_id"),
        sender_id=sid,
        sender_name=sender.get("full_name", "") if sender else "",
        sender_role=sender.get("role", "") if sender else "",
        body=m.get("body"),
        file_id=m.get("file_id"),
        file_name=fname,
        read_at=m.get("read_at"),
        created_at=m.get("created_at"),
    )


@router.get("/conversations", response_model=List[ConversationOut])
def conversations(db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    if user.get("is_admin"):
        convs = db.conversations.find({})
        convs.sort(key=lambda c: (c.get("last_message_at") is None, -(c["last_message_at"].timestamp()) if c.get("last_message_at") else 0))
    else:
        convs = [_conversation_for(db, user)]
    clients = db.clients.by_ids({c.get("client_id") for c in convs})
    users = db.users.by_ids({c.get("user_id") for c in clients.values()})
    out = []
    for c in convs:
        client = clients.get(c.get("client_id"))
        if not client:
            continue
        cuser = users.get(client.get("user_id"))
        out.append(
            ConversationOut(
                id=c.id,
                client_id=c.get("client_id"),
                company_name=client.get("company_name", ""),
                client_name=cuser.get("full_name", "") if cuser else "",
                last_message_at=c.get("last_message_at"),
                last_message_preview=c.get("last_message_preview"),
                unread=c.get("admin_unread", 0) if user.get("is_admin") else c.get("client_unread", 0),
            )
        )
    return out


@router.get("/messages", response_model=List[ChatMessageOut])
def messages(
    conversation_id: Optional[int] = None,
    client_id: Optional[int] = None,
    before_id: Optional[int] = None,
    limit: int = Query(50, le=200),
    db: DB = Depends(get_db),
    user: Doc = Depends(get_current_user),
):
    conv = _conversation_for(db, user, conversation_id, client_id)
    filt: dict = {"conversation_id": conv.id}
    if before_id:
        filt["_id"] = {"$lt": before_id}
    rows = db.messages.find(filt, sort=[("_id", -1)], limit=limit)
    rows.reverse()
    now = utcnow()
    changed = False
    for m in rows:
        if m.get("sender_id") != user.id and m.get("read_at") is None:
            db.messages.update(m.id, {"read_at": now})
            m["read_at"] = now
            changed = True
    db.conversations.update(conv.id, {"admin_unread": 0} if user.get("is_admin") else {"client_unread": 0})
    if changed:
        publish(f"user:{user.id}", "chat_read", {"conversation_id": conv.id})
    users: Dict[int, Optional[Doc]] = {}
    return [_msg_out(db, m, users) for m in rows]


@router.post("/messages", response_model=ChatMessageOut, status_code=201)
def send_message(
    body: ChatMessageIn,
    conversation_id: Optional[int] = None,
    client_id: Optional[int] = None,
    db: DB = Depends(get_db),
    user: Doc = Depends(get_current_user),
):
    if not body.body and not body.file_id:
        raise HTTPException(status_code=400, detail="Message body or file required")
    conv = _conversation_for(db, user, conversation_id, client_id)
    if body.file_id:
        f = db.files.get(body.file_id)
        if not f or (not user.get("is_admin") and f.get("owner_user_id") != user.id):
            raise HTTPException(status_code=404, detail="File not found")
        db.files.update(f.id, {"kind": "chat", "client_id": conv.get("client_id")})
    now = utcnow()
    m = db.messages.insert({"conversation_id": conv.id, "sender_id": user.id, "body": body.body, "file_id": body.file_id, "read_at": None, "created_at": now})
    preview = (body.body or "📎 File")[:120]
    client = db.clients.get(conv.get("client_id"))
    if user.get("is_admin"):
        # replying implies the admin has seen the thread
        db.conversations.update(conv.id, {"last_message_at": now, "last_message_preview": preview, "admin_unread": 0}, inc={"client_unread": 1})
        targets = [client.get("user_id")] if client else []
        link = "/portal#/chat"
    else:
        db.conversations.update(conv.id, {"last_message_at": now, "last_message_preview": preview, "client_unread": 0}, inc={"admin_unread": 1})
        targets = admin_user_ids(db)
        link = f"/admin#/chat/{conv.id}"
    out = _msg_out(db, m, {})
    payload = {"conversation_id": conv.id, "message": out.model_dump(mode="json")}
    notify(
        db,
        [t for t in targets if t],
        type=NotificationType.CHAT.value,
        title=f"New message from {user.get('full_name', '')}",
        body=preview,
        link=link,
        data={"conversation_id": conv.id},
    )
    for uid in targets:
        if uid:
            publish(f"user:{uid}", "chat_message", payload)
    publish(f"user:{user.id}", "chat_message", payload)
    return out
