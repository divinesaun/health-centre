"""Clinic admin API endpoints for Divine Comfort Clinic.

Single-tenant mode — all endpoints operate on the one configured clinic.
All /clinic/* endpoints require a valid Supabase JWT.
"""

from fastapi import APIRouter, Depends

from app.dependencies import get_clinic_id, require_admin_auth
from app.modules.clinics.schemas import (
    ClinicResponse,
    ClinicUpdate,
    ServiceCreate,
    ServiceResponse,
)
from app.modules.clinics.service import ClinicService

router = APIRouter(prefix="/clinic", tags=["clinic"])


@router.get("/", response_model=ClinicResponse)
async def get_clinic(
    clinic_id: str = Depends(get_clinic_id),
    _user: dict = Depends(require_admin_auth),
):
    """Get Divine Comfort Clinic details.

    Args:
        clinic_id: Auto-resolved clinic UUID (injected).
        _user: Authenticated admin user (injected).

    Returns:
        The clinic record.
    """
    service = ClinicService()
    return service.get_clinic(clinic_id)


@router.patch("/", response_model=ClinicResponse)
async def update_clinic(
    data: ClinicUpdate,
    clinic_id: str = Depends(get_clinic_id),
    _user: dict = Depends(require_admin_auth),
):
    """Update Divine Comfort Clinic details.

    Args:
        data: Clinic update payload (partial).
        clinic_id: Auto-resolved clinic UUID (injected).
        _user: Authenticated admin user (injected).

    Returns:
        The updated clinic record.
    """
    service = ClinicService()
    return service.update_clinic(clinic_id, data)


@router.get("/services", response_model=list[ServiceResponse])
async def list_services(
    active_only: bool = True,
    clinic_id: str = Depends(get_clinic_id),
    _user: dict = Depends(require_admin_auth),
):
    """List all services for Divine Comfort Clinic.

    Args:
        active_only: Filter to active services only (default True).
        clinic_id: Auto-resolved clinic UUID (injected).
        _user: Authenticated admin user (injected).

    Returns:
        List of service records.
    """
    service = ClinicService()
    return service.list_services(clinic_id, active_only=active_only)


@router.post("/services", response_model=ServiceResponse, status_code=201)
async def create_service(
    data: ServiceCreate,
    clinic_id: str = Depends(get_clinic_id),
    _user: dict = Depends(require_admin_auth),
):
    """Create a new service for Divine Comfort Clinic.

    Args:
        data: Service creation payload.
        clinic_id: Auto-resolved clinic UUID (injected).
        _user: Authenticated admin user (injected).

    Returns:
        The created service record.
    """
    service = ClinicService()
    return service.create_service(clinic_id, data)
