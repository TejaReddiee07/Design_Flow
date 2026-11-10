from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.common import Email, ORMModel


class ClientOut(ORMModel):
    id: int
    user_id: int
    email: str = ""
    full_name: str = ""
    company_name: str
    website: Optional[str] = None
    industry: Optional[str] = None
    brand_notes: Optional[str] = None
    drive_folder_id: Optional[str] = None
    currency: str = "USD"
    status: str
    onboarding_stage: str
    active_requests: int = 0
    unpaid_requests: int = 0
    total_requests: int = 0
    total_paid: float = 0.0
    created_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None


class ClientCreate(BaseModel):
    email: Email
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=120)
    company_name: Optional[str] = Field(default="", max_length=160)  # optional: individuals use their own name
    website: Optional[str] = None
    industry: Optional[str] = None
    brand_notes: Optional[str] = None
    currency: str = Field(default="USD", pattern="^(USD|GBP|INR)$")


class ClientUpdate(BaseModel):
    company_name: Optional[str] = Field(default=None, max_length=160)
    website: Optional[str] = Field(default=None, max_length=255)
    industry: Optional[str] = Field(default=None, max_length=120)
    brand_notes: Optional[str] = None
    currency: Optional[str] = Field(default=None, pattern="^(USD|GBP|INR)$")
    status: Optional[str] = None
    onboarding_stage: Optional[str] = None
    drive_folder_id: Optional[str] = None
    is_active: Optional[bool] = None


class ClientOverview(BaseModel):
    client: ClientOut
    requests_by_status: Dict[str, int]
    recent_requests: List[Dict[str, Any]]
    payments: List[Dict[str, Any]]
    brand_assets: List[Dict[str, Any]]
    projects: List[Dict[str, Any]]


class ProjectOut(ORMModel):
    id: int
    client_id: int
    company_name: str = ""
    name: str
    description: Optional[str] = None
    status: str
    drive_folder_id: Optional[str] = None
    request_count: int = 0
    created_at: Optional[datetime] = None


class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: Optional[str] = Field(default=None, max_length=5000)
    client_id: Optional[int] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=160)
    description: Optional[str] = Field(default=None, max_length=5000)
    status: Optional[str] = None
