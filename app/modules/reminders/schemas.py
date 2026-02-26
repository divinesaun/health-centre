"""Pydantic schemas for the reminders module.

Defines response models for reminder operations.
"""

from typing import Optional

from pydantic import BaseModel


class ReminderResponse(BaseModel):
    """Schema for reminder API responses.

    Attributes:
        id: Reminder UUID.
        appointment_id: Associated appointment UUID.
        clinic_id: Parent clinic UUID.
        scheduled_for: When the reminder is scheduled.
        sent_at: When the reminder was actually sent.
        status: Reminder status (pending, sent, failed).
    """

    id: str
    appointment_id: Optional[str] = None
    clinic_id: str
    scheduled_for: str
    sent_at: Optional[str] = None
    status: str
