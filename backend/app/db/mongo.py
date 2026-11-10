"""MongoDB data layer.

Every collection uses integer ids (from the `counters` collection) so the public API and the
frontend keep the same numeric ids they had with SQL. Documents are returned as `Doc` objects:
plain dicts with attribute access (`req.title`, `req["title"]`) and an `id` mirror of `_id`.

Usage:
    from app.db.mongo import get_db
    db = get_db()
    req = db.requests.get(12)
    db.requests.update(req.id, {"status": "accepted"})
    rows = db.requests.find({"client_id": 3}, sort=[("submitted_at", -1)], limit=50)

MONGO_URI=mongomock:// selects the in-memory mongomock client (used by the tests).
"""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from pymongo import ASCENDING, DESCENDING, ReturnDocument

from app.core.config import settings

log = logging.getLogger("mongo")

# ---------------------------------------------------------------------------
# Concurrency helpers
# ---------------------------------------------------------------------------
_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="dbq")


def parallel(*fns: Callable[[], Any]) -> List[Any]:
    """Run independent reads concurrently: one Atlas round trip (~130 ms) instead of N.
    pymongo's client is thread-safe; on mongomock (tests) the reads simply run in order."""
    if len(fns) <= 1 or (_db is not None and _db.is_mock):
        return [f() for f in fns]
    return list(_pool.map(lambda f: f(), fns))


# Write hooks: on_write("users", fn) -> fn(doc_id) after an update/delete of one document,
# fn(None) after a bulk write. Used by the per-request user cache in core/deps.py.
_write_hooks: Dict[str, List[Callable[[Optional[int]], None]]] = {}


def on_write(collection: str, fn: Callable[[Optional[int]], None]) -> None:
    _write_hooks.setdefault(collection, []).append(fn)


def _fire(collection: str, doc_id: Optional[int]) -> None:
    for fn in _write_hooks.get(collection, ()):
        try:
            fn(doc_id)
        except Exception:  # pragma: no cover - a cache hook must never break a write
            log.exception("write hook for %s failed", collection)

# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _fix(value: Any) -> Any:
    """Make datetimes timezone-aware (pymongo/mongomock may return naive UTC)."""
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    if isinstance(value, dict):
        return {k: _fix(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_fix(v) for v in value]
    return value


class Doc(dict):
    """dict + attribute access. `doc.id` == `doc['_id']`."""

    def __getattr__(self, key: str) -> Any:
        if key == "id":
            return self.get("_id")
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key) from None

    def __setattr__(self, key: str, value: Any) -> None:
        if key == "id":
            self["_id"] = value
        else:
            self[key] = value

    def public(self) -> Dict[str, Any]:
        """Copy with `id` instead of `_id` (for API responses)."""
        out = {k: v for k, v in self.items() if k != "_id"}
        out["id"] = self.get("_id")
        return out


def wrap(raw: Optional[Dict[str, Any]]) -> Optional[Doc]:
    if raw is None:
        return None
    d = Doc(_fix(raw))
    if "_id" in d:
        d["id"] = d["_id"]
    return d


# ---------------------------------------------------------------------------
# Collection wrapper
# ---------------------------------------------------------------------------


