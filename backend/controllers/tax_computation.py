from datetime import datetime, timezone
import json
import math
from typing import Any
import uuid

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from models.tax_profile import TaxProfileModel
from models.itr_filing import ITRFilingModel
from schemas.tax_computation import (
    DocumentReconciliationRequest,
    DocumentReconciliationResponse,
    RegimeComputationResult,
    SlabDetail,
    TaxComputationRequest,
    TaxComputationResponse,
    TaxProfileCreate,
    TaxProfileResponse,
)
from schemas.itr_filing import ITRFilingCreate


# ==============================================================================
# TAX COMPUTATION ENGINE (CBDT STATUTORY RULES & SLABS)
# ==============================================================================

def compute_new_regime(req: TaxComputationRequest) -> RegimeComputationResult:
    """
    Compute tax under New Tax Regime (Section 115BAC).
    Budget 2024 / AY 2025-26 & 2026-27 rules:
    - Standard deduction: ₹75,000 for salaried employees
    - Slabs: 0-3L (0%), 3-7L (5%), 7-10L (10%), 10-12L (15%), 12-15L (20%), >15L (30%)
    - Full rebate u/s 87A: Income up to ₹7,00,000 pays ₹0 tax
    - 4% Health & Education Cess
    """
    gross_salary = req.salary.gross_salary + req.salary.perquisites_17_2 + req.salary.profits_in_lieu_17_3
    other_inc = req.other_sources.savings_interest + req.other_sources.fixed_deposit_interest + req.other_sources.dividend_income + req.other_sources.other_income
    gross_total_income = gross_salary + other_inc

    # Standard deduction: ₹75,000 (applicable to salaried)
    std_ded = min(75000.0, gross_salary) if gross_salary > 0 else 0.0

    # Net taxable income
    taxable_income = max(0.0, gross_total_income - std_ded)

    # Slab calculation
    slabs = [
        ("0 to 3,00,000", 0.0, 300000.0, 0.0),
        ("3,00,001 to 7,00,000", 300000.0, 700000.0, 5.0),
        ("7,00,001 to 10,00,000", 700000.0, 1000000.0, 10.0),
        ("10,00,001 to 12,00,000", 1000000.0, 1200000.0, 15.0),
        ("12,00,001 to 15,00,000", 1200000.0, 1500000.0, 20.0),
        ("Above 15,00,000", 1500000.0, float("inf"), 30.0),
    ]

    slab_details: list[SlabDetail] = []
    base_tax = 0.0

    for name, low, high, rate in slabs:
        if taxable_income > low:
            taxable_in_slab = min(taxable_income, high) - low
            tax_for_slab = taxable_in_slab * (rate / 100.0)
            base_tax += tax_for_slab
            slab_details.append(SlabDetail(
                slab_name=name,
                taxable_in_slab=round(taxable_in_slab, 2),
                rate_percentage=rate,
                tax_amount=round(tax_for_slab, 2),
            ))
        else:
            slab_details.append(SlabDetail(
                slab_name=name,
                taxable_in_slab=0.0,
                rate_percentage=rate,
                tax_amount=0.0,
            ))

    # Section 87A rebate & Marginal Relief
    rebate_87a = 0.0
    marginal_relief = 0.0

    if taxable_income <= 700000.0:
        rebate_87a = base_tax
    elif taxable_income > 700000.0 and base_tax > (taxable_income - 700000.0):
        # Marginal relief: tax cannot exceed income in excess of ₹7 Lakhs
        marginal_relief = base_tax - (taxable_income - 700000.0)

    tax_after_rebate = max(0.0, base_tax - rebate_87a - marginal_relief)
    cess = round(tax_after_rebate * 0.04, 2)
    total_tax = round(tax_after_rebate + cess, 2)

    total_paid = (
        req.taxes_paid.tds_salary
        + req.taxes_paid.tds_other
        + req.taxes_paid.advance_tax
        + req.taxes_paid.self_assessment_tax
    )
    diff = round(total_paid - total_tax, 2)

    return RegimeComputationResult(
        regime_name="New Regime (115BAC)",
        gross_total_income=round(gross_total_income, 2),
        standard_deduction=round(std_ded, 2),
        hra_exemption=0.0,
        loss_from_house_property=0.0,
        total_deductions_chapter_via=0.0,
        net_taxable_income=round(taxable_income, 2),
        slab_breakdown=slab_details,
        gross_tax_liability=round(base_tax, 2),
        rebate_87a=round(rebate_87a, 2),
        marginal_relief=round(marginal_relief, 2),
        tax_after_rebate=round(tax_after_rebate, 2),
        health_and_education_cess=cess,
        total_tax_payable=total_tax,
        total_taxes_paid=round(total_paid, 2),
        balance_payable_or_refund=abs(diff),
        is_refund=diff >= 0,
    )


