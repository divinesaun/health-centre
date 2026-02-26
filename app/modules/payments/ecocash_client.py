"""EcoCash HTTP wrapper (isolated).

This module is the ONLY place that communicates with the EcoCash API.
Implements httpx.AsyncClient with 30-second timeout, exponential backoff
on HTTP 429, and structured error handling per the spec.

API key is masked in all log output. Never raises raw HTTP errors —
always wraps in PaymentInitiationError with a clean message.
"""

import asyncio
from typing import Any

import httpx

from app.config import get_settings
from app.core.exceptions import PaymentInitiationError
from app.core.logging import get_logger

logger = get_logger(__name__)

MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 2


class EcoCashClient:
    """Isolated HTTP client for EcoCash payment API.

    All EcoCash communication goes through this class. Implements
    exponential backoff, structured error handling, and idempotent
    payment requests via sourceReference UUIDs.
    """

    def __init__(self):
        """Initialize with settings from environment."""
        self.settings = get_settings()
        self.base_url = self.settings.ECOCASH_BASE_URL
        self.api_key = self.settings.ECOCASH_API_KEY
        self.is_sandbox = self.settings.ECOCASH_SANDBOX

    async def initiate_payment(
        self,
        customer_msisdn: str,
        amount: float,
        reason: str,
        currency: str = "USD",
        source_reference: str = "",
    ) -> dict[str, Any]:
        """Initiate a C2B payment via EcoCash.

        Sends a payment request to the patient's phone. The patient must
        enter their EcoCash PIN to confirm. Uses exponential backoff on 429.

        Args:
            customer_msisdn: Patient phone number without + prefix (e.g. '263774222475').
            amount: Payment amount.
            reason: Human-readable payment reason.
            currency: Currency code (default 'USD').
            source_reference: UUID for idempotency (from payments table).

        Returns:
            The EcoCash API response dict on success.

        Raises:
            PaymentInitiationError: On any failure, with a clean message.
        """
        # Strip + prefix if present
        clean_msisdn = customer_msisdn.lstrip("+")

        # Determine endpoint
        endpoint = "/api/v2/payment/instant/c2b/sandbox" if self.is_sandbox else "/api/v2/payment/instant/c2b"
        url = f"{self.base_url}{endpoint}"

        payload = {
            "customerMsisdn": clean_msisdn,
            "amount": amount,
            "reason": reason,
            "currency": currency,
            "sourceReference": source_reference,
        }

        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }

        # Log request (mask API key)
        logger.debug(
            "ecocash_request",
            url=url,
            customer_msisdn=clean_msisdn,
            amount=amount,
            currency=currency,
            source_reference=source_reference,
            api_key="[REDACTED]",
        )

        last_error: Exception | None = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(url, json=payload, headers=headers)

                # Log response (mask sensitive data)
                logger.debug(
                    "ecocash_response",
                    status_code=response.status_code,
                    attempt=attempt + 1,
                    source_reference=source_reference,
                )

                return self._handle_response(response, source_reference)

            except PaymentInitiationError:
                raise

            except httpx.TimeoutException as exc:
                last_error = exc
                logger.warning(
                    "ecocash_timeout",
                    attempt=attempt + 1,
                    source_reference=source_reference,
                )
                if attempt < MAX_RETRIES:
                    wait = BACKOFF_BASE_SECONDS * (2 ** attempt)
                    await asyncio.sleep(wait)
                    continue

            except Exception as exc:
                last_error = exc
                logger.error(
                    "ecocash_unexpected_error",
                    error=str(exc),
                    attempt=attempt + 1,
                    source_reference=source_reference,
                )
                break

        raise PaymentInitiationError(
            message="Payment service is temporarily unavailable. Please try again.",
            context={
                "source_reference": source_reference,
                "last_error": str(last_error) if last_error else "unknown",
            },
        )

    def _handle_response(self, response: httpx.Response, source_reference: str) -> dict:
        """Handle an EcoCash HTTP response according to the spec.

        Args:
            response: The httpx Response object.
            source_reference: The payment source reference UUID.

        Returns:
            The parsed response body on success.

        Raises:
            PaymentInitiationError: On error responses, with appropriate message.
        """
        status = response.status_code

        # 200 OK — Mark payment 'processing', await confirmation
        if status == 200:
            try:
                return response.json()
            except Exception:
                return {"status": "processing"}

        # 400 Bad Request — Invalid number
        if status == 400:
            raise PaymentInitiationError(
                message="Invalid phone number. Please check and try again.",
                context={
                    "source_reference": source_reference,
                    "http_status": 400,
                },
            )

        # 401/403 — Auth failure, alert admin
        if status in (401, 403):
            logger.error(
                "ecocash_auth_failure",
                http_status=status,
                source_reference=source_reference,
            )
            raise PaymentInitiationError(
                message="Payment service configuration error. Please contact the clinic.",
                context={
                    "source_reference": source_reference,
                    "http_status": status,
                    "alert_admin": True,
                },
            )

        # 402 Request Failed
        if status == 402:
            raise PaymentInitiationError(
                message="Payment could not be processed. Please try again.",
                context={
                    "source_reference": source_reference,
                    "http_status": 402,
                },
            )

        # 409 Conflict — Check if existing payment is already paid
        if status == 409:
            logger.info(
                "ecocash_duplicate_payment",
                source_reference=source_reference,
            )
            raise PaymentInitiationError(
                message="duplicate_payment",
                context={
                    "source_reference": source_reference,
                    "http_status": 409,
                    "is_duplicate": True,
                },
            )

        # 429 Too Many Requests — Retry with exponential backoff
        if status == 429:
            raise httpx.TimeoutException(
                message="Rate limited by EcoCash API"
            )

        # 500+ Server Error
        if status >= 500:
            raise PaymentInitiationError(
                message="EcoCash is temporarily unavailable. Please try again shortly.",
                context={
                    "source_reference": source_reference,
                    "http_status": status,
                },
            )

        # Any other status
        raise PaymentInitiationError(
            message="An unexpected payment error occurred. Please try again.",
            context={
                "source_reference": source_reference,
                "http_status": status,
            },
        )
