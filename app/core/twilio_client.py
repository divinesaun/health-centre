"""Twilio WhatsApp messaging singleton.

Provides a single function `send_whatsapp_message()` that all modules
use to send messages to patients. Never instantiate Twilio clients elsewhere.
"""

from twilio.rest import Client

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_twilio_client: Client | None = None


def _get_twilio_client() -> Client:
    """Return the singleton Twilio client instance.

    Returns:
        The shared Twilio REST client.
    """
    global _twilio_client
    if _twilio_client is None:
        settings = get_settings()
        _twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    return _twilio_client


async def send_whatsapp_message(
    to: str,
    body: str,
    from_number: str | None = None,
    clinic_id: str | None = None,
) -> str | None:
    """Send a WhatsApp message via Twilio.

    Args:
        to: Recipient WhatsApp number in format 'whatsapp:+263...'
        body: Message body text.
        from_number: Sender WhatsApp number. Defaults to TWILIO_WHATSAPP_NUMBER.
        clinic_id: Clinic ID for logging context.

    Returns:
        The Twilio message SID on success, None on failure.

    Raises:
        No exceptions are raised — errors are caught and logged.
    """
    settings = get_settings()
    sender = from_number or settings.TWILIO_WHATSAPP_NUMBER

    try:
        client = _get_twilio_client()
        message = client.messages.create(
            body=body,
            from_=sender,
            to=to,
        )

        logger.info(
            "whatsapp_message_sent",
            clinic_id=clinic_id,
            to=to,
            message_sid=message.sid,
        )
        return message.sid

    except Exception as exc:
        logger.error(
            "whatsapp_message_failed",
            clinic_id=clinic_id,
            to=to,
            error=str(exc),
        )
        return None
