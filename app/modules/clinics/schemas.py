"""Pydantic schemas for the clinics module.

Defines request/response models for clinic CRUD operations.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ClinicCreate(BaseModel):
    """Schema for creating a new clinic.

    Attributes:
        name: The clinic display name.
        whatsapp_number: The clinic's WhatsApp number (without whatsapp: prefix).
        twilio_account_sid: Optional Twilio account SID for per-clinic tokens.
        twilio_auth_token: Optional Twilio auth token.
        timezone: Timezone string, defaults to Africa/Harare.
        subscription_tier: Subscription tier, defaults to 'basic'.
        greeting_message: Optional custom greeting message.
    """

    name: str = Field(..., min_length=1, max_length=255)
    whatsapp_number: str = Field(..., min_length=10, max_length=20)
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    timezone: str = "Africa/Harare"
    subscription_tier: str = "basic"
    greeting_message: Optional[str] = None


class ClinicUpdate(BaseModel):
    """Schema for updating an existing clinic.

    All fields are optional — only provided fields are updated.

    Attributes:
        name: The clinic display name.
        whatsapp_number: The clinic's WhatsApp number.
        twilio_account_sid: Twilio account SID.
        twilio_auth_token: Twilio auth token.
        timezone: Timezone string.
        is_active: Whether the clinic is active.
        subscription_tier: Subscription tier.
        greeting_message: Custom greeting message.
    """

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    whatsapp_number: Optional[str] = Field(None, min_length=10, max_length=20)
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    timezone: Optional[str] = None
    is_active: Optional[bool] = None
    subscription_tier: Optional[str] = None
    greeting_message: Optional[str] = None


class ClinicResponse(BaseModel):
    """Schema for clinic API responses.

    Attributes:
        id: Clinic UUID.
        name: The clinic display name.
        whatsapp_number: The clinic's WhatsApp number.
        timezone: Timezone string.
        is_active: Whether the clinic is active.
        subscription_tier: Subscription tier.
        greeting_message: Custom greeting message.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
    """

    id: str
    name: str
    whatsapp_number: str
    timezone: str
    is_active: bool
    subscription_tier: str
    greeting_message: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ServiceCreate(BaseModel):
    """Schema for creating a new service for a clinic.

    Attributes:
        name: The service display name.
        duration_minutes: Duration of the service in minutes.
        booking_fee_usd: Booking fee in USD.
        display_order: Display order in the service list.
    """

    name: str = Field(..., min_length=1, max_length=255)
    duration_minutes: int = Field(default=30, ge=5, le=480)
    booking_fee_usd: float = Field(default=0.00, ge=0)
    display_order: int = Field(default=0, ge=0)


class ServiceResponse(BaseModel):
    """Schema for service API responses.

    Attributes:
        id: Service UUID.
        clinic_id: Parent clinic UUID.
        name: The service display name.
        duration_minutes: Duration in minutes.
        booking_fee_usd: Booking fee in USD.
        is_active: Whether the service is active.
        display_order: Display order.
    """

    id: str
    clinic_id: str
    name: str
    duration_minutes: int
    booking_fee_usd: float
    is_active: bool
    display_order: int
