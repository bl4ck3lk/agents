"""SQLAlchemy models for agents web app."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agents.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    pass


class User(SQLAlchemyBaseUserTableUUID, Base, TimestampMixin):
    """User model for authentication."""

    __tablename__ = "users"

    # Additional fields beyond fastapi-users defaults
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # Platform key access control
    can_use_platform_key: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    monthly_usage_limit_usd: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2), nullable=True
    )

    # Relationships
    api_keys: Mapped[list["APIKey"]] = relationship(
        "APIKey", back_populates="user", cascade="all, delete-orphan"
    )
    web_jobs: Mapped[list["WebJob"]] = relationship(
        "WebJob", back_populates="user", cascade="all, delete-orphan"
    )
    usage_records: Mapped[list["Usage"]] = relationship(
        "Usage", back_populates="user", cascade="all, delete-orphan"
    )


class APIKey(Base, TimestampMixin):
    """Encrypted LLM API keys for users."""

    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'openai', 'anthropic', etc.
    encrypted_key: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # Fernet-encrypted
    name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )  # User-friendly label

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="api_keys")


class WebJob(Base):
    """Web job linking user to TaskQ task."""

    __tablename__ = "web_jobs"

    id: Mapped[str] = mapped_column(
        String(50), primary_key=True
    )  # job_20231119_143022
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    taskq_task_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), nullable=True, index=True
    )  # FK to TaskQ tasks table

    # File URLs
    input_file_url: Mapped[str] = mapped_column(Text, nullable=False)
    output_file_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Job configuration
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Progress tracking (denormalized from TaskQ for quick access)
    total_units: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    processed_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False, index=True
    )  # pending, running, completed, failed, cancelled

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="web_jobs")
    usage_records: Mapped[list["Usage"]] = relationship(
        "Usage", back_populates="web_job", cascade="all, delete-orphan"
    )


class Usage(Base):
    """Usage tracking for billing."""

    __tablename__ = "usage"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("web_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Token usage
    tokens_input: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_output: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 6), default=Decimal("0"), nullable=False
    )

    # Extended tracking fields
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    used_platform_key: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    raw_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 6), default=Decimal("0"), server_default="0", nullable=False
    )
    markup_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 6), default=Decimal("0"), server_default="0", nullable=False
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="usage_records")
    web_job: Mapped["WebJob"] = relationship("WebJob", back_populates="usage_records")


class PlatformAPIKey(Base, TimestampMixin):
    """Platform-owned API keys (not user-specific)."""

    __tablename__ = "platform_api_keys"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    provider: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # 'openrouter', 'openai', etc.
    encrypted_key: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # Fernet-encrypted
    name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )  # Admin-friendly label
    base_url: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )  # e.g., 'https://openrouter.ai/api/v1'
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )


class SystemSettings(Base):
    """System-wide settings (key-value store)."""

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ModelPricing(Base):
    """Rate card for billing - model pricing with markup."""

    __tablename__ = "model_pricing"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    model_pattern: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )  # e.g., 'gpt-4o*', 'claude-3*'
    provider: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    input_cost_per_million: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False
    )
    output_cost_per_million: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False
    )
    markup_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("20"), server_default="20", nullable=False
    )
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    effective_to: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # NULL = active
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