def compute_old_regime(req: TaxComputationRequest) -> RegimeComputationResult:
    """
    Compute tax under Old Tax Regime.
    Allows:
    - Standard deduction: ₹50,000
    - HRA exemption under Section 10(13A)
    - House property loss / Home loan interest u/s 24(b) up to ₹2,00,000
    - Chapter VI-A deductions: 80C (up to 1.5L), 80D, 80CCD(1B) (50k), 80E, 80G, 80TTA
    - Section 87A rebate for income up to ₹5,00,000 (up to ₹12,500)
    - 4% Health & Education Cess
    """
    gross_salary = req.salary.gross_salary + req.salary.perquisites_17_2 + req.salary.profits_in_lieu_17_3

    # HRA Exemption calculation
    hra_exemption = 0.0
    if req.salary.hra_received > 0 and req.salary.actual_rent_paid > 0:
        basic_approx = gross_salary * 0.50  # approximate basic salary at 50% of gross
        metro_rate = 0.50 if req.salary.is_metro_city else 0.40
        rule2a_1 = req.salary.hra_received
        rule2a_2 = basic_approx * metro_rate
        rule2a_3 = max(0.0, req.salary.actual_rent_paid - (basic_approx * 0.10))
        hra_exemption = min(rule2a_1, rule2a_2, rule2a_3)

    std_ded = min(50000.0, gross_salary) if gross_salary > 0 else 0.0
    net_salary = max(0.0, gross_salary - hra_exemption - std_ded - req.salary.professional_tax)

    # House property (Home loan interest capped at ₹2,00,000 for self occupied)
    hp_loss = min(200000.0, req.house_property.housing_loan_interest)

    # Other sources
    other_inc = req.other_sources.savings_interest + req.other_sources.fixed_deposit_interest + req.other_sources.dividend_income + req.other_sources.other_income

    gross_total_income = max(0.0, net_salary - hp_loss + other_inc)

    # Chapter VI-A deductions
    c_80c = min(150000.0, req.deductions.section_80c + req.deductions.section_80ccc + req.deductions.section_80ccd_1)
    c_80ccd1b = min(50000.0, req.deductions.section_80ccd_1b)

    # 80D Health Insurance
    self_limit = 50000.0 if req.deductions.parents_are_senior_citizens else 25000.0  # approximate
    c_80d_self = min(self_limit, req.deductions.section_80d_self_family)
    parent_limit = 50000.0 if req.deductions.parents_are_senior_citizens else 25000.0
    c_80d_parents = min(parent_limit, req.deductions.section_80d_parents)
    total_80d = c_80d_self + c_80d_parents

    # 80TTA savings deduction up to ₹10,000
    c_80tta = min(10000.0, req.other_sources.savings_interest)

    total_chapter_via = c_80c + c_80ccd1b + total_80d + req.deductions.section_80e + req.deductions.section_80g + c_80tta
    taxable_income = max(0.0, gross_total_income - total_chapter_via)

    # Slabs for regular (<60)
    slabs = [
        ("0 to 2,50,000", 0.0, 250000.0, 0.0),
        ("2,50,001 to 5,00,000", 250000.0, 500000.0, 5.0),
        ("5,00,001 to 10,00,000", 500000.0, 1000000.0, 20.0),
        ("Above 10,00,000", 1000000.0, float("inf"), 30.0),
    ]

    slab_details: list[SlabDetail] = []
    base_tax = 0.0

    for name, low, high, rate in slabs:
        if taxable_income > low:
            taxable_in_slab = min(taxable_income, high) - low
            tax_for_slab = taxable_in_slab * (rate / 100.0)
            base_tax += tax_for_slab
            slab_details.append(SlabDetail(
                slab_name=name,
                taxable_in_slab=round(taxable_in_slab, 2),
                rate_percentage=rate,
                tax_amount=round(tax_for_slab, 2),
            ))
        else:
            slab_details.append(SlabDetail(
                slab_name=name,
                taxable_in_slab=0.0,
                rate_percentage=rate,
                tax_amount=0.0,
            ))

    # Section 87A for Old Regime (up to ₹12,500 if income <= ₹5L)
    rebate_87a = min(12500.0, base_tax) if taxable_income <= 500000.0 else 0.0
    tax_after_rebate = max(0.0, base_tax - rebate_87a)
    cess = round(tax_after_rebate * 0.04, 2)
    total_tax = round(tax_after_rebate + cess, 2)

    total_paid = (
        req.taxes_paid.tds_salary
        + req.taxes_paid.tds_other
        + req.taxes_paid.advance_tax
        + req.taxes_paid.self_assessment_tax
    )
    diff = round(total_paid - total_tax, 2)

    return RegimeComputationResult(
        regime_name="Old Regime",
        gross_total_income=round(gross_total_income + hp_loss, 2),
        standard_deduction=round(std_ded, 2),
        hra_exemption=round(hra_exemption, 2),
        loss_from_house_property=round(hp_loss, 2),
        total_deductions_chapter_via=round(total_chapter_via, 2),
        net_taxable_income=round(taxable_income, 2),
        slab_breakdown=slab_details,
        gross_tax_liability=round(base_tax, 2),
        rebate_87a=round(rebate_87a, 2),
        marginal_relief=0.0,
        tax_after_rebate=round(tax_after_rebate, 2),
        health_and_education_cess=cess,
        total_tax_payable=total_tax,
        total_taxes_paid=round(total_paid, 2),
        balance_payable_or_refund=abs(diff),
        is_refund=diff >= 0,
    )


