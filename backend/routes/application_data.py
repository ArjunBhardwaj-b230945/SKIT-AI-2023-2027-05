from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from controllers.application_data import (
    export_full_application_data,
    get_application_dashboard,
)
from database import get_db
from middleware.auth import get_current_user
from schemas.itr_filing import (
    ApplicationDashboardResponse,
    ApplicationDataExportResponse,
)

router = APIRouter(prefix="/application", tags=["Application Data & Dashboard"])


@router.get(
    "/dashboard",
    response_model=ApplicationDashboardResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user application dashboard telemetry",
    description="Consolidated overview of submitted ITRs, drafts, tax computed, refund claimed, and chat activity.",
)
def get_user_dashboard(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve aggregated dashboard metrics."""
    return get_application_dashboard(
        db=db,
        user_id=current_user["id"],
    )


@router.get(
    "/export",
    response_model=ApplicationDataExportResponse,
    status_code=status.HTTP_200_OK,
    summary="Export complete user application data",
    description="Export comprehensive user portfolio including profile, tax records, and ITR filings for data portability.",
)
def export_user_data(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate complete data export for calling user."""
    return export_full_application_data(
        db=db,
        user_id=current_user["id"],
    )
