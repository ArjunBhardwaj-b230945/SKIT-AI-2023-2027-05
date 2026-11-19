from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class SalaryIncomeInput(BaseModel):
    """Salary income components as extracted from Form 16 Part B."""
    gross_salary: float = Field(default=0.0, ge=0.0, description="Gross salary u/s 17(1)")
    perquisites_17_2: float = Field(default=0.0, ge=0.0, description="Value of perquisites u/s 17(2)")
    profits_in_lieu_17_3: float = Field(default=0.0, ge=0.0, description="Profits in lieu of salary u/s 17(3)")
    hra_received: float = Field(default=0.0, ge=0.0, description="House Rent Allowance received from employer")
    actual_rent_paid: float = Field(default=0.0, ge=0.0, description="Actual rent paid by the employee")
    is_metro_city: bool = Field(default=False, description="True if residing in Delhi, Mumbai, Kolkata, or Chennai")
    standard_deduction: float = Field(default=0.0, ge=0.0, description="Standard deduction u/s 16(ia) - auto applied")
    professional_tax: float = Field(default=0.0, ge=0.0, description="Tax on employment u/s 16(iii)")


class HousePropertyIncomeInput(BaseModel):
    """House property income/loss details."""
    gross_rent_received: float = Field(default=0.0, ge=0.0, description="Annual rent received if let out")
    municipal_taxes_paid: float = Field(default=0.0, ge=0.0, description="Municipal taxes paid by owner")
    housing_loan_interest: float = Field(
        default=0.0,
        ge=0.0,
        description="Interest paid on borrowed capital for self-occupied/let-out property u/s 24(b)",
    )


class OtherSourcesIncomeInput(BaseModel):
    """Income from other sources."""
    savings_interest: float = Field(default=0.0, ge=0.0, description="Interest from savings bank accounts")
    fixed_deposit_interest: float = Field(default=0.0, ge=0.0, description="Interest from fixed deposits / recurring deposits")
    dividend_income: float = Field(default=0.0, ge=0.0, description="Dividends received from shares / mutual funds")
    other_income: float = Field(default=0.0, ge=0.0, description="Any other taxable income")


class ChapterVIADeductionsInput(BaseModel):
    """Deductions claimed under Chapter VI-A (Old Tax Regime only)."""
    section_80c: float = Field(
        default=0.0,
        ge=0.0,
        description="EPF, PPF, ELSS, Life Insurance, Tuition Fees (capped at ₹1,50,000)",
    )
    section_80ccc: float = Field(default=0.0, ge=0.0, description="Pension fund contributions")
    section_80ccd_1: float = Field(default=0.0, ge=0.0, description="NPS employee contribution")
    section_80ccd_1b: float = Field(
        default=0.0,
        ge=0.0,
        description="Additional NPS contribution up to ₹50,000",
    )
    section_80d_self_family: float = Field(
        default=0.0,
        ge=0.0,
        description="Medical insurance premium for self, spouse, and children (up to ₹25k / ₹50k for senior citizen)",
    )
    section_80d_parents: float = Field(
        default=0.0,
        ge=0.0,
        description="Medical insurance premium for parents (up to ₹25k / ₹50k for senior citizen parents)",
    )
    parents_are_senior_citizens: bool = Field(default=False, description="True if parents are aged 60 or above")
    section_80e: float = Field(default=0.0, ge=0.0, description="Interest on higher education loan")
    section_80g: float = Field(default=0.0, ge=0.0, description="Eligible donations to approved funds/charities")
    section_80tta_ttb: float = Field(default=0.0, ge=0.0, description="Savings/deposit interest deduction (auto calculated)")


class TaxesPaidInput(BaseModel):
    """Taxes already deducted or deposited with the government."""
    tds_salary: float = Field(default=0.0, ge=0.0, description="TDS as per Form 16 Part A")
    tds_other: float = Field(default=0.0, ge=0.0, description="TDS from other sources / Form 26AS")
    advance_tax: float = Field(default=0.0, ge=0.0, description="Advance tax paid before fiscal year end")
    self_assessment_tax: float = Field(default=0.0, ge=0.0, description="Self-assessment tax paid u/s 140A")


