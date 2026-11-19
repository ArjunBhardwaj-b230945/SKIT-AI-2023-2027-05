from typing import Any, Callable
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from database import check_database_connectivity, engine
from models.user import User
from models.tax_record import TaxRecord
from models.chat import ChatMessageModel
from models.tax_profile import TaxProfileModel
from models.audit_log import AuditLogModel


def get_detailed_database_health(db: Session) -> dict[str, Any]:
    """
    Produce comprehensive database subsystem telemetry:
    - Connection connectivity and ping latency (ms)
    - Active connection pool allocations
    - Row counts across all primary application entity tables
    """
    connectivity = check_database_connectivity()

    table_counts: dict[str, int] = {}
    try:
        table_counts["users"] = db.scalar(select(func.count(User.id))) or 0
        table_counts["tax_records"] = db.scalar(select(func.count(TaxRecord.id))) or 0
        table_counts["chat_messages"] = db.scalar(select(func.count(ChatMessageModel.id))) or 0
        table_counts["tax_profiles"] = db.scalar(select(func.count(TaxProfileModel.id))) or 0
        table_counts["audit_logs"] = db.scalar(select(func.count(AuditLogModel.id))) or 0
    except Exception:
        # If any table is not yet migrated, default gracefully
        pass

    return {
        "status": "healthy" if connectivity.get("status") == "connected" else "unhealthy",
        "database": connectivity.get("status", "unknown"),
        "latency_ms": connectivity.get("latency_ms"),
        "pool": connectivity.get("pool"),
        "table_counts": table_counts,
    }


def execute_transaction_safely(
    db: Session,
    operation: Callable[[Session], Any],
) -> Any:
    """
    Execute an atomic database operation with standardized transaction error handling.
    Automatically rolls back on any operational failure.
    """
    try:
        result = operation(db)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def verify_user_cascade_status(db: Session, user_id: int) -> dict[str, int]:
    """
    Diagnostic helper to count all dependent records linked to a specific user.
    Confirms foreign key mapping prior to cascade deletions.
    """
    return {
        "tax_records_count": db.scalar(
            select(func.count(TaxRecord.id)).where(TaxRecord.user_id == user_id)
        ) or 0,
        "chat_messages_count": db.scalar(
            select(func.count(ChatMessageModel.id)).where(ChatMessageModel.user_id == user_id)
        ) or 0,
        "tax_profiles_count": db.scalar(
            select(func.count(TaxProfileModel.id)).where(TaxProfileModel.user_id == user_id)
        ) or 0,
        "audit_logs_count": db.scalar(
            select(func.count(AuditLogModel.id)).where(AuditLogModel.user_id == user_id)
        ) or 0,
    }
