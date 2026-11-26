from datetime import datetime, timezone
import json
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

if TYPE_CHECKING:
    from models.user import User


class ITRFilingModel(Base):
    """
    SQLAlchemy model representing an officially submitted Income Tax Return (ITR) filing.
    Finalizes the application data lifecycle with verified acknowledgement tracking.
    """
    __tablename__ = "itr_filings"

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

    acknowledgement_number: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        index=True,
        nullable=False,
        comment="Unique official ITR acknowledgement tracking identifier",
    )

    assessment_year: Mapped[str] = mapped_column(
        String(9),
        nullable=False,
        index=True,
    )

    financial_year: Mapped[str] = mapped_column(
        String(9),
        nullable=False,
        index=True,
    )

    itr_type: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="ITR-1",
    )

    filing_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="submitted",
        comment="submitted, verified, processed, defective",
    )

    pan_number: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        index=True,
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

    taxes_paid: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    refund_or_payable: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    computation_payload: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Serialized JSON payload containing itemized tax computation components",
    )

    verification_mode: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="aadhaar_otp",
    )

    verification_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="verified",
    )

    submission_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
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
        back_populates="itr_filings",
    )

    def get_computation_dict(self) -> dict[str, Any] | None:
        """Helper to parse stored JSON computation details."""
        if not self.computation_payload:
            return None
        try:
            return json.loads(self.computation_payload)
        except (ValueError, TypeError):
            return None

    def set_computation_dict(self, data: dict[str, Any] | None) -> None:
        """Helper to serialize computation payload to JSON string."""
        if data is None:
            self.computation_payload = None
        else:
            self.computation_payload = json.dumps(data)
