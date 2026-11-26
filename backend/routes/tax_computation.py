from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from controllers.tax_computation import (
    calculate_and_compare_taxes,
    list_user_itr_filings,
    list_user_tax_profiles,
    reconcile_documents,
    store_user_tax_profile,
    submit_final_itr_filing,
)
from database import get_db
from middleware.auth import get_current_user
from schemas.tax_computation import (
    DocumentReconciliationRequest,
    DocumentReconciliationResponse,
    TaxComputationRequest,
    TaxComputationResponse,
    TaxProfileCreate,
    TaxProfileResponse,
)
from schemas.itr_filing import (
    ITRFilingCreate,
    ITRFilingResponse,
)

router = APIRouter(tags=["Tax Computation & ITR Filing Pipeline"])


@router.post(
    "/tax/compute",
    response_model=TaxComputationResponse,
    status_code=status.HTTP_200_OK,
    summary="Compute and compare tax regimes",
    description="Calculates taxes for both Old and New regimes, applies statutory deductions, and returns the optimal choice.",
)
def compute_taxes(
    request: TaxComputationRequest,
    _: dict = Depends(get_current_user),
):
    """Execute dual regime calculation and optimal regime recommendation."""
    return calculate_and_compare_taxes(request)


@router.post(
    "/tax/reconcile-documents",
    response_model=DocumentReconciliationResponse,
    status_code=status.HTTP_200_OK,
    summary="Reconcile Form 16 vs 26AS vs AIS",
    description="Cross-validates TDS credits and PAN consistency across tax documents.",
)
def reconcile_tax_documents(
    request: DocumentReconciliationRequest,
    _: dict = Depends(get_current_user),
):
    """Validate TDS and PAN across Form 16 and 26AS."""
    return reconcile_documents(request)


@router.post(
    "/tax/profiles",
    response_model=TaxProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save taxpayer profile snapshot",
    description="Stores taxpayer identification, bank info, and verified tax computation summary.",
)
def create_tax_profile(
    request: TaxProfileCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Persist user tax profile to database."""
    return store_user_tax_profile(
        db=db,
        user_id=current_user["id"],
        payload=request,
    )


@router.get(
    "/tax/profiles",
    response_model=list[TaxProfileResponse],
    summary="List saved taxpayer profiles",
    description="Retrieve all saved taxpayer profiles for the authenticated user.",
)
def get_tax_profiles(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve saved tax profiles for user."""
    return list_user_tax_profiles(
        db=db,
        user_id=current_user["id"],
    )


@router.post(
    "/itr/submit",
    response_model=ITRFilingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit and finalize ITR filing",
    description="Persists final ITR filing data and generates an official acknowledgement number.",
)
def submit_itr(
    request: ITRFilingCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit finalized ITR to the database."""
    return submit_final_itr_filing(
        db=db,
        user_id=current_user["id"],
        payload=request,
    )


@router.get(
    "/itr/filings",
    response_model=list[ITRFilingResponse],
    summary="List all submitted ITR filings",
    description="Fetch all officially submitted ITR filing records for the current user.",
)
def get_itr_filings(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List submitted ITR records."""
    return list_user_itr_filings(
        db=db,
        user_id=current_user["id"],
    )