def calculate_and_compare_taxes(req: TaxComputationRequest) -> TaxComputationResponse:
    """Execute dual regime computation, compare tax liabilities, and return optimal choice."""
    new_res = compute_new_regime(req)
    old_res = compute_old_regime(req)

    if new_res.total_tax_payable < old_res.total_tax_payable:
        recommended = "New Regime (115BAC)"
        savings = round(old_res.total_tax_payable - new_res.total_tax_payable, 2)
        summary = (
            f"The **New Tax Regime** saves you **₹{savings:,.2f}** in taxes compared to the Old Regime. "
            f"Its higher standard deduction (₹75,000) and lower slab rates result in lower net liability."
        )
    elif old_res.total_tax_payable < new_res.total_tax_payable:
        recommended = "Old Regime"
        savings = round(new_res.total_tax_payable - old_res.total_tax_payable, 2)
        summary = (
            f"The **Old Tax Regime** saves you **₹{savings:,.2f}** in taxes. "
            f"Your high deductions under Section 80C, 80D, HRA, and Home Loan interest make the Old Regime optimal."
        )
    else:
        recommended = "Either (Equal)"
        savings = 0.0
        summary = "Both tax regimes result in identical tax liabilities for your income and deduction profile."

    return TaxComputationResponse(
        assessment_year=req.assessment_year,
        financial_year=req.financial_year,
        recommended_regime=recommended,
        tax_savings_with_recommended=savings,
        summary=summary,
        new_regime=new_res,
        old_regime=old_res,
        computed_at=datetime.now(timezone.utc),
    )


# ==============================================================================
# DOCUMENT RECONCILIATION CONTROLLER
# ==============================================================================

