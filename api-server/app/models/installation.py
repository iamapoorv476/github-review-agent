import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import BigInteger, Boolean, DateTime, Text, ARRAY, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class Installation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "installations"

    # GitHub identifiers
    github_install_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        index=True
    )
    account_login: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    account_type: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )  # 'Organization' or 'User'
    account_avatar_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )

    # Auth tokens (stored encrypted)
    access_token: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    access_token_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Lifecycle
    installed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )
    uninstalled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True
    )

    # Settings
    review_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )
    review_categories: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=lambda: ["security", "performance", "quality"]
    )

    # Relationships
    repositories: Mapped[List["Repository"]] = relationship(
        back_populates="installation",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<Installation id={self.id} "
            f"account={self.account_login} "
            f"active={self.is_active}>"
        )