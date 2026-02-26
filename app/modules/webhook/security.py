"""Twilio signature validation for webhook security.

Every inbound webhook request is validated using Twilio's RequestValidator
with per-clinic auth tokens. Invalid signatures result in HTTP 403.
"""

from fastapi import Request
from twilio.request_validator import RequestValidator

from app.config import get_settings
from app.core.exceptions import InvalidTwilioSignatureError
from app.core.logging import get_logger

logger = get_logger(__name__)


async def validate_twilio_signature(
    request: Request,
    form_data: dict,
    clinic_auth_token: str | None = None,
) -> None:
    """Validate the Twilio HMAC signature on an inbound webhook request.

    Uses per-clinic auth tokens when available, falls back to the global
    TWILIO_AUTH_TOKEN from settings.

    Args:
        request: The incoming FastAPI request.
        form_data: The parsed form data from the request body.
        clinic_auth_token: Optional per-clinic Twilio auth token.

    Raises:
        InvalidTwilioSignatureError: If the signature is invalid or missing.
    """
    settings = get_settings()

    # Use per-clinic token if available, otherwise use global token
    auth_token = clinic_auth_token or settings.TWILIO_AUTH_TOKEN
    validator = RequestValidator(auth_token)

    # Reconstruct the full URL as Twilio sees it
    # In production behind Vercel, use the VERCEL_URL
    url = str(request.url)
    if settings.APP_ENV == "production" and settings.VERCEL_URL:
        url = f"{settings.VERCEL_URL}{request.url.path}"

    # Get the X-Twilio-Signature header
    signature = request.headers.get("X-Twilio-Signature", "")

    if not signature:
        client_ip = request.client.host if request.client else "unknown"
        logger.warning(
            "twilio_signature_missing",
            source_ip=client_ip,
            path=str(request.url.path),
        )
        raise InvalidTwilioSignatureError(
            message="Missing X-Twilio-Signature header",
            context={"source_ip": client_ip},
        )

    is_valid = validator.validate(url, form_data, signature)

    if not is_valid:
        client_ip = request.client.host if request.client else "unknown"
        logger.warning(
            "twilio_signature_invalid",
            source_ip=client_ip,
            path=str(request.url.path),
        )
        raise InvalidTwilioSignatureError(
            message="Invalid Twilio signature",
            context={"source_ip": client_ip},
        )

    logger.debug("twilio_signature_valid", path=str(request.url.path))
