from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ServiceOut(ORMModel):
    id: int
    slug: str
    name: str
    category: str
    tagline: Optional[str] = None
    description: Optional[str] = None
    long_description: Optional[str] = None
    turnaround_days: int
    starting_price: Optional[float] = None
    icon: Optional[str] = None
    form_schema: List[Dict[str, Any]] = []
    deliverables: List[str] = []
    is_active: bool
    sort_order: int
    pending_count: int = 0
    total_requests: int = 0
    prices: Dict[str, float] = {}  # {"USD": 149, "GBP": 118, "INR": 12520}
    price_unit: str = "per request"


class ServiceUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    category: Optional[str] = Field(default=None, max_length=80)
    tagline: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    long_description: Optional[str] = None
    turnaround_days: Optional[int] = Field(default=None, ge=0, le=60)
    starting_price: Optional[float] = Field(default=None, ge=0)
    icon: Optional[str] = Field(default=None, max_length=64)
    form_schema: Optional[List[Dict[str, Any]]] = None
    deliverables: Optional[List[str]] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class ServiceAnalytics(BaseModel):
    service_id: int
    slug: str
    name: str
    total: int
    by_status: Dict[str, int]
    avg_turnaround_hours: Optional[float] = None
    last_30_days: int
    revision_rate: float
    trend: List[Dict[str, Any]]
