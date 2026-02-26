"""Booking handlers for service selection, slot selection, and confirmation states.

Handles SELECTING_SERVICE, SELECTING_SLOT, and CONFIRMING_DETAILS states.
Each handler queries the database with clinic_id isolation and returns
the next state, response messages, and updated context.
"""

import random
import string
from datetime import date, timedelta, datetime, timezone

from app.core.exceptions import SlotAlreadyLockedError, SlotNotAvailableError
from app.core.logging import get_logger
from app.db.client import get_supabase_client
from app.modules.flow.states import ConversationState
from app.modules.flow import templates

logger = get_logger(__name__)


def _generate_booking_reference() -> str:
    """Generate a unique booking reference in format MED-XXXXX.

    Returns:
        A booking reference string like 'MED-00142'.
    """
    number = random.randint(10000, 99999)
    return f"MED-{number}"


async def handle_selecting_service(
    clinic_id: str,
    clinic: dict,
    patient_whatsapp: str,
    message_body: str,
    context: dict,
) -> tuple[ConversationState, list[str], dict]:
    """Handle the SELECTING_SERVICE state.

    If the patient sends '1' (Book Appointment) or is already in this state,
    show the numbered list of active services for the clinic.
    If the patient sends a service number, store the selection and move to slot selection.

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
    clinic_name = clinic.get("name", "Medical Centre")

    # If patient is selecting from the main menu
    if message_body in ("1", "2", "3"):
        if message_body == "2":
            # View Available Slots — show all slots without service filter
            return await _show_all_available_slots(clinic_id, clinic, context)
        elif message_body == "3":
            # FAQs — handled by FAQ handler, but transition from here
            return ConversationState.IDLE, [], {**context, "_redirect_faq": True}

    # Check if we have services cached in context
    services_cache = context.get("services_list")

    if not services_cache:
        # Query active services for this clinic
        result = (
            db.table("services")
            .select("id, name, booking_fee_usd, duration_minutes")
            .eq("clinic_id", clinic_id)
            .eq("is_active", True)
            .order("display_order")
            .execute()
        )

        if not result.data:
            return (
                ConversationState.IDLE,
                ["This clinic has no services available at the moment. Please try again later."],
                context,
            )

        services_cache = result.data
        context["services_list"] = services_cache

        # Show service list
        msg = templates.service_list_message(clinic_name, services_cache)
        return ConversationState.SELECTING_SERVICE, [msg], context

    # Patient is selecting a service by number
    try:
        selection = int(message_body)
        if 1 <= selection <= len(services_cache):
            selected = services_cache[selection - 1]
            context["selected_service_id"] = selected["id"]
            context["selected_service_name"] = selected["name"]
            context["selected_service_fee"] = float(selected.get("booking_fee_usd", 0))

            # Show available slots for this service
            return await _show_slots_for_service(clinic_id, clinic, context)
        else:
            msg = templates.invalid_input_message(
                templates.service_list_message(clinic_name, services_cache)
            )
            return ConversationState.SELECTING_SERVICE, [msg], context
    except ValueError:
        msg = templates.invalid_input_message(
            templates.service_list_message(clinic_name, services_cache)
        )
        return ConversationState.SELECTING_SERVICE, [msg], context


async def _show_slots_for_service(
    clinic_id: str,
    clinic: dict,
    context: dict,
) -> tuple[ConversationState, list[str], dict]:
    """Query and display available slots for the selected service.

    Args:
        clinic_id: The clinic UUID.
        clinic: The full clinic record dict.
        context: The current session context dict.

    Returns:
        Tuple of (new_state, response_messages, updated_context).
    """
    db = get_supabase_client()
    service_id = context.get("selected_service_id")

    today = date.today()
    end_date = today + timedelta(days=7)

    result = (
        db.table("slots")
        .select("id, slot_date, start_time, end_time, practitioner_id")
        .eq("clinic_id", clinic_id)
        .eq("status", "available")
        .gte("slot_date", today.isoformat())
        .lte("slot_date", end_date.isoformat())
        .order("slot_date")
        .order("start_time")
        .execute()
    )

    # Filter by service_id if set on the slot
    slots = result.data if result.data else []
    if service_id:
        # Include slots that match the service or have no service filter
        slots = [
            s for s in slots
            if s.get("service_id") == service_id or s.get("service_id") is None
        ]

    if not slots:
        return ConversationState.IDLE, [templates.no_slots_message()], context

    # Enrich with practitioner names
    enriched_slots = []
    for slot in slots[:10]:  # Limit to 10 slots for readability
        prac_name = None
        if slot.get("practitioner_id"):
            prac_result = (
                db.table("practitioners")
                .select("name")
                .eq("id", slot["practitioner_id"])
                .eq("clinic_id", clinic_id)
                .execute()
            )
            if prac_result.data:
                prac_name = prac_result.data[0]["name"]
        enriched_slots.append({
            **slot,
            "practitioner_name": prac_name,
        })

    context["available_slots"] = enriched_slots
    msg = templates.slot_list_message(enriched_slots)
    return ConversationState.SELECTING_SLOT, [msg], context


async def _show_all_available_slots(
    clinic_id: str,
    clinic: dict,
    context: dict,
) -> tuple[ConversationState, list[str], dict]:
    """Show all available slots without service filter.

    Args:
        clinic_id: The clinic UUID.
        clinic: The full clinic record dict.
        context: The current session context dict.

    Returns:
        Tuple of (new_state, response_messages, updated_context).
    """
    db = get_supabase_client()
    today = date.today()
    end_date = today + timedelta(days=7)

    result = (
        db.table("slots")
        .select("id, slot_date, start_time, end_time, practitioner_id")
        .eq("clinic_id", clinic_id)
        .eq("status", "available")
        .gte("slot_date", today.isoformat())
        .lte("slot_date", end_date.isoformat())
        .order("slot_date")
        .order("start_time")
        .limit(15)
        .execute()
    )

    slots = result.data if result.data else []
    if not slots:
        return (
            ConversationState.IDLE,
            [templates.no_slots_message()],
            context,
        )

    enriched = []
    for slot in slots:
        prac_name = None
        if slot.get("practitioner_id"):
            prac_result = (
                db.table("practitioners")
                .select("name")
                .eq("id", slot["practitioner_id"])
                .eq("clinic_id", clinic_id)
                .execute()
            )
            if prac_result.data:
                prac_name = prac_result.data[0]["name"]
        enriched.append({**slot, "practitioner_name": prac_name})

    msg = templates.slot_list_message(enriched)
    return ConversationState.IDLE, [msg, "To book, reply *MENU* and select Book Appointment."], context


async def handle_selecting_slot(
    clinic_id: str,
    clinic: dict,
    patient_whatsapp: str,
    message_body: str,
    context: dict,
) -> tuple[ConversationState, list[str], dict]:
    """Handle the SELECTING_SLOT state.

    Patient selects a slot by number. Stores the selection and shows
    the booking summary for confirmation.

    Args:
        clinic_id: The clinic UUID.
        clinic: The full clinic record dict.
        patient_whatsapp: The patient's WhatsApp number.
        message_body: The patient's message text.
        context: The current session context dict.

    Returns:
        Tuple of (new_state, response_messages, updated_context).
    """
    available_slots = context.get("available_slots", [])

    if not available_slots:
        return await _show_slots_for_service(clinic_id, clinic, context)

    try:
        selection = int(message_body)
        if 1 <= selection <= len(available_slots):
            selected = available_slots[selection - 1]
            context["selected_slot_id"] = selected["id"]
            context["selected_slot_date"] = selected["slot_date"]
            context["selected_slot_start"] = selected["start_time"]
            context["selected_slot_end"] = selected["end_time"]
            context["selected_practitioner_id"] = selected.get("practitioner_id")
            context["selected_practitioner_name"] = selected.get("practitioner_name")

            # Show booking summary
            msg = templates.booking_summary_message(
                service_name=context.get("selected_service_name", "Consultation"),
                practitioner_name=selected.get("practitioner_name"),
                slot_date=selected["slot_date"],
                start_time=selected["start_time"],
                booking_fee=context.get("selected_service_fee", 0),
            )
            return ConversationState.CONFIRMING_DETAILS, [msg], context
        else:
            msg = templates.invalid_input_message(
                templates.slot_list_message(available_slots)
            )
            return ConversationState.SELECTING_SLOT, [msg], context
    except ValueError:
        msg = templates.invalid_input_message(
            templates.slot_list_message(available_slots)
        )
        return ConversationState.SELECTING_SLOT, [msg], context


async def handle_confirming_details(
    clinic_id: str,
    clinic: dict,
    patient_whatsapp: str,
    message_body: str,
    context: dict,
) -> tuple[ConversationState, list[str], dict]:
    """Handle the CONFIRMING_DETAILS state.

    Patient replies YES to confirm booking and proceed to payment,
    or NO to cancel.

    Args:
        clinic_id: The clinic UUID.
        clinic: The full clinic record dict.
        patient_whatsapp: The patient's WhatsApp number.
        message_body: The patient's message text.
        context: The current session context dict.

    Returns:
        Tuple of (new_state, response_messages, updated_context).

    Raises:
        SlotAlreadyLockedError: If the slot lock fails (slot was taken).
    """
    db = get_supabase_client()
    upper_body = message_body.upper().strip()

    if upper_body == "NO":
        return ConversationState.IDLE, [templates.cancel_message()], {}

    if upper_body != "YES":
        summary = templates.booking_summary_message(
            service_name=context.get("selected_service_name", "Consultation"),
            practitioner_name=context.get("selected_practitioner_name"),
            slot_date=context.get("selected_slot_date", ""),
            start_time=context.get("selected_slot_start", ""),
            booking_fee=context.get("selected_service_fee", 0),
        )
        msg = templates.invalid_input_message(summary)
        return ConversationState.CONFIRMING_DETAILS, [msg], context

    # YES — proceed to create appointment and initiate payment
    slot_id = context.get("selected_slot_id")
    session_id = context.get("session_id", "")

    # Attempt atomic slot lock
    lock_result = (
        db.table("slots")
        .update({
            "status": "locked",
            "locked_until": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
            "locked_by_session": session_id,
        })
        .eq("id", slot_id)
        .eq("status", "available")
        .eq("clinic_id", clinic_id)
        .execute()
    )

    if not lock_result.data:
        return (
            ConversationState.IDLE,
            [templates.slot_taken_message()],
            {},
        )

    # Generate booking reference
    booking_ref = _generate_booking_reference()

    # Create appointment record
    appointment_data = {
        "clinic_id": clinic_id,
        "patient_id": context.get("patient_id"),
        "slot_id": slot_id,
        "service_id": context.get("selected_service_id"),
        "practitioner_id": context.get("selected_practitioner_id"),
        "status": "pending_payment",
        "booking_reference": booking_ref,
    }
    appt_result = db.table("appointments").insert(appointment_data).execute()

    if not appt_result.data:
        # Release the slot lock on failure
        db.table("slots").update({
            "status": "available",
            "locked_until": None,
            "locked_by_session": None,
        }).eq("id", slot_id).eq("clinic_id", clinic_id).execute()
        return (
            ConversationState.IDLE,
            [templates.error_recovery_message()],
            {},
        )

    appointment_id = appt_result.data[0]["id"]
    context["appointment_id"] = appointment_id
    context["booking_reference"] = booking_ref

    # Create payment record
    booking_fee = context.get("selected_service_fee", 0)
    clean_number = patient_whatsapp.replace("whatsapp:", "").replace("+", "")

    payment_data = {
        "clinic_id": clinic_id,
        "appointment_id": appointment_id,
        "amount_usd": booking_fee,
        "currency": "USD",
        "provider": "ecocash",
        "customer_msisdn": clean_number,
        "status": "pending",
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
    }
    payment_result = db.table("payments").insert(payment_data).execute()

    if not payment_result.data:
        # Rollback: cancel appointment and release slot
        db.table("appointments").update({"status": "cancelled"}).eq(
            "id", appointment_id
        ).eq("clinic_id", clinic_id).execute()
        db.table("slots").update({
            "status": "available",
            "locked_until": None,
            "locked_by_session": None,
        }).eq("id", slot_id).eq("clinic_id", clinic_id).execute()
        return (
            ConversationState.IDLE,
            [templates.error_recovery_message()],
            {},
        )

    payment_id = payment_result.data[0]["id"]
    source_reference = payment_result.data[0]["source_reference"]
    context["payment_id"] = payment_id
    context["source_reference"] = str(source_reference)

    # If booking fee is zero, skip payment and confirm directly
    if booking_fee <= 0:
        db.table("payments").update({
            "status": "paid",
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", payment_id).eq("clinic_id", clinic_id).execute()

        db.table("appointments").update({
            "status": "confirmed",
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", appointment_id).eq("clinic_id", clinic_id).execute()

        db.table("slots").update({"status": "booked"}).eq(
            "id", slot_id
        ).eq("clinic_id", clinic_id).execute()

        # Schedule reminder
        _schedule_reminder(db, clinic_id, appointment_id, context)

        confirmation = templates.payment_confirmed_message(
            patient_name=context.get("patient_name"),
            booking_reference=booking_ref,
            service_name=context.get("selected_service_name", "Consultation"),
            practitioner_name=context.get("selected_practitioner_name"),
            slot_date=context.get("selected_slot_date", ""),
            start_time=context.get("selected_slot_start", ""),
            clinic_name=clinic.get("name", "Medical Centre"),
        )
        return ConversationState.IDLE, [confirmation], {}

    # Initiate EcoCash payment
    context["awaiting_payment"] = True

    logger.info(
        "booking_created_awaiting_payment",
        clinic_id=clinic_id,
        patient_whatsapp=patient_whatsapp,
        appointment_id=appointment_id,
        booking_reference=booking_ref,
    )

    return ConversationState.AWAITING_PAYMENT, [], context


def _schedule_reminder(
    db, clinic_id: str, appointment_id: str, context: dict
) -> None:
    """Schedule a 24-hour reminder for the appointment.

    Args:
        db: The Supabase client.
        clinic_id: The clinic UUID.
        appointment_id: The appointment UUID.
        context: The session context with slot date/time info.
    """
    try:
        slot_date = context.get("selected_slot_date")
        slot_start = context.get("selected_slot_start")
        if slot_date and slot_start:
            # Parse date and time, schedule 24h before
            appt_dt = datetime.fromisoformat(f"{slot_date}T{slot_start}")
            reminder_dt = appt_dt - timedelta(hours=24)
            # Ensure reminder is in the future
            if reminder_dt > datetime.now(timezone.utc):
                db.table("reminders").insert({
                    "appointment_id": appointment_id,
                    "clinic_id": clinic_id,
                    "scheduled_for": reminder_dt.isoformat(),
                    "status": "pending",
                }).execute()
    except Exception as exc:
        logger.error(
            "reminder_scheduling_failed",
            clinic_id=clinic_id,
            appointment_id=appointment_id,
            error=str(exc),
        )
