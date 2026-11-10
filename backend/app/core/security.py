"""Password hashing and JWT helpers."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
import jwt

from app.core.config import settings

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(user_id: int, role: str, extra: Optional[Dict[str, Any]] = None) -> str:
    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": _now(),
        "exp": _now() + timedelta(minutes=settings.access_token_minutes),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def create_refresh_token(user_id: int) -> tuple[str, datetime, str]:
    """Returns (token, expires_at, jti)."""
    jti = secrets.token_urlsafe(24)
    expires = _now() + timedelta(days=settings.refresh_token_days)
    payload = {"sub": str(user_id), "type": "refresh", "jti": jti, "iat": _now(), "exp": expires}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM), expires, jti


def decode_token(token: str) -> Dict[str, Any]:
    """Raises jwt exceptions on failure."""
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])


def random_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)
