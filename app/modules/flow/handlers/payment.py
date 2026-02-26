"""Payment state handlers for AWAITING_PAYMENT and PAYMENT_PROCESSING states.

Handles EcoCash payment initiation and processing. Integrates with the
ecocash_client module for actual payment API calls.
"""

from datetime import datetime, timezone

from app.core.exceptions import PaymentInitiationError
from app.core.logging import get_logger
from app.db.client import get_supabase_client
from app.modules.flow.states import ConversationState
from app.modules.flow import templates

logger = get_logger(__name__)


async def handle_awaiting_payment(
    clinic_id: str,
    clinic: dict,
    patient_whatsapp: str,
    message_body: str,
    context: dict,
) -> tuple[ConversationState, list[str], dict]:
    """Handle the AWAITING_PAYMENT state.

    Initiates the EcoCash payment and transitions to PAYMENT_PROCESSING.
    This state is entered after the patient confirms booking details.

    Args:
        clinic_id: The clinic UUID.
        clinic: The full clinic record dict.
        patient_whatsapp: The patient's WhatsApp number.
        message_body: The patient's message text.
        context: The current session context dict.

    Returns:
        Tuple of (new_state, response_messages, updated_context).
    """
    db = get_supabase_client()

    payment_id = context.get("payment_id")
    source_reference = context.get("source_reference")
    booking_fee = context.get("selected_service_fee", 0)
    service_name = context.get("selected_service_name", "Consultation")
    clean_number = patient_whatsapp.replace("whatsapp:", "").replace("+", "")

    if not payment_id or not source_reference:
        logger.error(
            "payment_missing_context",
            clinic_id=clinic_id,
            patient_whatsapp=patient_whatsapp,
            context_keys=list(context.keys()),
        )
        return (
            ConversationState.IDLE,
            [templates.error_recovery_message()],
            {},
        )

    try:
        # Import and call the EcoCash client
        from app.modules.payments.ecocash_client import EcoCashClient

        ecocash = EcoCashClient()
        result = await ecocash.initiate_payment(
            customer_msisdn=clean_number,
            amount=booking_fee,
            reason=f"Booking Fee - {service_name}",
            currency="USD",
            source_reference=source_reference,
        )

        # Update payment status to processing
        db.table("payments").update({
            "status": "processing",
        }).eq("id", payment_id).eq("clinic_id", clinic_id).execute()

        msg = templates.payment_initiated_message(booking_fee, "USD")
        return ConversationState.PAYMENT_PROCESSING, [msg], context

    except PaymentInitiationError as exc:
        logger.error(
            "payment_initiation_failed",
            clinic_id=clinic_id,
            patient_whatsapp=patient_whatsapp,
            payment_id=payment_id,
            error=exc.message,
        )

        # Release slot and cancel appointment
        await _rollback_booking(db, clinic_id, context)

        return (
            ConversationState.IDLE,
            [templates.payment_failed_message(exc.message)],
            {},
        )


async def handle_payment_processing(
    clinic_id: str,
    clinic: dict,
    patient_whatsapp: str,
    message_body: str,
    context: dict,
) -> tuple[ConversationState, list[str], dict]:
    """Handle the PAYMENT_PROCESSING state.

    While payment is processing, the patient may send messages.
    We check payment status and respond accordingly. The actual payment
    confirmation comes via the expire-payments cron or EcoCash callback.

    Args:
        clinic_id: The clinic UUID.
        clinic: The full clinic record dict.
        patient_whatsapp: The patient's WhatsApp number.
        message_body: The patient's message text.
        context: The current session context dict.

    Returns:
        Tuple of (new_state, response_messages, updated_context).
    """
    db = get_supabase_client()
    payment_id = context.get("payment_id")

    if not payment_id:
        return (
            ConversationState.IDLE,
            [templates.error_recovery_message()],
            {},
        )

    # Check current payment status
    result = (
        db.table("payments")
        .select("status, confirmed_at")
        .eq("id", payment_id)
        .eq("clinic_id", clinic_id)
        .execute()
    )

    if not result.data:
        return (
            ConversationState.IDLE,
            [templates.error_recovery_message()],
            {},
        )

    payment = result.data[0]

    if payment["status"] == "paid":
        # Payment confirmed — complete booking
        return await _complete_booking(db, clinic_id, clinic, context)

    if payment["status"] in ("failed", "expired"):
        return (
            ConversationState.IDLE,
            [templates.payment_failed_message()],
            {},
        )

    # Still processing — inform patient
    return (
        ConversationState.PAYMENT_PROCESSING,
        [
            "⏳ Your payment is still being processed. "
            "Please check your phone for the EcoCash prompt.\n\n"
            "Reply *CANCEL* to cancel the booking."
        ],
        context,
    )


async def _complete_booking(
    db, clinic_id: str, clinic: dict, context: dict
) -> tuple[ConversationState, list[str], dict]:
    """Complete a booking after payment confirmation.

    Updates appointment status, marks slot as booked, and schedules reminder.

    Args:
        db: The Supabase client.
        clinic_id: The clinic UUID.
        clinic: The full clinic record dict.
        context: The session context dict.

    Returns:
        Tuple of (new_state, response_messages, updated_context).
    """
    appointment_id = context.get("appointment_id")
    slot_id = context.get("selected_slot_id")

    # Confirm appointment
    db.table("appointments").update({
        "status": "confirmed",
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", appointment_id).eq("clinic_id", clinic_id).execute()

    # Mark slot as booked
    db.table("slots").update({
        "status": "booked",
    }).eq("id", slot_id).eq("clinic_id", clinic_id).execute()

    # Schedule reminder (24h before)
    from app.modules.flow.handlers.booking import _schedule_reminder
    _schedule_reminder(db, clinic_id, appointment_id, context)

    confirmation = templates.payment_confirmed_message(
        patient_name=context.get("patient_name"),
        booking_reference=context.get("booking_reference", ""),
        service_name=context.get("selected_service_name", "Consultation"),
        practitioner_name=context.get("selected_practitioner_name"),
        slot_date=context.get("selected_slot_date", ""),
        start_time=context.get("selected_slot_start", ""),
        clinic_name=clinic.get("name", "Medical Centre"),
    )

    logger.info(
        "booking_confirmed",
        clinic_id=clinic_id,
        appointment_id=appointment_id,
        booking_reference=context.get("booking_reference"),
    )

    return ConversationState.IDLE, [confirmation], {}


async def _rollback_booking(db, clinic_id: str, context: dict) -> None:
    """Rollback a booking by cancelling the appointment and releasing the slot.

    Args:
        db: The Supabase client.
        clinic_id: The clinic UUID.
        context: The session context dict.
    """
    appointment_id = context.get("appointment_id")
    slot_id = context.get("selected_slot_id")
    payment_id = context.get("payment_id")

    try:
        if payment_id:
            db.table("payments").update({
                "status": "failed",
                "failure_reason": "Payment initiation failed",
            }).eq("id", payment_id).eq("clinic_id", clinic_id).execute()

        if appointment_id:
            db.table("appointments").update({
                "status": "cancelled",
            }).eq("id", appointment_id).eq("clinic_id", clinic_id).execute()

        if slot_id:
            db.table("slots").update({
                "status": "available",
                "locked_until": None,
                "locked_by_session": None,
            }).eq("id", slot_id).eq("clinic_id", clinic_id).execute()

    except Exception as exc:
        logger.error(
            "booking_rollback_failed",
            clinic_id=clinic_id,
            appointment_id=appointment_id,
            error=str(exc),
        )
