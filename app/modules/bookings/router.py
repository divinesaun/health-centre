"""Bookings admin API endpoints for Divine Comfort Clinic.

Single-tenant mode — clinic_id is auto-resolved.
Provides slot management and appointment listing.
All endpoints require admin JWT authentication.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_clinic_id, require_admin_auth
from app.modules.bookings.schemas import (
    AppointmentResponse,
    SlotBulkCreate,
    SlotCreate,
    SlotResponse,
)
from app.modules.bookings.service import BookingService

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.get("/slots", response_model=list[SlotResponse])
async def list_available_slots(
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    service_id: Optional[str] = Query(None),
    clinic_id: str = Depends(get_clinic_id),
    _user: dict = Depends(require_admin_auth),
):
    """List available slots for Divine Comfort Clinic.

    Args:
        from_date: Optional start date filter.
        to_date: Optional end date filter.
        service_id: Optional service ID filter.
        clinic_id: Auto-resolved clinic UUID (injected).
        _user: Authenticated admin user (injected).

    Returns:
        List of available slot records.
    """
    service = BookingService()
    return service.list_available_slots(clinic_id, from_date, to_date, service_id)


@router.post("/slots", response_model=SlotResponse, status_code=201)
async def create_slot(
    data: SlotCreate,
    clinic_id: str = Depends(get_clinic_id),
    _user: dict = Depends(require_admin_auth),
):
    """Create a single time slot.

    Args:
        data: Slot creation payload.
        clinic_id: Auto-resolved clinic UUID (injected).
        _user: Authenticated admin user (injected).

    Returns:
        The created slot record.
    """
    service = BookingService()
    return service.create_slot(clinic_id, data)


@router.post("/slots/bulk", response_model=list[SlotResponse], status_code=201)
async def create_slots_bulk(
    data: SlotBulkCreate,
    clinic_id: str = Depends(get_clinic_id),
    _user: dict = Depends(require_admin_auth),
):
    """Create multiple time slots in bulk.

    Args:
        data: Bulk slot creation payload.
        clinic_id: Auto-resolved clinic UUID (injected).
        _user: Authenticated admin user (injected).

    Returns:
        List of created slot records.
    """
    service = BookingService()
    return service.create_slots_bulk(clinic_id, data)


@router.get("/appointments", response_model=list[AppointmentResponse])
async def list_appointments(
    status: Optional[str] = Query(None),
    clinic_id: str = Depends(get_clinic_id),
    _user: dict = Depends(require_admin_auth),
):
    """List appointments for Divine Comfort Clinic.

    Args:
        status: Optional status filter.
        clinic_id: Auto-resolved clinic UUID (injected).
        _user: Authenticated admin user (injected).

    Returns:
        List of appointment records.
    """
    service = BookingService()
    return service.list_appointments(clinic_id, status=status)
