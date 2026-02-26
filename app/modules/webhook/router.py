"""Twilio webhook endpoint.

POST /webhook/twilio receives inbound WhatsApp messages from Twilio
and delegates processing to the WebhookService. Returns TwiML-compatible
responses. All requests are Twilio-signature verified.
"""

from fastapi import APIRouter, Request, Response

from app.core.logging import get_logger
from app.modules.webhook.service import WebhookService

logger = get_logger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])


@router.post("/twilio")
async def twilio_webhook(request: Request) -> Response:
    """Receive and process an inbound Twilio WhatsApp message.

    Twilio sends form-encoded POST data. This endpoint parses the form,
    delegates to WebhookService for processing, and returns an empty
    TwiML response (all replies are sent via the REST API, not TwiML).

    Args:
        request: The incoming FastAPI request containing Twilio form data.

    Returns:
        An empty TwiML response with 200 status.
    """
    form_data = await request.form()
    form_dict = dict(form_data)

    service = WebhookService()
    await service.process_inbound_message(request, form_dict)

    # Return empty TwiML — responses are sent via Twilio REST API
    twiml_response = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
    return Response(content=twiml_response, media_type="application/xml")
