import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Integer, JSON, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
import enum
from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class PlanType(str, enum.Enum):
    FREE = "free"
    PRO = "pro"


class ScanStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ScanType(str, enum.Enum):
    GITHUB = "github"
    KUBERNETES = "kubernetes"
    CONTAINER = "container"
    COST = "cost"
    FULL = "full"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    github_id: Mapped[str | None] = mapped_column(String(50), unique=True, index=True)
    github_username: Mapped[str | None] = mapped_column(String(100))
    github_access_token: Mapped[str | None] = mapped_column(String(500))
    full_name: Mapped[str | None] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    plan: Mapped[PlanType] = mapped_column(SAEnum(PlanType), default=PlanType.FREE)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(100))
    scans_used_this_month: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    scans: Mapped[list["Scan"]] = relationship("Scan", back_populates="user", cascade="all, delete-orphan")

    @property
    def scan_limit(self) -> int:
        return 3 if self.plan == PlanType.FREE else 999


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    scan_type: Mapped[ScanType] = mapped_column(SAEnum(ScanType))
    status: Mapped[ScanStatus] = mapped_column(SAEnum(ScanStatus), default=ScanStatus.PENDING, index=True)
    target: Mapped[str] = mapped_column(String(500))  # repo URL, kubeconfig path, etc.
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    results: Mapped[dict | None] = mapped_column(JSON)
    score: Mapped[int | None] = mapped_column(Integer)  # 0-100
    issues_critical: Mapped[int] = mapped_column(Integer, default=0)
    issues_warning: Mapped[int] = mapped_column(Integer, default=0)
    issues_info: Mapped[int] = mapped_column(Integer, default=0)
    celery_task_id: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(String(1000))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship("User", back_populates="scans")
    report: Mapped["Report | None"] = relationship("Report", back_populates="scan", uselist=False)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scans.id"), unique=True)
    s3_key: Mapped[str] = mapped_column(String(500))
    s3_url: Mapped[str | None] = mapped_column(String(1000))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    scan: Mapped["Scan"] = relationship("Scan", back_populates="report")