def reconcile_documents(req: DocumentReconciliationRequest) -> DocumentReconciliationResponse:
    """
    Cross-validate Form 16 vs Form 26AS vs AIS data.
    Ensures PAN consistency and verifies TDS reconciliation before ITR filing.
    """
    pan_match = req.employee_pan.strip().upper() == req.form26as_pan.strip().upper()
    tds_diff = abs(req.form16_tds - req.form26as_tds)
    tds_match = tds_diff <= 10.0  # allowable rounding variance of ₹10

    salary_diff = abs(req.form16_salary - req.ais_salary) if req.ais_salary > 0 else 0.0
    salary_match = salary_diff <= 100.0

    flags: list[str] = []
    if not pan_match:
        flags.append(f"PAN Mismatch: Form 16 PAN ({req.employee_pan}) differs from 26AS PAN ({req.form26as_pan})")

    if not tds_match:
        flags.append(f"TDS Mismatch: Form 16 reports ₹{req.form16_tds:,.2f} but Form 26AS reports ₹{req.form26as_tds:,.2f} (Variance: ₹{tds_diff:,.2f})")

    if req.ais_salary > 0 and not salary_match:
        flags.append(f"Salary Variance: Form 16 gross salary differs from AIS by ₹{salary_diff:,.2f}")

    can_proceed = pan_match and tds_match

    if can_proceed:
        summary = "All documents reconciled successfully. PAN and TDS credits match between Form 16 and 26AS."
    else:
        summary = "Reconciliation issues detected. Please review PAN or ask your employer/deductor to revise TDS return before filing."

    return DocumentReconciliationResponse(
        pan_match=pan_match,
        tds_match=tds_match,
        tds_variance=round(tds_diff, 2),
        salary_match=salary_match,
        salary_variance=round(salary_diff, 2),
        can_proceed=can_proceed,
        validation_flags=flags,
        reconciliation_summary=summary,
    )


# ==============================================================================
# TAX PROFILE & ITR FILING APPLICATION DATA PERSISTENCE
# ==============================================================================

def store_user_tax_profile(db: Session, user_id: int, payload: TaxProfileCreate) -> dict[str, Any]:
    """Persist a complete taxpayer profile snapshot to PostgreSQL."""
    profile = TaxProfileModel(
        user_id=user_id,
        assessment_year=payload.assessment_year.strip(),
        financial_year=payload.financial_year.strip(),
        pan_number=payload.pan_number.strip().upper(),
        full_name=payload.full_name.strip(),
        date_of_birth=payload.date_of_birth,
        aadhaar_last_four=payload.aadhaar_last_four,
        bank_account_number=payload.bank_account_number,
        bank_ifsc=payload.bank_ifsc.upper() if payload.bank_ifsc else None,
        address=payload.address,
        salary_income=float(payload.salary_income),
        total_deductions=float(payload.total_deductions),
        recommended_regime=payload.recommended_regime,
        total_tax=float(payload.total_tax),
        refund_due=float(payload.refund_due),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "assessment_year": profile.assessment_year,
        "financial_year": profile.financial_year,
        "pan_number": profile.pan_number,
        "full_name": profile.full_name,
        "date_of_birth": profile.date_of_birth,
        "aadhaar_last_four": profile.aadhaar_last_four,
        "bank_account_number": profile.bank_account_number,
        "bank_ifsc": profile.bank_ifsc,
        "address": profile.address,
        "salary_income": profile.salary_income,
        "total_deductions": profile.total_deductions,
        "recommended_regime": profile.recommended_regime,
        "total_tax": profile.total_tax,
        "refund_due": profile.refund_due,
        "created_at": profile.created_at.isoformat(),
        "updated_at": profile.updated_at.isoformat(),
    }


