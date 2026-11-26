from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class ITRFilingCreate(BaseModel):
    """Schema to submit and finalize an application ITR filing into the database."""
    assessment_year: str = Field(..., pattern=r"^\d{4}-\d{2,4}$", examples=["2025-26"])
    financial_year: str = Field(..., pattern=r"^\d{4}-\d{2,4}$", examples=["2024-25"])
    pan_number: str = Field(..., min_length=10, max_length=10, pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$")
    itr_type: Literal["ITR-1", "ITR-2", "ITR-3", "ITR-4"] = Field(default="ITR-1")
    gross_total_income: float = Field(default=0.0, ge=0.0)
    total_deductions: float = Field(default=0.0, ge=0.0)
    taxable_income: float = Field(default=0.0, ge=0.0)
    total_tax_payable: float = Field(default=0.0, ge=0.0)
    taxes_paid: float = Field(default=0.0, ge=0.0)
    refund_or_payable: float = Field(default=0.0)
    computation_payload: dict[str, Any] | None = Field(default=None)
    verification_mode: Literal["aadhaar_otp", "net_banking", "bank_account", "demat", "offline"] = Field(
        default="aadhaar_otp"
    )


class ITRFilingResponse(BaseModel):
    """Serialized schema for finalized ITR filing records."""
    id: int
    user_id: int
    acknowledgement_number: str
    assessment_year: str
    financial_year: str
    itr_type: str
    filing_status: str
    pan_number: str
    gross_total_income: float
    total_deductions: float
    taxable_income: float
    total_tax_payable: float
    taxes_paid: float
    refund_or_payable: float
    computation_payload: dict[str, Any] | None
    verification_mode: str
    verification_status: str
    submission_timestamp: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ITRFilingListResponse(BaseModel):
    """Paginated collection of submitted ITR filings."""
    total: int
    filings: list[ITRFilingResponse]


class ApplicationDashboardResponse(BaseModel):
    """Aggregated dashboard telemetry summarizing all user application data."""
    user_id: int
    email: str
    total_filings_submitted: int
    draft_records_count: int
    total_tax_computed: float
    total_refund_claimed: float
    active_chat_sessions: int
    latest_acknowledgement_number: str | None
    last_activity_timestamp: datetime | None


class ApplicationDataExportResponse(BaseModel):
    """Comprehensive data export of all application state for the authenticated user."""
    exported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    user: dict[str, Any]
    profiles: list[dict[str, Any]]
    tax_records: list[dict[str, Any]]
    itr_filings: list[dict[str, Any]]
    chat_messages_count: int
