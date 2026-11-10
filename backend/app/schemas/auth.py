from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import Email, ORMModel


class RegisterIn(BaseModel):
    email: Email
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=120)
    company_name: Optional[str] = Field(default="", max_length=160)  # optional: individuals use their own name
    website: Optional[str] = Field(default=None, max_length=255)
    industry: Optional[str] = Field(default=None, max_length=120)
    currency: str = Field(default="USD", pattern="^(USD|GBP|INR)$")

    @field_validator("password")
    @classmethod
    def _strength(cls, v: str) -> str:
        if not any(c.isdigit() for c in v) or not any(c.isalpha() for c in v):
            raise ValueError("Password must contain letters and numbers")
        return v


class LoginIn(BaseModel):
    email: Email
    password: str = Field(min_length=1, max_length=128)


class RefreshIn(BaseModel):
    refresh_token: str


class ClientBrief(ORMModel):
    id: int
    company_name: str
    website: Optional[str] = None
    industry: Optional[str] = None
    currency: str = "USD"
    status: str
    onboarding_stage: str


class UserOut(ORMModel):
    id: int
    email: Email
    full_name: str
    role: str
    is_active: bool
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    timezone: Optional[str] = None
    last_login_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    client: Optional[ClientBrief] = None

    @classmethod
    def from_user(cls, user) -> "UserOut":
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role_name,
            is_active=user.is_active,
            avatar_url=user.avatar_url,
            phone=user.phone,
            timezone=user.timezone,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
            client=ClientBrief.model_validate(user.client) if user.client else None,
        )


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    phone: Optional[str] = Field(default=None, max_length=40)
    timezone: Optional[str] = Field(default=None, max_length=64)
    avatar_url: Optional[str] = Field(default=None, max_length=500)
    company_name: Optional[str] = Field(default=None, max_length=160)
    website: Optional[str] = Field(default=None, max_length=255)
    industry: Optional[str] = Field(default=None, max_length=120)
    brand_notes: Optional[str] = Field(default=None, max_length=5000)
    currency: Optional[str] = Field(default=None, pattern="^(USD|GBP|INR)$")


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)
