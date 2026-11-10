from __future__ import annotations

from typing import Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.audit import audit
from app.core.config import settings
from app.core.deps import enrich_user, get_current_user, load_user
from app.core.naming import company_or_name
from app.core.rate_limit import AUTH_LIMIT, limiter
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.db.mongo import DB, Doc, get_db, utcnow
from app.models.enums import NotificationType
from app.schemas.auth import ClientBrief, LoginIn, PasswordChange, ProfileUpdate, RefreshIn, RegisterIn, TokenOut, UserOut
from app.schemas.common import Msg
from app.services.notification_service import notify_admins

router = APIRouter(prefix="/auth", tags=["auth"])


def user_out(db: DB, user: Doc) -> UserOut:
    client = user.get("client")
    if client is None and user.get("role") == "client":
        client = db.client_of_user(user)
    return UserOut(
        id=user.id,
        email=user.get("email", ""),
        full_name=user.get("full_name", ""),
        role=user.get("role", ""),
        is_active=bool(user.get("is_active", True)),
        avatar_url=user.get("avatar_url"),
        phone=user.get("phone"),
        timezone=user.get("timezone"),
        last_login_at=user.get("last_login_at"),
        created_at=user.get("created_at"),
        client=ClientBrief(
            id=client.id,
            company_name=client.get("company_name", ""),
            website=client.get("website"),
            industry=client.get("industry"),
            currency=client.get("currency") or "USD",
            status=client.get("status", "active"),
            onboarding_stage=client.get("onboarding_stage", "new"),
        )
        if client
        else None,
    )


def _issue_tokens(db: DB, user: Doc, request: Request) -> TokenOut:
    access = create_access_token(user.id, user.get("role", ""))
    refresh, expires, jti = create_refresh_token(user.id)
    db.refresh_tokens.insert({"user_id": user.id, "jti": jti, "expires_at": expires, "revoked": False, "user_agent": request.headers.get("user-agent")})
    user = db.users.update(user.id, {"last_login_at": utcnow()}) or user
    user = enrich_user(db, user)
    return TokenOut(access_token=access, refresh_token=refresh, expires_in=settings.access_token_minutes * 60, user=user_out(db, user))


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(AUTH_LIMIT)
def register(request: Request, body: RegisterIn, db: DB = Depends(get_db)):
    email = body.email.lower()
    if db.users.exists({"email": email}):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = db.users.insert(
        {"email": email, "password_hash": hash_password(body.password), "full_name": body.full_name, "role": "client",
         "is_active": True, "avatar_url": None, "phone": None, "timezone": "UTC", "last_login_at": None}
    )
    company = company_or_name(body.company_name, body.full_name)
    client = db.clients.insert(
        {"user_id": user.id, "company_name": company, "website": body.website, "industry": body.industry,
         "brand_notes": None, "drive_folder_id": None, "currency": body.currency.upper(), "status": "active", "onboarding_stage": "new"}
    )
    db.conversations.insert({"client_id": client.id, "last_message_at": None, "last_message_preview": None, "admin_unread": 0, "client_unread": 0})
    audit(db, action="register", entity="user", entity_id=user.id, user=user, request=request)
    notify_admins(
        db,
        type=NotificationType.LEAD.value,
        title=f"New signup: {company}",
        body=f"{body.full_name} ({email}) created an account.",
        link=f"/admin#/clients/{client.id}",
        data={"client_id": client.id},
    )
    try:
        from app.core.jobs import enqueue_job

        enqueue_job("onboarding", {"client_id": client.id})
    except Exception:  # pragma: no cover
        pass
    return _issue_tokens(db, enrich_user(db, user), request)


@router.post("/login", response_model=TokenOut)
@limiter.limit(AUTH_LIMIT)
def login(request: Request, body: LoginIn, db: DB = Depends(get_db)):
    user = db.users.find_one({"email": body.email.lower()})
    if not user or not verify_password(body.password, user.get("password_hash", "")):
        audit(db, action="login_failed", entity="user", actor=body.email, request=request)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account disabled")
    audit(db, action="login", entity="user", entity_id=user.id, user=user, request=request)
    return _issue_tokens(db, enrich_user(db, user), request)


@router.post("/refresh", response_model=TokenOut)
@limiter.limit(AUTH_LIMIT)
def refresh(request: Request, body: RefreshIn, db: DB = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")
    row = db.refresh_tokens.find_one({"jti": payload.get("jti")})
    if not row or row.get("revoked"):
        raise HTTPException(status_code=401, detail="Refresh token revoked")
    user = load_user(db, int(payload["sub"]))
    if not user or not user.get("is_active", True):
        raise HTTPException(status_code=401, detail="User inactive")
    db.refresh_tokens.update(row.id, {"revoked": True})  # rotate
    return _issue_tokens(db, user, request)


@router.post("/logout", response_model=Msg)
def logout(body: RefreshIn, user: Doc = Depends(get_current_user), db: DB = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
        row = db.refresh_tokens.find_one({"jti": payload.get("jti")})
        if row and row.get("user_id") == user.id:
            db.refresh_tokens.update(row.id, {"revoked": True})
    except jwt.PyJWTError:
        pass
    return Msg(message="Logged out")


@router.get("/me", response_model=UserOut)
def me(user: Doc = Depends(get_current_user), db: DB = Depends(get_db)):
    return user_out(db, user)


@router.patch("/me", response_model=UserOut)
def update_me(body: ProfileUpdate, user: Doc = Depends(get_current_user), db: DB = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    user_changes = {k: data[k] for k in ("full_name", "phone", "timezone", "avatar_url") if k in data and data[k] is not None}
    if user_changes:
        db.users.update(user.id, user_changes)
    client = user.get("client")
    if client:
        client_changes = {k: (data[k].upper() if k == "currency" else data[k]) for k in ("company_name", "website", "industry", "brand_notes", "currency") if k in data and data[k] is not None}
        name_now = user_changes.get("full_name") or user.get("full_name")
        if "company_name" in client_changes:
            client_changes["company_name"] = company_or_name(client_changes["company_name"], name_now)
        elif "full_name" in user_changes and client.get("company_name") == user.get("full_name"):
            client_changes["company_name"] = name_now  # individuals: keep their folder/name in step with the profile
        if client_changes:
            db.clients.update(client.id, client_changes)
    audit(db, action="update_profile", entity="user", entity_id=user.id, user=user, after=data)
    fresh = load_user(db, user.id)
    return user_out(db, fresh)


@router.post("/change-password", response_model=Msg)
def change_password(body: PasswordChange, user: Doc = Depends(get_current_user), db: DB = Depends(get_db)):
    if user.get("email") == settings.admin_email.lower():
        raise HTTPException(status_code=403, detail="The primary admin password is set in the .env file (ADMIN_PASSWORD) and cannot be changed here.")
    if not verify_password(body.current_password, user.get("password_hash", "")):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    db.users.update(user.id, {"password_hash": hash_password(body.new_password)})
    db.refresh_tokens.update_many({"user_id": user.id}, {"revoked": True})
    audit(db, action="change_password", entity="user", entity_id=user.id, user=user)
    return Msg(message="Password updated")
