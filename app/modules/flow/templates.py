"""All WhatsApp message templates for MediBook.

Every patient-facing message string lives exclusively in this file.
No message text is hardcoded in handlers or services.
Messages are warm, professional, brief, and action-oriented.
"""


def greeting_message(clinic_name: str, patient_name: str | None = None) -> str:
    """Generate the initial greeting message with main menu.

    Args:
        clinic_name: The clinic's display name.
        patient_name: The patient's first name, if known.

    Returns:
        The formatted greeting message string.
    """
    name_part = f" {patient_name}" if patient_name else ""
    return (
        f"Welcome to *{clinic_name}*! 👋\n"
        f"Hi{name_part}, how can we help you today?\n\n"
        f"1️⃣ Book Appointment\n"
        f"2️⃣ View Available Slots\n"
        f"3️⃣ FAQs\n\n"
        f"Reply with the number of your choice."
    )


def service_list_message(clinic_name: str, services: list[dict]) -> str:
    """Generate a numbered list of available services.

    Args:
        clinic_name: The clinic's display name.
        services: List of service dicts with 'name' and 'booking_fee_usd'.

    Returns:
        The formatted service list message string.
    """
    lines = [f"📋 *Services at {clinic_name}:*\n"]
    for i, svc in enumerate(services, 1):
        fee = svc.get("booking_fee_usd", 0)
        fee_str = f"${fee:.2f}" if fee else "Free"
        lines.append(f"{i}. {svc['name']} ({fee_str})")
    lines.append("\nReply with the number of the service you'd like to book.")
    return "\n".join(lines)


def slot_list_message(slots: list[dict]) -> str:
    """Generate a numbered list of available time slots.

    Args:
        slots: List of slot dicts with 'slot_date', 'start_time', 'end_time',
               and optionally 'practitioner_name'.

    Returns:
        The formatted slot list message string.
    """
    lines = ["🕐 *Available Slots:*\n"]
    for i, slot in enumerate(slots, 1):
        date_str = slot.get("slot_date", "")
        start = slot.get("start_time", "")
        end = slot.get("end_time", "")
        practitioner = slot.get("practitioner_name", "")
        prac_str = f" — {practitioner}" if practitioner else ""
        lines.append(f"{i}. {date_str} | {start} - {end}{prac_str}")
    lines.append("\nReply with the number of your preferred slot.")
    return "\n".join(lines)


def no_slots_message() -> str:
    """Generate message when no slots are available.

    Returns:
        The no-slots-available message string.
    """
    return (
        "😔 Sorry, there are no available slots in the next 7 days.\n\n"
        "Please check back later or contact the clinic directly.\n"
        "Reply *MENU* to return to the main menu."
    )


def booking_summary_message(
    service_name: str,
    practitioner_name: str | None,
    slot_date: str,
    start_time: str,
    booking_fee: float,
) -> str:
    """Generate the booking confirmation summary.

    Args:
        service_name: Name of the selected service.
        practitioner_name: Name of the practitioner, if any.
        slot_date: The appointment date.
        start_time: The appointment start time.
        booking_fee: The booking fee amount in USD.

    Returns:
        The formatted booking summary message string.
    """
    prac_line = f"\n👨‍⚕️ *Doctor:* {practitioner_name}" if practitioner_name else ""
    fee_str = f"${booking_fee:.2f}" if booking_fee else "Free"
    return (
        f"📋 *Booking Summary:*\n\n"
        f"🏥 *Service:* {service_name}{prac_line}\n"
        f"📅 *Date:* {slot_date}\n"
        f"🕐 *Time:* {start_time}\n"
        f"💰 *Booking Fee:* {fee_str}\n\n"
        f"Reply *YES* to confirm and proceed to payment.\n"
        f"Reply *NO* to cancel."
    )


def payment_initiated_message(amount: float, currency: str = "USD") -> str:
    """Generate the payment initiation message.

    Args:
        amount: The payment amount.
        currency: The currency code (default USD).

    Returns:
        The formatted payment initiated message string.
    """
    return (
        f"💳 *Payment Request Sent!*\n\n"
        f"A payment of *{currency} {amount:.2f}* has been sent to your EcoCash.\n"
        f"Please enter your PIN on your phone to complete the payment.\n\n"
        f"⏳ You have 10 minutes to complete this payment.\n"
        f"Reply *CANCEL* to cancel the booking."
    )


def payment_confirmed_message(
    patient_name: str | None,
    booking_reference: str,
    service_name: str,
    practitioner_name: str | None,
    slot_date: str,
    start_time: str,
    clinic_name: str,
    clinic_address: str | None = None,
) -> str:
    """Generate the booking confirmation message after payment.

    Args:
        patient_name: The patient's first name.
        booking_reference: The unique booking reference code.
        service_name: Name of the booked service.
        practitioner_name: Name of the practitioner.
        slot_date: The appointment date.
        start_time: The appointment start time.
        clinic_name: The clinic's display name.
        clinic_address: Optional clinic address.

    Returns:
        The formatted booking confirmation message string.
    """
    name_part = patient_name or "there"
    prac_line = f"\n  3. Doctor: {practitioner_name}" if practitioner_name else ""
    address_line = f"\n\n📍 *{clinic_name}*\n{clinic_address}" if clinic_address else ""
    return (
        f"✅ *Booking Confirmed!*\n\n"
        f"Hi {name_part}, your appointment has been booked successfully.\n\n"
        f"📋 *Details:*\n"
        f"  1. Reference: {booking_reference}\n"
        f"  2. Service: {service_name}{prac_line}\n"
        f"  4. Date: {slot_date}\n"
        f"  5. Time: {start_time}"
        f"{address_line}\n\n"
        f"You will receive a reminder 24 hours before your appointment.\n\n"
        f"Reply *CANCEL* to cancel your booking."
    )


