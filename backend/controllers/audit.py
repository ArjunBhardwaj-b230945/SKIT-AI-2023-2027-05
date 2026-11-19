from datetime import datetime, timezone
import json
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from models.audit_log import AuditLogModel
from schemas.audit_log import AuditLogResponse


def serialize_audit_log(log: AuditLogModel) -> dict[str, Any]:
    """Serialize AuditLog ORM instance to a dictionary."""
    return {
        "id": log.id,
        "user_id": log.user_id,
        "action": log.action,
        "entity_type": log.entity_type,
        "entity_id": log.entity_id,
        "details": log.details,
        "ip_address": log.ip_address,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    }


def record_audit_event(
    db: Session,
    action: str,
    entity_type: str,
    user_id: int | None = None,
    entity_id: int | None = None,
    details: dict[str, Any] | str | None = None,
    ip_address: str | None = None,
) -> AuditLogModel | None:
    """
    Persist an audit log entry for database operations.
    Silently catches transient logging errors so primary business transactions are never aborted.
    """
    serialized_details = (
        json.dumps(details)
        if isinstance(details, dict)
        else details
    )

    log_entry = AuditLogModel(
        user_id=user_id,
        action=action.strip().upper(),
        entity_type=entity_type.strip(),
        entity_id=entity_id,
        details=serialized_details,
        ip_address=ip_address,
        created_at=datetime.now(timezone.utc),
    )

    try:
        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)
        return log_entry
    except Exception:
        db.rollback()
        return None


def retrieve_user_audit_logs(
    db: Session,
    user_id: int,
    skip: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """Fetch paginated audit entries initiated by a specific user."""
    query = (
        select(AuditLogModel)
        .where(AuditLogModel.user_id == user_id)
        .order_by(desc(AuditLogModel.created_at))
    )

    count_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(count_query) or 0

    logs = db.scalars(query.offset(skip).limit(limit)).all()

    return {
        "total": total,
        "page": (skip // limit) + 1 if limit > 0 else 1,
        "limit": limit,
        "logs": [serialize_audit_log(entry) for entry in logs],
    }


def retrieve_system_audit_logs(
    db: Session,
    action: str | None = None,
    entity_type: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """Administrative access to system-wide database transaction audit records."""
    query = select(AuditLogModel)

    if action:
        query = query.where(AuditLogModel.action == action.strip().upper())
    if entity_type:
        query = query.where(AuditLogModel.entity_type == entity_type.strip())

    count_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(count_query) or 0

    logs = db.scalars(
        query.order_by(desc(AuditLogModel.created_at))
        .offset(skip)
        .limit(limit)
    ).all()

    return {
        "total": total,
        "page": (skip // limit) + 1 if limit > 0 else 1,
        "limit": limit,
        "logs": [serialize_audit_log(entry) for entry in logs],
    }
