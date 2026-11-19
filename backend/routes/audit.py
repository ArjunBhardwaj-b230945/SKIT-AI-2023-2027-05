from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from controllers.audit import (
    retrieve_system_audit_logs,
    retrieve_user_audit_logs,
)
from controllers.database_ops import get_detailed_database_health
from database import get_db
from middleware.auth import get_current_admin, get_current_user
from schemas.audit_log import (
    AuditLogListResponse,
    DatabaseHealthResponse,
)

router = APIRouter(tags=["Database & Audit Diagnostics"])


@router.get(
    "/audit/my-logs",
    response_model=AuditLogListResponse,
    summary="Retrieve user activity audit log",
    description="Fetch a chronological history of state mutations and events for the current user.",
)
def get_my_audit_logs(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve audit events initiated by the calling user."""
    return retrieve_user_audit_logs(
        db=db,
        user_id=current_user["id"],
        skip=skip,
        limit=limit,
    )


@router.get(
    "/audit/system-logs",
    response_model=AuditLogListResponse,
    summary="Retrieve system-wide database audit logs (Admin only)",
    description="Administrative query interface for database mutations across all users and models.",
)
def get_system_audit_logs(
    action: str | None = Query(default=None, description="Filter by action name"),
    entity_type: str | None = Query(default=None, description="Filter by target entity"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    _: dict = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Fetch system-wide database transaction traces."""
    return retrieve_system_audit_logs(
        db=db,
        action=action,
        entity_type=entity_type,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/database/diagnostics",
    response_model=DatabaseHealthResponse,
    summary="Get detailed database performance & pool health",
    description="Telemetry on PostgreSQL connection pool allocations, latency, and entity row counts.",
)
def get_database_diagnostics(
    db: Session = Depends(get_db),
):
    """Telemetry diagnostic endpoint for database connection pool and entity tables."""
    return get_detailed_database_health(db)
