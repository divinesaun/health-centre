"""Conversation state machine engine.

The flow engine is the heart of the system. It manages conversation state
stored in the conversation_sessions table. For each inbound message:
1. Load/create the patient's session (UPSERT if new)
2. Check session expiry — reset to IDLE if expired
3. Route the message to the correct handler based on current state
4. Save updated state/context back to session
5. On ANY unhandled exception: catch, log, send recovery message, reset to IDLE
"""

from datetime import datetime, timedelta, timezone

from app.core.logging import get_logger
from app.db.client import get_supabase_client
from app.modules.flow.states import ConversationState
from app.modules.flow.handlers.greeting import handle_idle
from app.modules.flow.handlers.booking import (
    handle_selecting_service,
    handle_selecting_slot,
    handle_confirming_details,
)
from app.modules.flow.handlers.payment import (
    handle_awaiting_payment,
    handle_payment_processing,
)
from app.modules.flow.handlers.faq import handle_faq
from app.modules.flow import templates

logger = get_logger(__name__)

SESSION_TTL_MINUTES = 30


class FlowEngine:
    """Conversation state machine that routes messages to handlers.

    Loads session state from the database, routes to the appropriate
    handler, and persists updated state after each interaction.
    """

    def __init__(self):
        """Initialize the flow engine with a Supabase client."""
        self.db = get_supabase_client()

    async def process(
        self,
        clinic_id: str,
        clinic: dict,
        patient_whatsapp: str,
        message_body: str,
        profile_name: str | None = None,
    ) -> tuple[list[str], str]:
        """Process an inbound message through the state machine.

        Args:
            clinic_id: The clinic UUID.
            clinic: The full clinic record dict.
            patient_whatsapp: The patient's WhatsApp number (whatsapp:+263...).
            message_body: The sanitised message body.
            profile_name: The WhatsApp profile name, if available.

        Returns:
            Tuple of (response_messages, final_state_string).
        """
        try:
            # Load or create session
            session = await self._load_or_create_session(clinic_id, patient_whatsapp)
            session_id = session["id"]
            current_state = session["state"]
            context = session.get("context", {}) or {}
            context["session_id"] = session_id

            # Check expiry
            expires_at = session.get("expires_at")
            if expires_at and self._is_expired(expires_at):
                logger.info(
                    "session_expired_reset",
                    clinic_id=clinic_id,
                    patient_whatsapp=patient_whatsapp,
                    previous_state=current_state,
                )
                current_state = ConversationState.IDLE.value
                context = {"session_id": session_id}

            # Check for global commands: CANCEL, BACK, MENU
            upper_body = message_body.upper().strip()
            if upper_body in ("CANCEL", "BACK"):
                new_state = ConversationState.IDLE
                messages = [templates.cancel_message()]
                context = {}
                await self._save_session(session_id, clinic_id, patient_whatsapp, new_state, context)
                return messages, new_state.value

            if upper_body == "MENU":
                current_state = ConversationState.IDLE.value
                context = {"session_id": session_id}

            # Route to handler
            state_enum = ConversationState(current_state)
            new_state, messages, updated_context = await self._route(
                state=state_enum,
                clinic_id=clinic_id,
                clinic=clinic,
                patient_whatsapp=patient_whatsapp,
                message_body=message_body,
                context=context,
                profile_name=profile_name,
            )

            # Handle FAQ redirect
            if updated_context.get("_redirect_faq"):
                del updated_context["_redirect_faq"]
                new_state_faq, faq_messages, faq_context = await handle_faq(
                    clinic_id=clinic_id,
                    clinic=clinic,
                    patient_whatsapp=patient_whatsapp,
                    message_body=message_body,
                    context=updated_context,
                )
                messages = faq_messages
                new_state = new_state_faq
                updated_context = faq_context

            # Save session
            await self._save_session(
                session_id, clinic_id, patient_whatsapp, new_state, updated_context
            )

            return messages, new_state.value

        except Exception as exc:
            # Level 2 error handling — catch all, log, send recovery, reset to IDLE
            logger.error(
                "flow_engine_error",
                clinic_id=clinic_id,
                patient_whatsapp=patient_whatsapp,
                error=str(exc),
                exc_info=True,
            )

            # Try to reset session to IDLE
            try:
                await self._reset_session(clinic_id, patient_whatsapp)
            except Exception:
                pass

            return [templates.error_recovery_message()], ConversationState.IDLE.value

    async def _route(
        self,
        state: ConversationState,
        clinic_id: str,
        clinic: dict,
        patient_whatsapp: str,
        message_body: str,
        context: dict,
        profile_name: str | None = None,
    ) -> tuple[ConversationState, list[str], dict]:
        """Route a message to the appropriate state handler.

        Args:
            state: The current conversation state.
            clinic_id: The clinic UUID.
            clinic: The full clinic record dict.
            patient_whatsapp: The patient's WhatsApp number.
            message_body: The sanitised message body.
            context: The current session context.
            profile_name: The WhatsApp profile name.

        Returns:
            Tuple of (new_state, response_messages, updated_context).
        """
        handlers = {
            ConversationState.IDLE: lambda: handle_idle(
                clinic_id, clinic, patient_whatsapp, message_body, context, profile_name
            ),
            ConversationState.SELECTING_SERVICE: lambda: handle_selecting_service(
                clinic_id, clinic, patient_whatsapp, message_body, context
            ),
            ConversationState.SELECTING_SLOT: lambda: handle_selecting_slot(
                clinic_id, clinic, patient_whatsapp, message_body, context
            ),
            ConversationState.CONFIRMING_DETAILS: lambda: handle_confirming_details(
                clinic_id, clinic, patient_whatsapp, message_body, context
            ),
            ConversationState.AWAITING_PAYMENT: lambda: handle_awaiting_payment(
                clinic_id, clinic, patient_whatsapp, message_body, context
            ),
            ConversationState.PAYMENT_PROCESSING: lambda: handle_payment_processing(
                clinic_id, clinic, patient_whatsapp, message_body, context
            ),
        }

        handler = handlers.get(state)
        if handler:
            return await handler()

        # Unknown state — reset to IDLE
        logger.warning(
            "unknown_state_reset",
            clinic_id=clinic_id,
            state=state.value,
        )
        return await handle_idle(
            clinic_id, clinic, patient_whatsapp, message_body, {}, profile_name
        )

    async def _load_or_create_session(
        self, clinic_id: str, patient_whatsapp: str
    ) -> dict:
        """Load an existing session or create a new one via UPSERT.

        Args:
            clinic_id: The clinic UUID.
            patient_whatsapp: The patient's WhatsApp number.

        Returns:
            The session record as a dict.
        """
        # Try to load existing session
        result = (
            self.db.table("conversation_sessions")
            .select("*")
            .eq("clinic_id", clinic_id)
            .eq("patient_whatsapp", patient_whatsapp)
            .execute()
        )

        if result.data:
            # Update the session expiry
            session = result.data[0]
            new_expires = (datetime.now(timezone.utc) + timedelta(minutes=SESSION_TTL_MINUTES)).isoformat()
            self.db.table("conversation_sessions").update({
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": new_expires,
            }).eq("id", session["id"]).eq("clinic_id", clinic_id).execute()
            return session

        # Create new session
        new_session = {
            "clinic_id": clinic_id,
            "patient_whatsapp": patient_whatsapp,
            "state": ConversationState.IDLE.value,
            "context": {},
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=SESSION_TTL_MINUTES)).isoformat(),
        }
        insert_result = (
            self.db.table("conversation_sessions")
            .insert(new_session)
            .execute()
        )

        if insert_result.data:
            return insert_result.data[0]

        # If insert fails (race condition), try loading again
        retry_result = (
            self.db.table("conversation_sessions")
            .select("*")
            .eq("clinic_id", clinic_id)
            .eq("patient_whatsapp", patient_whatsapp)
            .execute()
        )
        if retry_result.data:
            return retry_result.data[0]

        raise RuntimeError("Failed to create or load session")

    async def _save_session(
        self,
        session_id: str,
        clinic_id: str,
        patient_whatsapp: str,
        new_state: ConversationState,
        context: dict,
    ) -> None:
        """Persist updated session state and context.

        Args:
            session_id: The session UUID.
            clinic_id: The clinic UUID.
            patient_whatsapp: The patient's WhatsApp number.
            new_state: The new conversation state.
            context: The updated session context.
        """
        # Remove non-serializable keys from context
        clean_context = {
            k: v for k, v in context.items()
            if k != "session_id" and v is not None
        }

        self.db.table("conversation_sessions").update({
            "state": new_state.value,
            "context": clean_context,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=SESSION_TTL_MINUTES)).isoformat(),
        }).eq("id", session_id).eq("clinic_id", clinic_id).execute()

    async def _reset_session(
        self, clinic_id: str, patient_whatsapp: str
    ) -> None:
        """Reset a session to IDLE state with empty context.

        Args:
            clinic_id: The clinic UUID.
            patient_whatsapp: The patient's WhatsApp number.
        """
        self.db.table("conversation_sessions").update({
            "state": ConversationState.IDLE.value,
            "context": {},
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=SESSION_TTL_MINUTES)).isoformat(),
        }).eq("clinic_id", clinic_id).eq("patient_whatsapp", patient_whatsapp).execute()

    @staticmethod
    def _is_expired(expires_at: str) -> bool:
        """Check if a session has expired.

        Args:
            expires_at: ISO format timestamp string.

        Returns:
            True if the session has expired, False otherwise.
        """
        try:
            expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            return datetime.now(timezone.utc) > expiry
        except (ValueError, AttributeError):
            return True
