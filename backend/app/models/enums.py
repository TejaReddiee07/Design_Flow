"""String enums shared by models, schemas and services."""
from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    def __str__(self) -> str:  # pragma: no cover
        return str(self.value)


class Role(StrEnum):
    ADMIN = "admin"
    CLIENT = "client"
    STAFF = "staff"


class ClientStatus(StrEnum):
    TRIAL = "trial"
    ACTIVE = "active"
    PAUSED = "paused"
    CHURNED = "churned"


class OnboardingStage(StrEnum):
    NEW = "new"
    ASSETS_REQUESTED = "assets_requested"
    ASSETS_RECEIVED = "assets_received"
    ACTIVE = "active"


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class Priority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class RequestStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    COMPLETED = "completed"


class DesignStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"


class RevisionStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


class SubscriptionPlan(StrEnum):
    STARTER = "starter"
    PRO = "pro"
    PREMIUM = "premium"


class SubscriptionStatus(StrEnum):
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    PAUSED = "paused"
    CANCELED = "canceled"


class NotificationType(StrEnum):
    NEW_REQUEST = "new_request"
    REQUEST_STATUS = "request_status"
    REVISION = "revision"
    FILE_UPLOAD = "file_upload"
    PAYMENT = "payment"
    LEAD = "lead"
    AGENT = "agent"
    APPROVAL_NEEDED = "approval_needed"
    DELIVERY = "delivery"
    CHAT = "chat"
    SUPPORT = "support"
    SYSTEM = "system"


class AgentStatus(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class LeadStatus(StrEnum):
    NEW = "new"
    CONTACTED = "contacted"
    REPLIED = "replied"
    QUALIFIED = "qualified"
    CONVERTED = "converted"
    REJECTED = "rejected"


class OutreachStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    SENT = "sent"
    REPLIED = "replied"
    BOUNCED = "bounced"


class TicketStatus(StrEnum):
    OPEN = "open"
    PENDING = "pending"
    RESOLVED = "resolved"
    CLOSED = "closed"


class FileKind(StrEnum):
    UPLOAD = "upload"
    DESIGN = "design"
    DELIVERY = "delivery"
    BRAND_ASSET = "brand_asset"
    CHAT = "chat"
    REVISION = "revision"


class BrandAssetType(StrEnum):
    LOGO = "logo"
    FONT = "font"
    COLOR = "color"
    GUIDELINE = "guideline"
    IMAGE = "image"
    OTHER = "other"


AGENT_KEYS = [
    "lead",
    "outreach",
    "onboarding",
    "project_manager",
    "strategy",
    "content",
    "design",
    "revision",
    "qa",
    "delivery",
    "marketing",
]
