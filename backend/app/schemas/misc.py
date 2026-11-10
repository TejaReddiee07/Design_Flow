"""Schemas for notifications, chat, support, billing, leads, agents, analytics, admin."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.common import Email, ORMModel


# ---- Notifications -------------------------------------------------------
class NotificationOut(ORMModel):
    id: int
    type: str
    title: str
    body: Optional[str] = None
    link: Optional[str] = None
    service_id: Optional[int] = None
    request_id: Optional[int] = None
    data: Dict[str, Any] = {}
    is_read: bool
    created_at: Optional[datetime] = None


class MarkReadIn(BaseModel):
    ids: List[int] = Field(default_factory=list)


# ---- Chat ----------------------------------------------------------------
class ChatMessageOut(ORMModel):
    id: int
    conversation_id: int
    sender_id: int
    sender_name: str = ""
    sender_role: str = ""
    body: Optional[str] = None
    file_id: Optional[int] = None
    file_name: Optional[str] = None
    read_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class ChatMessageIn(BaseModel):
    body: Optional[str] = Field(default=None, max_length=5000)
    file_id: Optional[int] = None


class ConversationOut(BaseModel):
    id: int
    client_id: int
    company_name: str
    client_name: str
    last_message_at: Optional[datetime] = None
    last_message_preview: Optional[str] = None
    unread: int = 0


# ---- Support -------------------------------------------------------------
class TicketCreate(BaseModel):
    subject: str = Field(min_length=3, max_length=200)
    message: str = Field(min_length=1, max_length=10000)
    priority: str = "normal"
    category: Optional[str] = None


class TicketReply(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    status: Optional[str] = None


class TicketOut(ORMModel):
    id: int
    client_id: int
    company_name: str = ""
    subject: str
    status: str
    priority: str
    category: Optional[str] = None
    messages: List[Dict[str, Any]] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None


# ---- Billing -------------------------------------------------------------
class PlanOut(BaseModel):
    key: str
    name: str
    price: float
    currency: str
    interval: str
    active_request_limit: int
    turnaround: str
    tagline: str
    features: List[str]
    highlight: bool


class CheckoutIn(BaseModel):
    plan: str
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


class CheckoutOut(BaseModel):
    provider: str
    checkout_url: Optional[str] = None
    activated: bool = False
    subscription: Optional[Dict[str, Any]] = None


class SubscriptionOut(ORMModel):
    id: int
    client_id: int
    company_name: str = ""
    plan: str
    plan_name: str = ""
    status: str
    provider: str
    amount: float
    currency: str
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    active_request_limit: int
    cancel_at_period_end: bool
    created_at: Optional[datetime] = None


class PaymentOut(ORMModel):
    id: int
    client_id: int
    company_name: str = ""
    subscription_id: Optional[int] = None
    request_id: Optional[int] = None
    request_title: Optional[str] = None
    amount: float
    currency: str
    settled_amount: Optional[float] = None
    settled_currency: str = "GBP"
    provider: str
    status: str
    invoice_number: Optional[str] = None
    invoice_url: Optional[str] = None
    description: Optional[str] = None
    paid_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class PaymentDetailOut(PaymentOut):
    """One invoice with how it was paid: method, transaction ids, settlement and history."""
    provider_payment_id: Optional[str] = None
    client_name: str = ""
    client_email: str = ""
    service_name: Optional[str] = None
    request_status: Optional[str] = None
    method: Dict[str, Any] = {}
    details: Dict[str, Any] = {}
    details_error: Optional[str] = None
    history: List[Dict[str, Any]] = []


class ManualPaymentIn(BaseModel):
    client_id: int
    amount: float = Field(gt=0)
    description: Optional[str] = None
    status: str = "paid"
    request_id: Optional[int] = None
    currency: Optional[str] = None


class LeadConvertIn(BaseModel):
    service_slug: Optional[str] = None
    title: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=5000)
    currency: str = "USD"
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)
    send_email: bool = True


# ---- Leads / Outreach ----------------------------------------------------
class LeadOut(ORMModel):
    id: int
    company_name: str
    website: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    score: int
    analysis: Dict[str, Any] = {}
    status: str
    source: str
    notes: Optional[str] = None
    client_id: Optional[int] = None
    outreach_count: int = 0
    created_at: Optional[datetime] = None


class LeadCreate(BaseModel):
    company_name: str = Field(min_length=1, max_length=160)
    website: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[Email] = None
    contact_phone: Optional[str] = None
    notes: Optional[str] = None
    score: int = 0


class LeadUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    score: Optional[int] = Field(default=None, ge=0, le=100)
    contact_name: Optional[str] = None
    contact_email: Optional[Email] = None
    industry: Optional[str] = None


class LeadGenerateIn(BaseModel):
    industry: Optional[str] = None
    location: Optional[str] = None
    count: int = Field(default=5, ge=1, le=25)
    service_slug: Optional[str] = None


class OutreachOut(ORMModel):
    id: int
    lead_id: int
    company_name: str = ""
    contact_email: Optional[str] = None
    channel: str
    subject: Optional[str] = None
    body: str
    status: str
    sent_at: Optional[datetime] = None
    follow_up_at: Optional[datetime] = None
    follow_up_count: int
    reply_text: Optional[str] = None
    generated_by: str
    created_at: Optional[datetime] = None


class OutreachDraftIn(BaseModel):
    lead_ids: List[int] = Field(min_length=1)
    tone: str = "friendly"


class OutreachSendIn(BaseModel):
    outreach_ids: List[int] = Field(min_length=1)


# ---- Agents --------------------------------------------------------------
class AgentOut(ORMModel):
    id: int
    key: str
    name: str
    description: Optional[str] = None
    status: str
    enabled: bool
    tasks_completed: int
    tasks_failed: int
    success_rate: float
    last_run_at: Optional[datetime] = None
    last_error: Optional[str] = None
    current_activity: Optional[str] = None
    schedule: Optional[str] = None
    config: Dict[str, Any] = {}
    sort_order: int


class AgentLogOut(ORMModel):
    id: int
    agent_key: str
    run_id: Optional[str] = None
    request_id: Optional[int] = None
    level: str
    status: str
    step: Optional[str] = None
    message: str
    input_summary: Optional[str] = None
    output_summary: Optional[str] = None
    tokens_in: int
    tokens_out: int
    duration_ms: int
    created_at: Optional[datetime] = None


class AgentConfigIn(BaseModel):
    schedule: Optional[str] = None
    enabled: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None


class AgentRunIn(BaseModel):
    payload: Dict[str, Any] = Field(default_factory=dict)


# ---- Contact (public) ----------------------------------------------------
class ContactIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: Email
    company: Optional[str] = Field(default=None, max_length=160)
    website: Optional[str] = Field(default=None, max_length=255)
    message: str = Field(min_length=5, max_length=5000)
    service: Optional[str] = None


# ---- Admin users ---------------------------------------------------------
class AdminUserOut(ORMModel):
    id: int
    email: str
    full_name: str
    role: str = ""
    is_active: bool
    last_login_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class AdminUserCreate(BaseModel):
    email: Email
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=120)
    role: str = "staff"


class AdminUserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)


class AuditOut(ORMModel):
    id: int
    user_id: Optional[int] = None
    actor: str
    action: str
    entity: str
    entity_id: Optional[int] = None
    ip: Optional[str] = None
    before: Optional[Dict[str, Any]] = None
    after: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None


class BrandAssetOut(ORMModel):
    id: int
    client_id: int
    type: str
    name: str
    file_id: Optional[int] = None
    value: Optional[str] = None
    version: int
    meta: Dict[str, Any] = {}
    download_url: Optional[str] = None
    created_at: Optional[datetime] = None


class BrandAssetIn(BaseModel):
    type: str
    name: str = Field(min_length=1, max_length=160)
    file_id: Optional[int] = None
    value: Optional[str] = Field(default=None, max_length=255)
    client_id: Optional[int] = None
