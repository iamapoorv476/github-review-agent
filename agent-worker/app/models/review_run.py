import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    BigInteger, Boolean, DateTime, Text,
    Integer, Numeric, ForeignKey
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class ReviewRun(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "review_runs"

    pull_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pull_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Job tracking
    bullmq_job_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trigger: Mapped[str] = mapped_column(Text, nullable=False)
    triggered_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status: queued → processing → completed | failed | cancelled
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="queued",
        index=True
    )

    # Timing
    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # LLM usage
    model_used: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cost_usd: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 6), nullable=True
    )
    tool_calls_made: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Results summary
    findings_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    critical_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    high_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    medium_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    low_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # GitHub
    github_review_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True
    )
    review_comment_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Failure handling
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Idempotency
    idempotency_key: Mapped[str] = mapped_column(
        Text,
        unique=True,
        nullable=False,
        index=True
    )

    # Relationships
    pull_request: Mapped["PullRequest"] = relationship(
        back_populates="review_runs"
    )
    findings: Mapped[List["Finding"]] = relationship(
        back_populates="review_run",
        cascade="all, delete-orphan"
    )
    reasoning_steps: Mapped[List["ReasoningStep"]] = relationship(
        back_populates="review_run",
        cascade="all, delete-orphan",
        order_by="ReasoningStep.step_number"
    )

    def __repr__(self) -> str:
        return (
            f"<ReviewRun id={self.id} "
            f"status={self.status} "
            f"findings={self.findings_count}>"
        )