class Repo:
    def __init__(self, database: "DB", name: str, timestamps: bool = True) -> None:
        self._db = database
        self.name = name
        self.col = database.raw[name]
        self.timestamps = timestamps

    # --- create ---------------------------------------------------------
    def insert(self, data: Dict[str, Any]) -> Doc:
        doc = dict(data)
        doc.pop("id", None)
        if "_id" not in doc:
            doc["_id"] = self._db.next_id(self.name)
        now = utcnow()
        if self.timestamps:
            doc.setdefault("created_at", now)
            doc.setdefault("updated_at", now)
        self.col.insert_one(doc)
        return wrap(doc)

    # --- read -----------------------------------------------------------
    def get(self, id: Any) -> Optional[Doc]:
        if id is None:
            return None
        try:
            id = int(id)
        except (TypeError, ValueError):
            return None
        return wrap(self.col.find_one({"_id": id}))

    def find_one(self, filter: Optional[Dict[str, Any]] = None, sort: Optional[Sequence[Tuple[str, int]]] = None) -> Optional[Doc]:
        cur = self.col.find(filter or {})
        if sort:
            cur = cur.sort(list(sort))
        cur = cur.limit(1)
        for raw in cur:
            return wrap(raw)
        return None

    def find(
        self,
        filter: Optional[Dict[str, Any]] = None,
        sort: Optional[Sequence[Tuple[str, int]]] = None,
        skip: int = 0,
        limit: int = 0,
        projection: Optional[Dict[str, int]] = None,
    ) -> List[Doc]:
        cur = self.col.find(filter or {}, projection)
        if sort:
            cur = cur.sort(list(sort))
        if skip:
            cur = cur.skip(skip)
        if limit:
            cur = cur.limit(limit)
        return [wrap(r) for r in cur]

    def count(self, filter: Optional[Dict[str, Any]] = None) -> int:
        return self.col.count_documents(filter or {})

    def exists(self, filter: Dict[str, Any]) -> bool:
        return self.col.find_one(filter, {"_id": 1}) is not None

    def distinct(self, field: str, filter: Optional[Dict[str, Any]] = None) -> List[Any]:
        return self.col.distinct(field, filter or {})

    def by_ids(self, ids: Iterable[Any]) -> Dict[Any, Doc]:
        ids = [int(i) for i in ids if i is not None]
        if not ids:
            return {}
        return {d.id: d for d in self.find({"_id": {"$in": ids}})}

    # --- update ---------------------------------------------------------
    def update(self, id: Any, set: Optional[Dict[str, Any]] = None, **ops: Any) -> Optional[Doc]:
        """update(id, {"status": "x"}) or update(id, inc={"count": 1}, push={"items": v}, unset=["field"])."""
        update: Dict[str, Any] = {}
        set = dict(set or {})
        set.pop("_id", None)
        set.pop("id", None)
        if self.timestamps:
            set["updated_at"] = utcnow()
        if set:
            update["$set"] = set
        for op in ("inc", "push", "pull", "addToSet"):
            if ops.get(op):
                update[f"${op}"] = ops[op]
        if ops.get("unset"):
            update["$unset"] = {k: "" for k in ops["unset"]}
        raw = self.col.find_one_and_update({"_id": int(id)}, update, return_document=ReturnDocument.AFTER)
        _fire(self.name, int(id))
        return wrap(raw)

    def update_many(self, filter: Dict[str, Any], set: Dict[str, Any]) -> int:
        set = dict(set)
        if self.timestamps:
            set["updated_at"] = utcnow()
        n = self.col.update_many(filter, {"$set": set}).modified_count
        _fire(self.name, None)
        return n

    def save(self, doc: Doc) -> Doc:
        """Persist every field of a Doc that was modified in place."""
        data = {k: v for k, v in doc.items() if k not in ("_id", "id")}
        return self.update(doc.id, data)

    # --- delete ---------------------------------------------------------
    def delete(self, id: Any) -> bool:
        ok = self.col.delete_one({"_id": int(id)}).deleted_count > 0
        _fire(self.name, int(id))
        return ok

    def delete_many(self, filter: Dict[str, Any]) -> int:
        n = self.col.delete_many(filter).deleted_count
        _fire(self.name, None)
        return n

    # --- misc -----------------------------------------------------------
    def aggregate(self, pipeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [_fix(r) for r in self.col.aggregate(pipeline)]

    def paginate(self, filter: Optional[Dict[str, Any]], sort: Sequence[Tuple[str, int]], page: int, page_size: int) -> Tuple[List[Doc], int]:
        rows, total = parallel(
            lambda: self.find(filter, sort=sort, skip=(page - 1) * page_size, limit=page_size),
            lambda: self.count(filter),
        )
        return rows, total


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

COLLECTIONS: Dict[str, str] = {
    "users": "Login accounts (admin, staff, client). Fields: email, password_hash, full_name, role, is_active, avatar_url, phone, timezone, last_login_at.",
    "refresh_tokens": "Issued refresh tokens: user_id, jti, expires_at, revoked, user_agent.",
    "clients": "Client companies: user_id, company_name, website, industry, brand_notes, drive_folder_id, currency, status, onboarding_stage.",
    "services": "The design services: slug, name, category, tagline, description, long_description, turnaround_days, starting_price (USD), icon, form_schema, deliverables, is_active, sort_order.",
    "projects": "Optional grouping of requests: client_id, name, description, status, drive_folder_id.",
    "service_requests": "Design requests: client_id, project_id, service_id, title, description, brief, priority, status, submitted_at/accepted_at/started_at/review_at/completed_at/rejected_at, rejection_reason, due_at, revision_count, price_amount, price_currency, is_paid, paid_at, current_run_id, pipeline_stage, ai_summary.",
    "designs": "Concept versions: request_id, version, title, concept, concept_data, file_id, preview_url, generated_by, status, qa_score, qa_notes.",
    "revisions": "Client feedback rounds: request_id, design_id, round, feedback, change_items, status, submitted_by, file_ids, resolved_at.",
    "deliveries": "Delivered packages: request_id, message, file_ids, download_links, delivered_by, delivered_at, version.",
    "files": "Stored files: owner_user_id, client_id, request_id, kind, original_name, stored_name, backend, path, drive_file_id, public_url, mime_type, size_bytes, version, parent_file_id, checksum, meta.",
    "brand_assets": "Client brand assets: client_id, type, name, file_id, value, version, meta.",
    "payments": "Invoices/payments per request: client_id, request_id, amount, currency, settled_amount, settled_currency, provider, provider_payment_id, status, invoice_number, invoice_url, description, paid_at.",
    "notifications": "Per-user notifications: user_id, type, title, body, link, service_id, request_id, data, is_read, read_at.",
    "conversations": "One chat thread per client: client_id, last_message_at, last_message_preview, admin_unread, client_unread.",
    "chat_messages": "Messages: conversation_id, sender_id, body, file_id, read_at.",
    "support_tickets": "Support tickets: client_id, subject, status, priority, category, messages (list), resolved_at.",
    "agents": "The 11 AI agents: key, name, description, status, enabled, tasks_completed, tasks_failed, success_rate, last_run_at, last_error, current_activity, schedule, config, sort_order.",
    "agent_logs": "Agent steps: agent_key, run_id, request_id, level, status, step, message, input_summary, output_summary, tokens_in, tokens_out, duration_ms.",
    "pipeline_events": "Live feed of what the agents did on a request (shown on the See-in-live page): request_id, run_id, type, agent_key, title, body, data, level.",
    "lead_database": "Leads: company_name, website, industry, location, contact_name, contact_email, contact_phone, score, analysis, status, source, notes, client_id.",
    "outreach_history": "Outreach emails: lead_id, channel, subject, body, status, sent_at, follow_up_at, follow_up_count, reply_text, generated_by.",
    "audit_logs": "Audit trail: user_id, actor, action, entity, entity_id, ip, user_agent, before, after.",
    "analytics": "Daily metric snapshots: metric, dimension, value, date.",
    "counters": "Integer id sequences per collection.",
}

NO_TIMESTAMP_UPDATE = {"notifications", "files", "agent_logs", "pipeline_events", "audit_logs", "analytics", "refresh_tokens", "chat_messages", "counters"}

INDEXES: Dict[str, List[Tuple[List[Tuple[str, int]], Dict[str, Any]]]] = {
    "users": [([("email", ASCENDING)], {"unique": True})],
    "refresh_tokens": [([("jti", ASCENDING)], {"unique": True}), ([("user_id", ASCENDING)], {})],
    "clients": [([("user_id", ASCENDING)], {"unique": True})],
    "services": [([("slug", ASCENDING)], {"unique": True}), ([("sort_order", ASCENDING)], {})],
    "projects": [([("client_id", ASCENDING)], {})],
    "service_requests": [([("client_id", ASCENDING)], {}), ([("service_id", ASCENDING)], {}), ([("status", ASCENDING)], {}), ([("submitted_at", DESCENDING)], {})],
    "designs": [([("request_id", ASCENDING), ("version", ASCENDING)], {})],
    "revisions": [([("request_id", ASCENDING)], {})],
    "deliveries": [([("request_id", ASCENDING)], {})],
    "files": [([("request_id", ASCENDING)], {}), ([("client_id", ASCENDING)], {})],
    "brand_assets": [([("client_id", ASCENDING)], {})],
    "payments": [([("client_id", ASCENDING)], {}), ([("request_id", ASCENDING)], {}), ([("provider_payment_id", ASCENDING)], {})],
    "notifications": [([("user_id", ASCENDING), ("is_read", ASCENDING)], {}), ([("created_at", DESCENDING)], {})],
    "conversations": [([("client_id", ASCENDING)], {"unique": True})],
    "chat_messages": [([("conversation_id", ASCENDING)], {})],
    "support_tickets": [([("client_id", ASCENDING)], {}), ([("status", ASCENDING)], {})],
    "agents": [([("key", ASCENDING)], {"unique": True})],
    "agent_logs": [([("agent_key", ASCENDING)], {}), ([("request_id", ASCENDING)], {}), ([("created_at", DESCENDING)], {})],
    "pipeline_events": [([("request_id", ASCENDING), ("_id", ASCENDING)], {})],
    "lead_database": [([("contact_email", ASCENDING)], {}), ([("status", ASCENDING)], {})],
    "outreach_history": [([("lead_id", ASCENDING)], {})],
    "audit_logs": [([("created_at", DESCENDING)], {}), ([("action", ASCENDING)], {})],
    "analytics": [([("metric", ASCENDING), ("dimension", ASCENDING), ("date", ASCENDING)], {"unique": True})],
}


class DB:
    """Holds the client and one Repo per collection (db.users, db.requests, ...)."""

    def __init__(self, uri: str, name: str) -> None:
        self.uri = uri
        self.name = name
        self.is_mock = uri.startswith("mongomock")
        if self.is_mock:
            import mongomock

            self.client = mongomock.MongoClient(tz_aware=True)
        else:
            from pymongo import MongoClient

            self.client = MongoClient(uri, tz_aware=True, tzinfo=timezone.utc, serverSelectionTimeoutMS=15000, appname="designflow")
        self.raw = self.client[name]
        self._lock = threading.Lock()
        for cname in COLLECTIONS:
            if cname == "counters":
                continue
            setattr(self, cname, Repo(self, cname, timestamps=cname not in NO_TIMESTAMP_UPDATE))
        # short aliases
        self.requests: Repo = self.service_requests
        self.leads: Repo = self.lead_database
        self.outreach: Repo = self.outreach_history
        self.tickets: Repo = self.support_tickets
        self.messages: Repo = self.chat_messages
        self.assets: Repo = self.brand_assets

    # --- ids ------------------------------------------------------------
    def next_id(self, name: str) -> int:
        raw = self.raw["counters"].find_one_and_update(
            {"_id": name}, {"$inc": {"seq": 1}}, upsert=True, return_document=ReturnDocument.AFTER
        )
        return int(raw["seq"])

    # --- lifecycle ------------------------------------------------------
    def ensure_indexes(self) -> None:
        for cname, specs in INDEXES.items():
            for keys, opts in specs:
                try:
                    self.raw[cname].create_index(keys, **opts)
                except Exception as exc:  # pragma: no cover
                    log.warning("index on %s %s failed: %s", cname, keys, exc)

    def ping(self) -> bool:
        try:
            self.client.admin.command("ping")
            return True
        except Exception:
            return self.is_mock

    def drop_all(self) -> None:
        """Tests only."""
        for cname in list(COLLECTIONS):
            self.raw[cname].drop()

    # --- convenience joins ------------------------------------------------
    def user_of_client(self, client: Optional[Doc]) -> Optional[Doc]:
        return self.users.get(client.user_id) if client else None

    def client_of_user(self, user: Optional[Doc]) -> Optional[Doc]:
        return self.clients.find_one({"user_id": user.id}) if user else None

    def admin_ids(self) -> List[int]:
        return [u.id for u in self.users.find({"role": "admin", "is_active": True}, projection={"_id": 1})]


_db: Optional[DB] = None
_db_lock = threading.Lock()


def get_db() -> DB:
    """Process-wide singleton (pymongo's client is thread-safe)."""
    global _db
    if _db is None:
        with _db_lock:
            if _db is None:
                _db = DB(settings.mongo_uri, settings.mongo_db)
    return _db


def reset_db() -> None:
    global _db
    _db = None
