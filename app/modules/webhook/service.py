"""Webhook orchestration service.

Handles the end-to-end processing of an inbound Twilio WhatsApp message
for Divine Comfort Clinic (single-tenant mode):
1. Load the single clinic record
2. Validate Twilio signature
3. Check rate limiting
4. Delegate to the flow engine
5. Send response messages back via Twilio
6. Log all conversation events
"""

import time
from datetime import datetime, timezone

from fastapi import Request

from app.config import get_settings
from app.core.exceptions import (
    ClinicNotFoundError,
    RateLimitExceededError,
)
from app.core.logging import get_logger
from app.core.twilio_client import send_whatsapp_message
from app.db.client import get_supabase_client
from app.modules.webhook.schemas import TwilioWebhookForm
from app.modules.webhook.security import validate_twilio_signature
from app.modules.flow.engine import FlowEngine

logger = get_logger(__name__)

# Rate limit: 20 messages per 5 minutes (300 seconds)
RATE_LIMIT_MAX = 20
RATE_LIMIT_WINDOW_SECONDS = 300
RATE_LIMIT_COOLDOWN_SECONDS = 60


class WebhookService:
    """Orchestrates inbound WhatsApp message processing.

    Coordinates clinic resolution, signature validation, rate limiting,
    conversation flow, and response delivery.
    """

    def __init__(self):
        """Initialize the webhook service with a Supabase client and flow engine."""
        self.db = get_supabase_client()
        self.flow_engine = FlowEngine()

    async def process_inbound_message(
        self, request: Request, form_data: dict
    ) -> dict:
        """Process an inbound WhatsApp message end-to-end.

        Args:
            request: The incoming FastAPI request for signature validation.
            form_data: Parsed Twilio webhook form data.

        Returns:
            A dict with status and message SID(s).

        Raises:
            ClinicNotFoundError: If no clinic matches the To number.
            InvalidTwilioSignatureError: If signature validation fails.
            RateLimitExceededError: If the patient exceeds rate limits.
        """
        start_time = time.monotonic()

        # Parse the form data
        parsed = TwilioWebhookForm(
            MessageSid=form_data.get("MessageSid", ""),
            From_=form_data.get("From", ""),
            To=form_data.get("To", ""),
            Body=form_data.get("Body", ""),
            NumMedia=form_data.get("NumMedia", "0"),
            ProfileName=form_data.get("ProfileName"),
        )

        patient_whatsapp = parsed.From_
        clinic_whatsapp = parsed.To
        message_body = parsed.Body.strip()
        profile_name = parsed.ProfileName

        # Step 1: Load the single clinic record
        clinic = await self._get_clinic()
        clinic_id = clinic["id"]

        # Step 2: Validate Twilio signature
        await validate_twilio_signature(request, form_data, clinic.get("twilio_auth_token"))

        # Step 3: Check rate limiting
        await self._check_rate_limit(clinic_id, patient_whatsapp)

        # Step 4: Log inbound message
        await self._log_conversation(
            clinic_id=clinic_id,
            patient_whatsapp=patient_whatsapp,
            direction="inbound",
            message_text=message_body,
            flow_state=None,
        )

        # Step 5: Delegate to flow engine
        response_messages, final_state = await self.flow_engine.process(
            clinic_id=clinic_id,
            clinic=clinic,
            patient_whatsapp=patient_whatsapp,
            message_body=message_body,
            profile_name=profile_name,
        )

        # Step 6: Send response messages
        message_sids = []
        for msg in response_messages:
            sid = await send_whatsapp_message(
                to=patient_whatsapp,
                body=msg,
                clinic_id=clinic_id,
            )
            if sid:
                message_sids.append(sid)

            # Log outbound message
            await self._log_conversation(
                clinic_id=clinic_id,
                patient_whatsapp=patient_whatsapp,
                direction="outbound",
                message_text=msg,
                flow_state=final_state,
            )

        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            "webhook_processed",
            clinic_id=clinic_id,
            patient_whatsapp=patient_whatsapp,
            state=final_state,
            duration_ms=duration_ms,
        )

        return {"status": "ok", "message_sids": message_sids}

    async def _get_clinic(self) -> dict:
        """Load the single Divine Comfort Clinic record.

        Looks up the clinic by the configured CLINIC_WHATSAPP_NUMBER.
        In single-tenant mode there is only one clinic.

        Returns:
            The clinic record as a dict.

        Raises:
            ClinicNotFoundError: If the clinic has not been seeded yet.
        """
        settings = get_settings()
        clean_number = settings.CLINIC_WHATSAPP_NUMBER.replace("+", "")

        result = (
            self.db.table("clinics")
            .select("*")
            .eq("whatsapp_number", clean_number)
            .eq("is_active", True)
            .execute()
        )

        if not result.data:
            raise ClinicNotFoundError(
                message="Divine Comfort Clinic not found — run the app once to auto-seed",
                context={"whatsapp_number": clean_number},
            )

        return result.data[0]

    async def _check_rate_limit(
        self, clinic_id: str, patient_whatsapp: str
    ) -> None:
        """Check if a patient has exceeded the message rate limit.

        Tracks message counts in the session context JSONB field.
        Limit: 20 messages per 5 minutes. Cooldown: 60 seconds.

        Args:
            clinic_id: The clinic UUID.
            patient_whatsapp: The patient's WhatsApp number.

        Raises:
            RateLimitExceededError: If the patient exceeds the rate limit.
        """
        now = datetime.now(timezone.utc).isoformat()

        # Get or create session
        result = (
            self.db.table("conversation_sessions")
            .select("id, context")
            .eq("clinic_id", clinic_id)
            .eq("patient_whatsapp", patient_whatsapp)
            .execute()
        )

        if not result.data:
            return  # New session, no rate limit concern

        session = result.data[0]
        context = session.get("context", {}) or {}
        rate_data = context.get("rate_limit", {})

        # Check cooldown
        cooldown_until = rate_data.get("cooldown_until")
        if cooldown_until:
            cooldown_dt = datetime.fromisoformat(cooldown_until)
            if datetime.now(timezone.utc) < cooldown_dt:
                raise RateLimitExceededError(
                    message="You're sending messages too quickly. Please wait a moment.",
                    context={
                        "clinic_id": clinic_id,
                        "patient_whatsapp": patient_whatsapp,
                    },
                )

        # Count messages in window
        timestamps = rate_data.get("timestamps", [])
        window_start = datetime.now(timezone.utc).timestamp() - RATE_LIMIT_WINDOW_SECONDS

        # Filter to only timestamps within the window
        recent = [ts for ts in timestamps if ts > window_start]
        recent.append(datetime.now(timezone.utc).timestamp())

        if len(recent) > RATE_LIMIT_MAX:
            # Set cooldown
            cooldown_until_dt = datetime.fromtimestamp(
                datetime.now(timezone.utc).timestamp() + RATE_LIMIT_COOLDOWN_SECONDS,
                tz=timezone.utc,
            )
            context["rate_limit"] = {
                "timestamps": recent[-RATE_LIMIT_MAX:],
                "cooldown_until": cooldown_until_dt.isoformat(),
            }
            self.db.table("conversation_sessions").update(
                {"context": context}
            ).eq("id", session["id"]).eq("clinic_id", clinic_id).execute()

            # Send throttle message
            await send_whatsapp_message(
                to=patient_whatsapp,
                body="You're sending messages too quickly. Please wait a moment and try again. 🙏",
                clinic_id=clinic_id,
            )

            raise RateLimitExceededError(
                message="Rate limit exceeded",
                context={
                    "clinic_id": clinic_id,
                    "patient_whatsapp": patient_whatsapp,
                },
            )

        # Update timestamps in context
        context["rate_limit"] = {"timestamps": recent[-RATE_LIMIT_MAX:]}
        self.db.table("conversation_sessions").update(
            {"context": context}
        ).eq("id", session["id"]).eq("clinic_id", clinic_id).execute()

    async def _log_conversation(
        self,
        clinic_id: str,
        patient_whatsapp: str,
        direction: str,
        message_text: str,
        flow_state: str | None,
    ) -> None:
        """Log a conversation event to the conversation_logs table.

        Args:
            clinic_id: The clinic UUID.
            patient_whatsapp: The patient's WhatsApp number.
            direction: 'inbound' or 'outbound'.
            message_text: The message text.
            flow_state: The current conversation flow state.
        """
        try:
            self.db.table("conversation_logs").insert(
                {
                    "clinic_id": clinic_id,
                    "patient_whatsapp": patient_whatsapp,
                    "direction": direction,
                    "message_text": message_text,
                    "flow_state": flow_state or "UNKNOWN",
                }
            ).execute()
        except Exception as exc:
            logger.error(
                "conversation_log_failed",
                clinic_id=clinic_id,
                patient_whatsapp=patient_whatsapp,
                direction=direction,
                error=str(exc),
            )