class TaxComputationRequest(BaseModel):
    """Comprehensive payload to compute tax and compare regimes."""
    assessment_year: str = Field(
        default="2025-26",
        description="Assessment year (e.g. 2024-25, 2025-26, 2026-27)",
    )
    financial_year: str = Field(
        default="2024-25",
        description="Financial year (e.g. 2023-24, 2024-25, 2025-26)",
    )
    date_of_birth: str | None = Field(
        default=None,
        description="Date of birth in YYYY-MM-DD format (used to apply senior citizen slabs in Old Regime)",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    salary: SalaryIncomeInput = Field(default_factory=SalaryIncomeInput)
    house_property: HousePropertyIncomeInput = Field(default_factory=HousePropertyIncomeInput)
    other_sources: OtherSourcesIncomeInput = Field(default_factory=OtherSourcesIncomeInput)
    deductions: ChapterVIADeductionsInput = Field(default_factory=ChapterVIADeductionsInput)
    taxes_paid: TaxesPaidInput = Field(default_factory=TaxesPaidInput)


class SlabDetail(BaseModel):
    """Detailed breakdown for an individual tax slab."""
    slab_name: str
    taxable_in_slab: float
    rate_percentage: float
    tax_amount: float


class RegimeComputationResult(BaseModel):
    """Detailed tax computation for a single regime."""
    regime_name: Literal["New Regime (115BAC)", "Old Regime"]
    gross_total_income: float
    standard_deduction: float
    hra_exemption: float
    loss_from_house_property: float
    total_deductions_chapter_via: float
    net_taxable_income: float
    slab_breakdown: list[SlabDetail]
    gross_tax_liability: float
    rebate_87a: float
    marginal_relief: float
    tax_after_rebate: float
    health_and_education_cess: float
    total_tax_payable: float
    total_taxes_paid: float
    balance_payable_or_refund: float
    is_refund: bool


class TaxComputationResponse(BaseModel):
    """Complete response containing parallel regime computations and optimal recommendation."""
    assessment_year: str
    financial_year: str
    recommended_regime: Literal["New Regime (115BAC)", "Old Regime", "Either (Equal)"]
    tax_savings_with_recommended: float
    summary: str
    new_regime: RegimeComputationResult
    old_regime: RegimeComputationResult
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DocumentReconciliationRequest(BaseModel):
    """Input payload to cross-validate Form 16 vs Form 26AS vs AIS."""
    employee_pan: str = Field(..., min_length=10, max_length=10, pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$")
    form16_tds: float = Field(..., ge=0.0, description="Total TDS as reported in Form 16 Part A")
    form26as_pan: str = Field(..., min_length=10, max_length=10, pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$")
    form26as_tds: float = Field(..., ge=0.0, description="Total TDS as reported in Form 26AS Part A")
    form16_salary: float = Field(default=0.0, ge=0.0)
    ais_salary: float = Field(default=0.0, ge=0.0)


class DocumentReconciliationResponse(BaseModel):
    """Reconciliation validation output flags and compliance status."""
    pan_match: bool
    tds_match: bool
    tds_variance: float
    salary_match: bool
    salary_variance: float
    can_proceed: bool
    validation_flags: list[str]
    reconciliation_summary: str


class TaxProfileCreate(BaseModel):
    """Schema to persist a user's complete tax filing profile."""
    assessment_year: str = Field(..., pattern=r"^\d{4}-\d{2,4}$")
    financial_year: str = Field(..., pattern=r"^\d{4}-\d{2,4}$")
    pan_number: str = Field(..., min_length=10, max_length=10, pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$")
    full_name: str = Field(..., min_length=2, max_length=100)
    date_of_birth: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    aadhaar_last_four: str | None = Field(default=None, min_length=4, max_length=4, pattern=r"^\d{4}$")
    bank_account_number: str | None = Field(default=None, max_length=30)
    bank_ifsc: str | None = Field(default=None, max_length=11)
    address: str | None = Field(default=None, max_length=255)
    salary_income: float = Field(default=0.0, ge=0.0)
    total_deductions: float = Field(default=0.0, ge=0.0)
    recommended_regime: str = Field(default="new")
    total_tax: float = Field(default=0.0, ge=0.0)
    refund_due: float = Field(default=0.0)


class TaxProfileResponse(TaxProfileCreate):
    """Schema for retrieved saved tax profiles."""
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
