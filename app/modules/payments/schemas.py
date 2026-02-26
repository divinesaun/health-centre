"""Pydantic schemas for the payments module.

Defines request/response models for payment operations and EcoCash callbacks.
"""

from typing import Optional

from pydantic import BaseModel


class PaymentResponse(BaseModel):
    """Schema for payment API responses.

    Attributes:
        id: Payment UUID.
        clinic_id: Parent clinic UUID.
        appointment_id: Associated appointment UUID.
        amount_usd: Payment amount in USD.
        currency: Currency code.
        provider: Payment provider name.
        source_reference: Idempotency UUID for EcoCash.
        customer_msisdn: Patient phone number.
        status: Payment status.
        failure_reason: Reason for failure, if any.
        initiated_at: Initiation timestamp.
        confirmed_at: Confirmation timestamp.
        expires_at: Expiry timestamp.
    """

    id: str
    clinic_id: str
    appointment_id: Optional[str] = None
    amount_usd: float
    currency: str = "USD"
    provider: str = "ecocash"
    source_reference: Optional[str] = None
    customer_msisdn: Optional[str] = None
    status: str
    failure_reason: Optional[str] = None
    initiated_at: Optional[str] = None
    confirmed_at: Optional[str] = None
    expires_at: Optional[str] = None


class EcoCashCallbackPayload(BaseModel):
    """Schema for an EcoCash payment callback/notification.

    The exact shape depends on EcoCash API documentation.
    This model captures the common fields.

    Attributes:
        sourceReference: The UUID sent in the original payment request.
        status: Payment status from EcoCash (e.g. 'COMPLETED', 'FAILED').
        transactionId: EcoCash transaction ID.
        amount: The payment amount.
        currency: Currency code.
        customerMsisdn: The customer phone number.
    """

    sourceReference: str
    status: str
    transactionId: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = "USD"
    customerMsisdn: Optional[str] = None
