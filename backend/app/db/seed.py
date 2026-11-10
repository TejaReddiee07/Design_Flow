"""Idempotent seed: indexes, the primary admin (from .env), the services, the 11 agents.

No sample data is ever created: clients, requests, leads and payments come only from real use.

Run:  python -m app.db.seed
"""
from __future__ import annotations

import logging

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.db.mongo import DB, Doc, get_db
from app.db.seed_data import AGENTS, SERVICES

log = logging.getLogger("seed")


def seed_admin(db: DB) -> Doc:
    """The primary admin is defined by ADMIN_EMAIL / ADMIN_PASSWORD / ADMIN_NAME in .env.
    Every run re-applies them, so .env is the only place these credentials can be changed."""
    email = settings.admin_email.lower()
    admin = db.users.find_one({"email": email}) or db.users.find_one({"role": "admin"}, sort=[("_id", 1)])
    if not admin:
        admin = db.users.insert({"email": email, "password_hash": hash_password(settings.admin_password), "full_name": settings.admin_name,
                                 "role": "admin", "is_active": True, "avatar_url": None, "phone": None, "timezone": "UTC", "last_login_at": None})
        log.info("Created primary admin %s", email)
        return admin
    changes = {}
    if admin.get("email") != email:
        changes["email"] = email
    if not verify_password(settings.admin_password, admin.get("password_hash", "")):
        changes["password_hash"] = hash_password(settings.admin_password)
    if admin.get("full_name") != settings.admin_name:
        changes["full_name"] = settings.admin_name
    changes.update(is_active=True, role="admin")
    if "email" in changes or "password_hash" in changes:
        db.refresh_tokens.update_many({"user_id": admin.id}, {"revoked": True})
        log.info("Primary admin updated from .env")
    return db.users.update(admin.id, changes)


def seed_services(db: DB) -> dict:
    out = {}
    for data in SERVICES:
        payload = {k: v for k, v in data.items() if k != "price_unit"}
        payload.setdefault("is_active", True)
        svc = db.services.find_one({"slug": data["slug"]})
        if not svc:
            svc = db.services.insert(payload)
        else:
            # keep admin edits (price, delivery days, name, active flag)
            keep = {k: svc.get(k) for k in ("starting_price", "turnaround_days", "name") if svc.get(k) not in (None, 0, "")}
            if svc.get("is_active") is not None:
                keep["is_active"] = bool(svc["is_active"])
            svc = db.services.update(svc.id, {**payload, **keep})
        out[svc.slug] = svc
    # services removed from the catalogue are hidden (history is kept)
    db.services.update_many({"slug": {"$nin": list(out)}}, {"is_active": False})
    return out


def seed_agents(db: DB) -> dict:
    out = {}
    for data in AGENTS:
        ag = db.agents.find_one({"key": data["key"]})
        if not ag:
            ag = db.agents.insert({**data, "status": "idle", "enabled": True, "tasks_completed": 0, "tasks_failed": 0, "success_rate": 100.0,
                                   "last_run_at": None, "last_error": None, "current_activity": "Idle", "config": {}})
        else:
            ag = db.agents.update(ag.id, {"name": data["name"], "description": data["description"], "sort_order": data["sort_order"]})
        out[ag.key] = ag
    return out


def fix_client_names(db: DB) -> int:
    """Clients who typed a placeholder ("Personal User", "N/A", "Self") as their company are shown by their own name."""
    from app.core.naming import company_or_name, is_placeholder_company

    fixed = 0
    for c in db.clients.find({}, projection={"company_name": 1, "user_id": 1}):
        if is_placeholder_company(c.get("company_name")):
            u = db.users.get(c.get("user_id"))
            name = company_or_name(c.get("company_name"), u.get("full_name") if u else "")
            if name and name != c.get("company_name"):
                db.clients.update(c.id, {"company_name": name})
                fixed += 1
    if fixed:
        log.info("Replaced %d placeholder company name(s) with the client's own name", fixed)
    return fixed


def run_seed(demo: bool | None = None) -> None:
    db = get_db()
    db.ensure_indexes()
    seed_admin(db)
    seed_services(db)
    seed_agents(db)
    fix_client_names(db)
    log.info("Seed complete")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_seed()