def list_user_tax_profiles(db: Session, user_id: int) -> list[dict[str, Any]]:
    """Retrieve all saved tax profiles for a user."""
    profiles = db.scalars(
        select(TaxProfileModel).where(TaxProfileModel.user_id == user_id).order_by(desc(TaxProfileModel.created_at))
    ).all()

    return [
        {
            "id": p.id,
            "user_id": p.user_id,
            "assessment_year": p.assessment_year,
            "financial_year": p.financial_year,
            "pan_number": p.pan_number,
            "full_name": p.full_name,
            "date_of_birth": p.date_of_birth,
            "aadhaar_last_four": p.aadhaar_last_four,
            "bank_account_number": p.bank_account_number,
            "bank_ifsc": p.bank_ifsc,
            "address": p.address,
            "salary_income": p.salary_income,
            "total_deductions": p.total_deductions,
            "recommended_regime": p.recommended_regime,
            "total_tax": p.total_tax,
            "refund_due": p.refund_due,
            "created_at": p.created_at.isoformat(),
            "updated_at": p.updated_at.isoformat(),
        }
        for p in profiles
    ]


def submit_final_itr_filing(db: Session, user_id: int, payload: ITRFilingCreate) -> dict[str, Any]:
    """
    Persist an officially finalized ITR filing record into the PostgreSQL database.
    Generates a unique acknowledgement number (ACK-YYYY-UUID).
    """
    clean_ay = payload.assessment_year.replace("-", "")
    ack_number = f"ACK{clean_ay}{uuid.uuid4().hex[:8].upper()}"

    filing = ITRFilingModel(
        user_id=user_id,
        acknowledgement_number=ack_number,
        assessment_year=payload.assessment_year.strip(),
        financial_year=payload.financial_year.strip(),
        itr_type=payload.itr_type,
        filing_status="submitted",
        pan_number=payload.pan_number.strip().upper(),
        gross_total_income=float(payload.gross_total_income),
        total_deductions=float(payload.total_deductions),
        taxable_income=float(payload.taxable_income),
        total_tax_payable=float(payload.total_tax_payable),
        taxes_paid=float(payload.taxes_paid),
        refund_or_payable=float(payload.refund_or_payable),
        computation_payload=json.dumps(payload.computation_payload) if payload.computation_payload else None,
        verification_mode=payload.verification_mode,
        verification_status="verified",
        submission_timestamp=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    db.add(filing)
    db.commit()
    db.refresh(filing)

    return {
        "id": filing.id,
        "user_id": filing.user_id,
        "acknowledgement_number": filing.acknowledgement_number,
        "assessment_year": filing.assessment_year,
        "financial_year": filing.financial_year,
        "itr_type": filing.itr_type,
        "filing_status": filing.filing_status,
        "pan_number": filing.pan_number,
        "gross_total_income": filing.gross_total_income,
        "total_deductions": filing.total_deductions,
        "taxable_income": filing.taxable_income,
        "total_tax_payable": filing.total_tax_payable,
        "taxes_paid": filing.taxes_paid,
        "refund_or_payable": filing.refund_or_payable,
        "computation_payload": filing.get_computation_dict(),
        "verification_mode": filing.verification_mode,
        "verification_status": filing.verification_status,
        "submission_timestamp": filing.submission_timestamp.isoformat(),
        "created_at": filing.created_at.isoformat(),
    }


def list_user_itr_filings(db: Session, user_id: int) -> list[dict[str, Any]]:
    """Retrieve all submitted ITR filings for the calling user."""
    filings = db.scalars(
        select(ITRFilingModel).where(ITRFilingModel.user_id == user_id).order_by(desc(ITRFilingModel.submission_timestamp))
    ).all()

    return [
        {
            "id": f.id,
            "user_id": f.user_id,
            "acknowledgement_number": f.acknowledgement_number,
            "assessment_year": f.assessment_year,
            "financial_year": f.financial_year,
            "itr_type": f.itr_type,
            "filing_status": f.filing_status,
            "pan_number": f.pan_number,
            "gross_total_income": f.gross_total_income,
            "total_deductions": f.total_deductions,
            "taxable_income": f.taxable_income,
            "total_tax_payable": f.total_tax_payable,
            "taxes_paid": f.taxes_paid,
            "refund_or_payable": f.refund_or_payable,
            "computation_payload": f.get_computation_dict(),
            "verification_mode": f.verification_mode,
            "verification_status": f.verification_status,
            "submission_timestamp": f.submission_timestamp.isoformat(),
            "created_at": f.created_at.isoformat(),
        }
        for f in filings
    ]
