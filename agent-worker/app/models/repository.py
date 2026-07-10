import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import BigInteger, Boolean, DateTime, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class Repository(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "repositories"

    # Foreign key to installation
    installation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("installations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # GitHub identifiers
    github_repo_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        index=True
    )
    owner: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True
    )
    is_private: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )
    default_branch: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="main"
    )

    # Denormalized stats for dashboard performance
    total_reviews: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )
    total_findings: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    # Lifecycle
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )
    last_reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Settings
    review_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )

    # Relationships
    installation: Mapped["Installation"] = relationship(
        back_populates="repositories"
    )
    pull_requests: Mapped[List["PullRequest"]] = relationship(
        back_populates="repository",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Repository id={self.id} full_name={self.full_name}>"