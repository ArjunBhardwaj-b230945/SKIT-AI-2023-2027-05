from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from controllers.tax_record import (
    delete_stored_tax_record,
    retrieve_tax_record_by_id,
    retrieve_user_tax_records,
    retrieve_user_tax_summary,
    store_tax_record,
    update_stored_tax_record,
)
from database import get_db
from middleware.auth import get_current_user
from schemas.tax_record import (
    TaxRecordCreate,
    TaxRecordListResponse,
    TaxRecordResponse,
    TaxRecordSummaryResponse,
    TaxRecordUpdate,
)

router = APIRouter(prefix="/tax-records", tags=["Tax Data Storage & Retrieval"])


@router.post(
    "",
    response_model=TaxRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Store a new tax record",
    description="Persist tax computation, income details, and filing metadata into the database.",
)
def create_record(
    request: TaxRecordCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Store tax computation data linked to the authenticated user."""
    return store_tax_record(
        db=db,
        user_id=current_user["id"],
        payload=request,
    )


@router.get(
    "",
    response_model=TaxRecordListResponse,
    summary="Retrieve stored tax records",
    description="Fetch a paginated list of tax records for the authenticated user with optional filtering.",
)
def list_records(
    assessment_year: str | None = Query(
        default=None,
        description="Filter records by assessment year (e.g., 2024-25)",
    ),
    filing_status: str | None = Query(
        default=None,
        description="Filter by workflow status (draft, computed, filed)",
    ),
    skip: int = Query(default=0, ge=0, description="Offset for pagination"),
    limit: int = Query(default=50, ge=1, le=100, description="Number of items to return"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve multiple tax records matching query criteria."""
    return retrieve_user_tax_records(
        db=db,
        user_id=current_user["id"],
        assessment_year=assessment_year,
        filing_status=filing_status,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/summary",
    response_model=TaxRecordSummaryResponse,
    summary="Retrieve tax data summary",
    description="Get aggregated metrics including total filings, draft count, and computed tax totals.",
)
def get_records_summary(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve high-level statistical summary for user's stored records."""
    return retrieve_user_tax_summary(
        db=db,
        user_id=current_user["id"],
    )


@router.get(
    "/{record_id}",
    response_model=TaxRecordResponse,
    summary="Retrieve specific tax record",
    description="Fetch single tax record details by its unique database ID.",
)
def get_record(
    record_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve an individual stored record with user authorization check."""
    is_admin = current_user.get("role") == "admin"
    return retrieve_tax_record_by_id(
        db=db,
        record_id=record_id,
        user_id=current_user["id"],
        is_admin=is_admin,
    )


@router.put(
    "/{record_id}",
    response_model=TaxRecordResponse,
    summary="Update stored tax record",
    description="Modify calculation fields, regime, or workflow status on a saved record.",
)
def modify_record(
    record_id: int,
    request: TaxRecordUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update existing tax record with transactional integrity."""
    is_admin = current_user.get("role") == "admin"
    return update_stored_tax_record(
        db=db,
        record_id=record_id,
        user_id=current_user["id"],
        payload=request,
        is_admin=is_admin,
    )


@router.delete(
    "/{record_id}",
    summary="Delete stored tax record",
    description="Remove a persisted tax record from the database.",
)
def delete_record(
    record_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an individual stored record with authorization check."""
    is_admin = current_user.get("role") == "admin"
    return delete_stored_tax_record(
        db=db,
        record_id=record_id,
        user_id=current_user["id"],
        is_admin=is_admin,
    )
