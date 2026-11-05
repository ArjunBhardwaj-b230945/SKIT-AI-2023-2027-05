from datetime import datetime, timezone
import json
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.tax_record import TaxRecord
from schemas.tax_record import (
    TaxRecordCreate,
    TaxRecordUpdate,
)


def serialize_tax_record(record: TaxRecord) -> dict[str, Any]:
    """Serialize a TaxRecord ORM instance into a JSON-compatible dictionary."""
    comp_details = record.get_computation_dict()

    return {
        "id": record.id,
        "user_id": record.user_id,
        "pan_number": record.pan_number,
        "financial_year": record.financial_year,
        "assessment_year": record.assessment_year,
        "tax_regime": record.tax_regime,
        "filing_status": record.filing_status,
        "gross_total_income": record.gross_total_income,
        "total_deductions": record.total_deductions,
        "taxable_income": record.taxable_income,
        "total_tax_payable": record.total_tax_payable,
        "computation_details": comp_details,
        "notes": record.notes,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


def store_tax_record(
    db: Session,
    user_id: int,
    payload: TaxRecordCreate,
) -> dict[str, Any]:
    """
    Persist a new tax computation or filing record into the PostgreSQL database.
    Performs data normalization, JSON serialization, and transactional commit.
    """
    comp_json = (
        json.dumps(payload.computation_details)
        if payload.computation_details is not None
        else None
    )

    record = TaxRecord(
        user_id=user_id,
        pan_number=payload.pan_number.strip().upper(),
        financial_year=payload.financial_year.strip(),
        assessment_year=payload.assessment_year.strip(),
        tax_regime=payload.tax_regime.value if hasattr(payload.tax_regime, "value") else str(payload.tax_regime),
        filing_status=payload.filing_status.value if hasattr(payload.filing_status, "value") else str(payload.filing_status),
        gross_total_income=float(payload.gross_total_income),
        total_deductions=float(payload.total_deductions),
        taxable_income=float(payload.taxable_income),
        total_tax_payable=float(payload.total_tax_payable),
        computation_details=comp_json,
        notes=payload.notes,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    db.add(record)
    try:
        db.commit()
        db.refresh(record)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to persist tax record: {str(exc)}",
        ) from exc

    return serialize_tax_record(record)


def retrieve_tax_record_by_id(
    db: Session,
    record_id: int,
    user_id: int,
    is_admin: bool = False,
) -> dict[str, Any]:
    """
    Retrieve a specific tax record by ID, enforcing user data isolation.
    Regular users can only access their own records; admins can inspect all.
    """
    record = db.get(TaxRecord, record_id)

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tax record with ID {record_id} not found",
        )

    if record.user_id != user_id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this tax record",
        )

    return serialize_tax_record(record)


def retrieve_user_tax_records(
    db: Session,
    user_id: int,
    assessment_year: str | None = None,
    filing_status: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """
    Retrieve a paginated and filtered collection of tax records for a given user.
    Supports filtering by assessment year and filing workflow status.
    """
    query = select(TaxRecord).where(TaxRecord.user_id == user_id)

    if assessment_year:
        query = query.where(TaxRecord.assessment_year == assessment_year.strip())

    if filing_status:
        query = query.where(TaxRecord.filing_status == filing_status.strip().lower())

    count_query = select(func.count()).select_from(query.subquery())
    total_count = db.scalar(count_query) or 0

    paginated_query = (
        query.order_by(TaxRecord.created_at.desc())
        .offset(skip)
        .limit(limit)
    )

    records = db.scalars(paginated_query).all()

    return {
        "total": total_count,
        "page": (skip // limit) + 1 if limit > 0 else 1,
        "limit": limit,
        "records": [serialize_tax_record(rec) for rec in records],
    }


def update_stored_tax_record(
    db: Session,
    record_id: int,
    user_id: int,
    payload: TaxRecordUpdate,
    is_admin: bool = False,
) -> dict[str, Any]:
    """
    Update selected fields of an existing persisted tax record.
    Preserves data integrity with transactional commit and automatic timestamp update.
    """
    record = db.get(TaxRecord, record_id)

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tax record with ID {record_id} not found",
        )

    if record.user_id != user_id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this tax record",
        )

    if payload.pan_number is not None:
        record.pan_number = payload.pan_number.strip().upper()
    if payload.financial_year is not None:
        record.financial_year = payload.financial_year.strip()
    if payload.assessment_year is not None:
        record.assessment_year = payload.assessment_year.strip()
    if payload.tax_regime is not None:
        record.tax_regime = payload.tax_regime.value if hasattr(payload.tax_regime, "value") else str(payload.tax_regime)
    if payload.filing_status is not None:
        record.filing_status = payload.filing_status.value if hasattr(payload.filing_status, "value") else str(payload.filing_status)
    if payload.gross_total_income is not None:
        record.gross_total_income = float(payload.gross_total_income)
    if payload.total_deductions is not None:
        record.total_deductions = float(payload.total_deductions)
    if payload.taxable_income is not None:
        record.taxable_income = float(payload.taxable_income)
    if payload.total_tax_payable is not None:
        record.total_tax_payable = float(payload.total_tax_payable)
    if payload.computation_details is not None:
        record.computation_details = json.dumps(payload.computation_details)
    if payload.notes is not None:
        record.notes = payload.notes

    record.updated_at = datetime.now(timezone.utc)

    try:
        db.commit()
        db.refresh(record)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update tax record: {str(exc)}",
        ) from exc

    return serialize_tax_record(record)


def delete_stored_tax_record(
    db: Session,
    record_id: int,
    user_id: int,
    is_admin: bool = False,
) -> dict[str, Any]:
    """
    Remove a stored tax record from the database.
    Validates ownership before executing the delete.
    """
    record = db.get(TaxRecord, record_id)

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tax record with ID {record_id} not found",
        )

    if record.user_id != user_id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this tax record",
        )

    db.delete(record)
    db.commit()

    return {
        "message": "Tax record deleted successfully",
        "id": record_id,
    }


def retrieve_user_tax_summary(
    db: Session,
    user_id: int,
) -> dict[str, Any]:
    """
    Compute aggregate storage metrics across all tax records for the authenticated user.
    Returns status counts, total tax sum, and distinct assessment years.
    """
    records = db.scalars(
        select(TaxRecord).where(TaxRecord.user_id == user_id)
    ).all()

    total_records = len(records)
    draft_count = sum(1 for r in records if r.filing_status == "draft")
    computed_count = sum(1 for r in records if r.filing_status == "computed")
    filed_count = sum(1 for r in records if r.filing_status == "filed")
    total_tax_sum = sum(r.total_tax_payable for r in records)
    assessment_years = sorted(list(set(r.assessment_year for r in records)))

    return {
        "total_records": total_records,
        "draft_count": draft_count,
        "computed_count": computed_count,
        "filed_count": filed_count,
        "total_tax_payable_sum": round(total_tax_sum, 2),
        "recorded_assessment_years": assessment_years,
    }
