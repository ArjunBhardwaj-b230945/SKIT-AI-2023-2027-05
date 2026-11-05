from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class TaxRegimeEnum(str, Enum):
    OLD = "old"
    NEW = "new"


class FilingStatusEnum(str, Enum):
    DRAFT = "draft"
    COMPUTED = "computed"
    VALIDATED = "validated"
    FILED = "filed"


class TaxRecordBase(BaseModel):
    """Base schema for tax record data storage and retrieval."""
    pan_number: str = Field(
        ...,
        min_length=10,
        max_length=10,
        description="Permanent Account Number (PAN)",
        pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$",
    )
    financial_year: str = Field(
        ...,
        description="Financial Year in format YYYY-YY or YYYY-YYYY",
        pattern=r"^\d{4}-\d{2,4}$",
    )
    assessment_year: str = Field(
        ...,
        description="Assessment Year in format YYYY-YY or YYYY-YYYY",
        pattern=r"^\d{4}-\d{2,4}$",
    )
    tax_regime: TaxRegimeEnum = Field(
        default=TaxRegimeEnum.NEW,
        description="Selected Tax Regime (old or new)",
    )
    filing_status: FilingStatusEnum = Field(
        default=FilingStatusEnum.DRAFT,
        description="Current workflow status of the record",
    )
    gross_total_income: float = Field(
        default=0.0,
        ge=0.0,
        description="Gross Total Income (GTI)",
    )
    total_deductions: float = Field(
        default=0.0,
        ge=0.0,
        description="Total eligible deductions (Chapter VI-A)",
    )
    taxable_income: float = Field(
        default=0.0,
        ge=0.0,
        description="Net Taxable Income after deductions",
    )
    total_tax_payable: float = Field(
        default=0.0,
        ge=0.0,
        description="Total computed tax payable after rebate & cess",
    )
    computation_details: dict[str, Any] | None = Field(
        default=None,
        description="Detailed structured computation breakdown or metadata",
    )
    notes: str | None = Field(
        default=None,
        max_length=500,
        description="User notes or remarks for this record",
    )


class TaxRecordCreate(TaxRecordBase):
    """Schema for persisting a new tax record to the database."""
    pass


class TaxRecordUpdate(BaseModel):
    """Schema for updating an existing stored tax record."""
    pan_number: str | None = Field(
        default=None,
        min_length=10,
        max_length=10,
        pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$",
    )
    financial_year: str | None = Field(default=None, pattern=r"^\d{4}-\d{2,4}$")
    assessment_year: str | None = Field(default=None, pattern=r"^\d{4}-\d{2,4}$")
    tax_regime: TaxRegimeEnum | None = None
    filing_status: FilingStatusEnum | None = None
    gross_total_income: float | None = Field(default=None, ge=0.0)
    total_deductions: float | None = Field(default=None, ge=0.0)
    taxable_income: float | None = Field(default=None, ge=0.0)
    total_tax_payable: float | None = Field(default=None, ge=0.0)
    computation_details: dict[str, Any] | None = None
    notes: str | None = Field(default=None, max_length=500)


class TaxRecordResponse(TaxRecordBase):
    """Serialized schema for tax record retrieval responses."""
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaxRecordListResponse(BaseModel):
    """Schema for listing multiple retrieved tax records."""
    total: int
    page: int
    limit: int
    records: list[TaxRecordResponse]


class TaxRecordSummaryResponse(BaseModel):
    """Schema for aggregated tax storage metrics across user records."""
    total_records: int
    draft_count: int
    computed_count: int
    filed_count: int
    total_tax_payable_sum: float
    recorded_assessment_years: list[str]
