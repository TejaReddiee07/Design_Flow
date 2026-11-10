"""FastAPI dependencies: database handle, current user, role guards."""
from __future__ import annotations

import copy
import threading
import time
from typing import Callable, Dict, Iterable, Optional, Tuple

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.security import decode_token
from app.db import mongo
from app.db.mongo import DB, Doc, get_db

bearer = HTTPBearer(auto_error=False)

# Every API call resolves the caller from its token: one or two database round trips (about 130 ms
# each against Atlas). A short cache removes that cost; any write to users/clients clears it.
USER_CACHE_SECONDS = 0.0 if settings.app_env == "test" else 20.0
_user_cache: Dict[int, Tuple[float, Doc]] = {}
_cache_lock = threading.Lock()


def invalidate_user_cache(user_id: Optional[int] = None) -> None:
    with _cache_lock:
        if user_id is None:
            _user_cache.clear()
        else:
            _user_cache.pop(int(user_id), None)


mongo.on_write("users", lambda doc_id: invalidate_user_cache(doc_id))
mongo.on_write("clients", lambda doc_id: invalidate_user_cache(None))


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def enrich_user(db: DB, user: Doc) -> Doc:
    """Attach the conveniences the routers rely on: role_name, is_admin, client."""
    user["role_name"] = user.get("role", "")
    user["is_admin"] = user.get("role") == "admin"
    user["client"] = db.client_of_user(user) if user.get("role") == "client" else None
    return user


def load_user(db: DB, user_id: int) -> Optional[Doc]:
    if USER_CACHE_SECONDS:
        with _cache_lock:
            hit = _user_cache.get(int(user_id))
        if hit and hit[0] > time.monotonic():
            return copy.deepcopy(hit[1])
    user = db.users.get(user_id)
    if not user:
        return None
    user = enrich_user(db, user)
    if USER_CACHE_SECONDS:
        with _cache_lock:
            _user_cache[int(user_id)] = (time.monotonic() + USER_CACHE_SECONDS, copy.deepcopy(user))
    return user


def get_user_from_token(db: DB, token: str) -> Doc:
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Token expired")
    except jwt.PyJWTError:
        raise _unauthorized("Invalid token")
    if payload.get("type") != "access":
        raise _unauthorized("Invalid token type")
    user = load_user(db, int(payload["sub"]))
    if not user or not user.get("is_active", True):
        raise _unauthorized("User not found or inactive")
    return user


def get_current_user(
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    db: DB = Depends(get_db),
) -> Doc:
    token = creds.credentials if creds else request.query_params.get("token")
    if not token:
        raise _unauthorized()
    user = get_user_from_token(db, token)
    request.state.user = user
    return user


def get_optional_user(
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    db: DB = Depends(get_db),
) -> Optional[Doc]:
    if not creds:
        return None
    try:
        return get_user_from_token(db, creds.credentials)
    except HTTPException:
        return None


def require_roles(*roles: str) -> Callable[..., Doc]:
    allowed: Iterable[str] = roles

    def _guard(user: Doc = Depends(get_current_user)) -> Doc:
        if user.get("role") not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return _guard


require_admin = require_roles("admin")
require_client = require_roles("client")
require_any = require_roles("admin", "client", "staff")


def get_current_client(user: Doc = Depends(get_current_user)) -> Doc:
    if user.get("role") != "client" or not user.get("client"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Client account required")
    return user["client"]


def client_scope(user: Doc, client_id: Optional[int]) -> Optional[int]:
    """Admins may act on any client; clients are forced to their own id."""
    if user.get("is_admin"):
        return client_id
    if not user.get("client"):
        raise HTTPException(status_code=403, detail="Client account required")
    return user["client"].id
