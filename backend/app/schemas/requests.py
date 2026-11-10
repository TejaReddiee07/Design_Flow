from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.enums import Priority, RequestStatus
from app.schemas.common import ORMModel


class RequestCreate(BaseModel):
    service_id: Optional[int] = None
    service_slug: Optional[str] = None
    project_id: Optional[int] = None
    title: str = Field(min_length=3, max_length=200)
    description: Optional[str] = Field(default=None, max_length=10000)
    brief: Dict[str, Any] = Field(default_factory=dict)
    priority: Priority = Priority.NORMAL
    file_ids: List[int] = Field(default_factory=list)
    client_id: Optional[int] = None  # admin may create on behalf of a client


class RequestUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3, max_length=200)
    description: Optional[str] = Field(default=None, max_length=10000)
    brief: Optional[Dict[str, Any]] = None
    priority: Optional[Priority] = None
    project_id: Optional[int] = None
    due_at: Optional[datetime] = None


class RejectIn(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=2000)


class StatusIn(BaseModel):
    status: RequestStatus
    note: Optional[str] = Field(default=None, max_length=2000)


class FileOut(ORMModel):
    id: int
    kind: str
    original_name: str
    mime_type: str
    size_bytes: int
    version: int
    public_url: Optional[str] = None
    request_id: Optional[int] = None
    created_at: Optional[datetime] = None
    download_url: Optional[str] = None


class DesignOut(ORMModel):
    id: int
    request_id: int
    version: int
    title: Optional[str] = None
    concept: Optional[str] = None
    concept_data: Dict[str, Any] = {}
    file_id: Optional[int] = None
    preview_url: Optional[str] = None
    generated_by: str
    status: str
    qa_score: Optional[float] = None
    qa_notes: Optional[str] = None
    created_at: Optional[datetime] = None
    # Design engine output: every deliverable file of this version (see app/agents/tools/design_engine).
    # Each item: {file_id, name, format, role, label, width, height, page, thumb_file_id}
    files: List[Dict[str, Any]] = []
    package_file_id: Optional[int] = None
    service_slug: Optional[str] = None


class RevisionOut(ORMModel):
    id: int
    request_id: int
    design_id: Optional[int] = None
    round: int
    feedback: str
    change_items: List[Any] = []
    status: str
    file_ids: List[int] = []
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None


class DeliveryOut(ORMModel):
    id: int
    request_id: int
    message: Optional[str] = None
    file_ids: List[int] = []
    download_links: List[Dict[str, Any]] = []
    delivered_by: str
    delivered_at: Optional[datetime] = None
    version: int
    design_id: Optional[int] = None
    package_file_id: Optional[int] = None
    files: List[Dict[str, Any]] = []  # same item shape as DesignOut.files


class RequestOut(ORMModel):
    id: int
    client_id: int
    client_name: str = ""
    company_name: str = ""
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    service_id: int
    service_name: str = ""
    service_slug: str = ""
    title: str
    description: Optional[str] = None
    brief: Dict[str, Any] = {}
    priority: str
    status: str
    pipeline_stage: Optional[str] = None
    ai_summary: Optional[str] = None
    submitted_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    review_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    due_at: Optional[datetime] = None
    revision_count: int = 0
    price_amount: Optional[float] = None
    price_currency: str = "USD"
    is_paid: bool = False
    paid_at: Optional[datetime] = None
    turnaround_days: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class RequestDetail(RequestOut):
    designs: List[DesignOut] = []
    revisions: List[RevisionOut] = []
    deliveries: List[DeliveryOut] = []
    files: List[FileOut] = []
    timeline: List[Dict[str, Any]] = []


class RevisionCreate(BaseModel):
    feedback: str = Field(min_length=3, max_length=10000)
    design_id: Optional[int] = None
    file_ids: List[int] = Field(default_factory=list)


class DesignCreate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    concept: Optional[str] = None
    concept_data: Dict[str, Any] = Field(default_factory=dict)
    file_id: Optional[int] = None
    preview_url: Optional[str] = None


class DeliveryCreate(BaseModel):
    message: Optional[str] = Field(default=None, max_length=5000)
    file_ids: List[int] = Field(default_factory=list)
    mark_completed: bool = False
