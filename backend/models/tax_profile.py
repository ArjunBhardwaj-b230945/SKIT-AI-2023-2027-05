from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

if TYPE_CHECKING:
    from models.user import User


class TaxProfileModel(Base):
    """
    SQLAlchemy model representing a complete user tax profile and filing snapshot.
    Persists taxpayer identification, verified bank info, and computation summary.
    """
    __tablename__ = "tax_profiles"

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

    pan_number: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        index=True,
    )

    full_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    date_of_birth: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    aadhaar_last_four: Mapped[str | None] = mapped_column(
        String(4),
        nullable=True,
    )

    bank_account_number: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    bank_ifsc: Mapped[str | None] = mapped_column(
        String(11),
        nullable=True,
    )

    address: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    salary_income: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    total_deductions: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    recommended_regime: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="new",
    )

    total_tax: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    refund_due: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
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

    # Relationship to parent user
    user: Mapped["User"] = relationship(
        "User",
        back_populates="tax_profiles",
    )
