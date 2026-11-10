"""Rate limiting via slowapi."""
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

# headers_enabled must stay False: with it on, slowapi requires every decorated
# endpoint to accept a `response: Response` parameter and raises 500 otherwise.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.rate_limit_default],
    headers_enabled=False,
    enabled=settings.app_env != "test",
)

AUTH_LIMIT = settings.rate_limit_auth
