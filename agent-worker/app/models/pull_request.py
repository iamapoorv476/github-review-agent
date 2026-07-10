import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import BigInteger, DateTime, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class PullRequest(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "pull_requests"

    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # GitHub identifiers
    github_pr_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    pr_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # PR metadata
    title: Mapped[str] = mapped_column(Text, nullable=False)
    author_login: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    base_branch: Mapped[str] = mapped_column(Text, nullable=False)
    head_branch: Mapped[str] = mapped_column(Text, nullable=False)
    head_sha: Mapped[str] = mapped_column(Text, nullable=False)

    # Stats
    files_changed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lines_added: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lines_removed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Lifecycle
    pr_opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    pr_closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    pr_merged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    repository: Mapped["Repository"] = relationship(
        back_populates="pull_requests"
    )
    review_runs: Mapped[List["ReviewRun"]] = relationship(
        back_populates="pull_request",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<PullRequest #{self.pr_number} {self.title[:30]}>"