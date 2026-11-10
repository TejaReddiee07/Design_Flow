from __future__ import annotations

import re
from typing import Annotated, Any, Dict, Generic, List, Optional, TypeVar

from pydantic import AfterValidator, BaseModel, ConfigDict

T = TypeVar("T")

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def _validate_email(v: str) -> str:
    v = (v or "").strip().lower()
    if len(v) > 254 or not _EMAIL_RE.match(v):
        raise ValueError("Invalid email address")
    return v


# Permissive email type: accepts .local / .test domains used in dev and demo accounts.
Email = Annotated[str, AfterValidator(_validate_email)]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Msg(BaseModel):
    ok: bool = True
    message: str = ""
    data: Optional[Dict[str, Any]] = None


class Page(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
