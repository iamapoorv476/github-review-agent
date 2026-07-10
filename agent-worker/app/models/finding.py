import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, DateTime, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class Finding(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "findings"

    review_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("review_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Location
    file_path: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    line_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    diff_position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Classification
    category: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    severity: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    rule_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Content
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    suggestion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    code_snippet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # GitHub posting status
    github_comment_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    was_posted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    post_failed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    post_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Developer feedback (future feature — column defined now)
    developer_reaction: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reacted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    review_run: Mapped["ReviewRun"] = relationship(back_populates="findings")

    def __repr__(self) -> str:
        return (
            f"<Finding {self.severity} {self.category} "
            f"at {self.file_path}:{self.line_number}>"
        )