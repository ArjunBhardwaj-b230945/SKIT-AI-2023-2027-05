from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from models.user import User
from models.tax_record import TaxRecord
from models.chat import ChatMessageModel
from models.tax_profile import TaxProfileModel
from models.itr_filing import ITRFilingModel
from controllers.tax_record import serialize_tax_record


def get_application_dashboard(db: Session, user_id: int) -> dict[str, Any]:
    """
    Produce unified application dashboard telemetry for the frontend UI.
    Aggregates filing statistics, tax computed, refund sums, and chat activity.
    """
    user = db.get(User, user_id)
    email = user.email if user else ""

    # ITR Filings stats
    filings = db.scalars(
        select(ITRFilingModel).where(ITRFilingModel.user_id == user_id)
    ).all()
    total_filings = len(filings)
    total_refund = sum(f.refund_or_payable for f in filings if f.refund_or_payable > 0)
    latest_ack = filings[0].acknowledgement_number if filings else None

    # Draft records stats
    tax_records = db.scalars(
        select(TaxRecord).where(TaxRecord.user_id == user_id)
    ).all()
    drafts = sum(1 for r in tax_records if r.filing_status == "draft")
    total_tax = sum(r.total_tax_payable for r in tax_records)

    # Chat sessions
    chat_sessions_count = db.scalar(
        select(func.count(func.distinct(ChatMessageModel.session_id))).where(
            ChatMessageModel.user_id == user_id
        )
    ) or 0

    latest_time = None
    if filings:
        latest_time = filings[0].submission_timestamp
    elif tax_records:
        latest_time = tax_records[0].created_at

    return {
        "user_id": user_id,
        "email": email,
        "total_filings_submitted": total_filings,
        "draft_records_count": drafts,
        "total_tax_computed": round(total_tax, 2),
        "total_refund_claimed": round(total_refund, 2),
        "active_chat_sessions": chat_sessions_count,
        "latest_acknowledgement_number": latest_ack,
        "last_activity_timestamp": latest_time.isoformat() if latest_time else None,
    }


def export_full_application_data(db: Session, user_id: int) -> dict[str, Any]:
    """
    Export complete data portfolio for the authenticated user:
    - User account credentials metadata
    - Personal tax profiles
    - Persisted computation tax records
    - Formally submitted ITR filings
    - Total chat interactions count
    """
    user = db.get(User, user_id)
    user_data = {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "created_at": user.created_at.isoformat(),
    } if user else {}

    profiles = db.scalars(
        select(TaxProfileModel).where(TaxProfileModel.user_id == user_id)
    ).all()
    profiles_data = [
        {
            "id": p.id,
            "assessment_year": p.assessment_year,
            "financial_year": p.financial_year,
            "pan_number": p.pan_number,
            "full_name": p.full_name,
            "salary_income": p.salary_income,
            "total_deductions": p.total_deductions,
            "recommended_regime": p.recommended_regime,
            "total_tax": p.total_tax,
            "refund_due": p.refund_due,
            "created_at": p.created_at.isoformat(),
        }
        for p in profiles
    ]

    records = db.scalars(
        select(TaxRecord).where(TaxRecord.user_id == user_id)
    ).all()
    records_data = [serialize_tax_record(r) for r in records]

    filings = db.scalars(
        select(ITRFilingModel).where(ITRFilingModel.user_id == user_id)
    ).all()
    filings_data = [
        {
            "id": f.id,
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
            "submission_timestamp": f.submission_timestamp.isoformat(),
        }
        for f in filings
    ]

    chat_count = db.scalar(
        select(func.count(ChatMessageModel.id)).where(ChatMessageModel.user_id == user_id)
    ) or 0

    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "user": user_data,
        "profiles": profiles_data,
        "tax_records": records_data,
        "itr_filings": filings_data,
        "chat_messages_count": chat_count,
    }
