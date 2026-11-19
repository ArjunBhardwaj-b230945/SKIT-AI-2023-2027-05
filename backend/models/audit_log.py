from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

if TYPE_CHECKING:
    from models.user import User


class AuditLogModel(Base):
    """
    SQLAlchemy model recording database operation traces and state mutations.
    Enables database integrity tracking, compliance logging, and security auditing.
    """
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
        autoincrement=True,
    )

    user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="e.g. USER_LOGIN, RECORD_CREATE, RECORD_UPDATE, RECORD_DELETE",
    )

    entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Target entity, e.g. User, TaxRecord, TaxProfile, ChatSession",
    )

    entity_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )

    details: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Serialized JSON metadata or operation description",
    )

    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    # Relationship to user who triggered the database action
    user: Mapped["User | None"] = relationship(
        "User",
        back_populates="audit_logs",
    )
