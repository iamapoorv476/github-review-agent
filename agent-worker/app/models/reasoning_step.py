import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class ReasoningStep(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "reasoning_steps"

    review_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("review_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Ordering
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Step type: thought | tool_call | tool_result | finding | summary
    step_type: Mapped[str] = mapped_column(Text, nullable=False)

    # Content
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tool_input: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    tool_output_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timing
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Token usage per step
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    review_run: Mapped["ReviewRun"] = relationship(
        back_populates="reasoning_steps"
    )

    def __repr__(self) -> str:
        return (
            f"<ReasoningStep #{self.step_number} "
            f"type={self.step_type} "
            f"run={self.review_run_id}>"
        )