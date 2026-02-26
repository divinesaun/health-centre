"""Pydantic schemas for the bookings module.

Defines request/response models for appointment and slot operations.
"""

from datetime import date, time
from typing import Optional

from pydantic import BaseModel, Field


class SlotCreate(BaseModel):
    """Schema for creating a new time slot.

    Attributes:
        practitioner_id: Optional practitioner UUID.
        service_id: Optional service UUID.
        slot_date: The date of the slot.
        start_time: The start time of the slot.
        end_time: The end time of the slot.
    """

    practitioner_id: Optional[str] = None
    service_id: Optional[str] = None
    slot_date: date
    start_time: time
    end_time: time


class SlotResponse(BaseModel):
    """Schema for slot API responses.

    Attributes:
        id: Slot UUID.
        clinic_id: Parent clinic UUID.
        practitioner_id: Practitioner UUID.
        service_id: Service UUID.
        slot_date: The date of the slot.
        start_time: The start time string.
        end_time: The end time string.
        status: Slot status (available, locked, booked, cancelled).
    """

    id: str
    clinic_id: str
    practitioner_id: Optional[str] = None
    service_id: Optional[str] = None
    slot_date: str
    start_time: str
    end_time: str
    status: str


class AppointmentResponse(BaseModel):
    """Schema for appointment API responses.

    Attributes:
        id: Appointment UUID.
        clinic_id: Parent clinic UUID.
        patient_id: Patient UUID.
        slot_id: Slot UUID.
        service_id: Service UUID.
        practitioner_id: Practitioner UUID.
        status: Appointment status.
        booking_reference: Unique booking reference code.
        notes: Optional appointment notes.
        created_at: Creation timestamp.
        confirmed_at: Confirmation timestamp.
    """

    id: str
    clinic_id: str
    patient_id: Optional[str] = None
    slot_id: Optional[str] = None
    service_id: Optional[str] = None
    practitioner_id: Optional[str] = None
    status: str
    booking_reference: str
    notes: Optional[str] = None
    created_at: Optional[str] = None
    confirmed_at: Optional[str] = None


class SlotBulkCreate(BaseModel):
    """Schema for bulk slot creation.

    Attributes:
        practitioner_id: Optional practitioner UUID.
        service_id: Optional service UUID.
        slot_date: The date for all slots.
        slots: List of (start_time, end_time) pairs.
    """

    practitioner_id: Optional[str] = None
    service_id: Optional[str] = None
    slot_date: date
    slots: list[dict] = Field(..., min_length=1)
