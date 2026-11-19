from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class AuditLogBase(BaseModel):
    """Base schema for database operation audit events."""
    action: str = Field(..., description="Action name, e.g. USER_LOGIN, RECORD_CREATE")
    entity_type: str = Field(..., description="Target model/entity name")
    entity_id: int | None = Field(default=None, description="Primary key of modified record")
    details: str | None = Field(default=None, description="JSON description of mutation")
    ip_address: str | None = Field(default=None, description="Caller client IP address")


class AuditLogResponse(AuditLogBase):
    """Schema for retrieved audit log entries."""
    id: int
    user_id: int | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogListResponse(BaseModel):
    """Paginated collection of audit log entries."""
    total: int
    page: int
    limit: int
    logs: list[AuditLogResponse]


class DatabasePoolDiagnostics(BaseModel):
    """Diagnostics on database connection pool utilization."""
    size: int
    checked_in: int
    checked_out: int
    overflow: int


class DatabaseHealthResponse(BaseModel):
    """Detailed health and performance status of the database subsystem."""
    status: str
    database: str
    latency_ms: float | None = None
    pool: DatabasePoolDiagnostics | None = None
    table_counts: dict[str, int] = Field(default_factory=dict)
