from datetime import datetime, timezone
import json
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

if TYPE_CHECKING:
    from models.user import User


class TaxRecord(Base):
    """
    SQLAlchemy model representing stored user tax computations and filing data.
    Provides persistent data storage and retrieval linked to authenticated users.
    """
    __tablename__ = "tax_records"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    pan_number: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        index=True,
    )

    financial_year: Mapped[str] = mapped_column(
        String(9),
        nullable=False,
        index=True,
    )

    assessment_year: Mapped[str] = mapped_column(
        String(9),
        nullable=False,
        index=True,
    )

    tax_regime: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="new",
    )

    filing_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
    )

    gross_total_income: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    total_deductions: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    taxable_income: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    total_tax_payable: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    computation_details: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="JSON string containing itemized calculation components",
    )

    notes: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="tax_records",
    )

    def get_computation_dict(self) -> dict[str, Any] | None:
        """Helper to parse stored JSON computation details."""
        if not self.computation_details:
            return None
        try:
            return json.loads(self.computation_details)
        except (ValueError, TypeError):
            return None

    def set_computation_dict(self, data: dict[str, Any] | None) -> None:
        """Helper to serialize computation details to JSON string."""
        if data is None:
            self.computation_details = None
        else:
            self.computation_details = json.dumps(data)