def payment_failed_message(reason: str | None = None) -> str:
    """Generate the payment failure message.

    Args:
        reason: Optional reason for the failure.

    Returns:
        The formatted payment failure message string.
    """
    reason_line = f"\nReason: {reason}" if reason else ""
    return (
        f"❌ *Payment Failed*{reason_line}\n\n"
        f"We couldn't process your payment. Please try again or contact the clinic.\n\n"
        f"Reply *MENU* to return to the main menu."
    )


def payment_expired_message() -> str:
    """Generate the payment expiry message.

    Returns:
        The formatted payment expired message string.
    """
    return (
        "⏰ *Payment Window Expired*\n\n"
        "Your payment window has expired and the slot has been released.\n"
        "Please try booking again.\n\n"
        "Reply *MENU* to return to the main menu."
    )


def slot_taken_message() -> str:
    """Generate the slot-already-taken message.

    Returns:
        The formatted slot taken message string.
    """
    return (
        "😔 Sorry, that slot was just taken by another patient.\n"
        "Please choose another slot.\n\n"
        "Reply *MENU* to return to the main menu."
    )


def cancel_message() -> str:
    """Generate the cancellation confirmation message.

    Returns:
        The formatted cancellation message string.
    """
    return (
        "🔙 Your current action has been cancelled.\n\n"
        "Reply *MENU* or send any message to start again."
    )


def error_recovery_message() -> str:
    """Generate the friendly error recovery message.

    Sent when an unhandled exception occurs during flow processing.

    Returns:
        The formatted error recovery message string.
    """
    return (
        "😅 Something went wrong on our end. Let's start over!\n\n"
        "Send any message to begin again."
    )


def invalid_input_message(current_prompt: str) -> str:
    """Generate a gentle nudge for unexpected input.

    Re-sends the current prompt with a soft prefix instead of an error.

    Args:
        current_prompt: The current prompt to re-send.

    Returns:
        The formatted invalid input message string.
    """
    return (
        f"I didn't quite catch that. Let me help you:\n\n{current_prompt}"
    )


def faq_message(clinic_name: str) -> str:
    """Generate the FAQ menu message.

    Args:
        clinic_name: The clinic's display name.

    Returns:
        The formatted FAQ message string.
    """
    return (
        f"❓ *Frequently Asked Questions — {clinic_name}*\n\n"
        f"1️⃣ What are your operating hours?\n"
        f"2️⃣ How do I cancel an appointment?\n"
        f"3️⃣ What payment methods do you accept?\n"
        f"4️⃣ How do I reschedule?\n\n"
        f"Reply with a number, or *MENU* to go back."
    )


def faq_hours_message() -> str:
    """Generate the operating hours FAQ response.

    Returns:
        The formatted FAQ hours message string.
    """
    return (
        "🕐 *Operating Hours:*\n\n"
        "Monday - Friday: 8:00 AM - 5:00 PM\n"
        "Saturday: 8:00 AM - 1:00 PM\n"
        "Sunday & Public Holidays: Closed\n\n"
        "Reply *MENU* to return to the main menu."
    )


def faq_cancel_message() -> str:
    """Generate the cancellation FAQ response.

    Returns:
        The formatted FAQ cancellation message string.
    """
    return (
        "🔙 *How to Cancel:*\n\n"
        "Reply *CANCEL* at any time during the booking process,\n"
        "or after booking, reply *CANCEL* with your booking reference.\n\n"
        "Reply *MENU* to return to the main menu."
    )


def faq_payment_message() -> str:
    """Generate the payment methods FAQ response.

    Returns:
        The formatted FAQ payment message string.
    """
    return (
        "💳 *Payment Methods:*\n\n"
        "We accept EcoCash mobile payments.\n"
        "A payment request will be sent to your phone during booking.\n\n"
        "Reply *MENU* to return to the main menu."
    )


def faq_reschedule_message() -> str:
    """Generate the rescheduling FAQ response.

    Returns:
        The formatted FAQ reschedule message string.
    """
    return (
        "📅 *Rescheduling:*\n\n"
        "To reschedule, please cancel your current appointment\n"
        "and book a new one. Rescheduling will be available soon.\n\n"
        "Reply *MENU* to return to the main menu."
    )


def reminder_message(
    patient_name: str | None,
    booking_reference: str,
    service_name: str,
    slot_date: str,
    start_time: str,
    clinic_name: str,
) -> str:
    """Generate the 24-hour appointment reminder message.

    Args:
        patient_name: The patient's first name.
        booking_reference: The unique booking reference code.
        service_name: Name of the booked service.
        slot_date: The appointment date.
        start_time: The appointment start time.
        clinic_name: The clinic's display name.

    Returns:
        The formatted reminder message string.
    """
    name_part = patient_name or "there"
    return (
        f"⏰ *Appointment Reminder*\n\n"
        f"Hi {name_part}, this is a reminder for your upcoming appointment.\n\n"
        f"📋 *Details:*\n"
        f"  Reference: {booking_reference}\n"
        f"  Service: {service_name}\n"
        f"  Date: {slot_date}\n"
        f"  Time: {start_time}\n"
        f"  Clinic: {clinic_name}\n\n"
        f"We look forward to seeing you! 🏥"
    )


def rate_limit_message() -> str:
    """Generate the rate limit throttle message.

    Returns:
        The formatted rate limit message string.
    """
    return (
        "You're sending messages too quickly. "
        "Please wait a moment and try again. 🙏"
    )
