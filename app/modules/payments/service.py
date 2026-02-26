"""Payments business logic service.

Handles payment lifecycle: initiation, confirmation, expiry, and rollback.
Level 3 error handling for payment-specific exceptions.
"""

from datetime import datetime, timedelta, timezone

from app.core.exceptions import PaymentExpiredError, PaymentInitiationError
from app.core.logging import get_logger
from app.core.twilio_client import send_whatsapp_message
from app.db.client import get_supabase_client
from app.modules.flow import templates
from app.modules.payments.ecocash_client import EcoCashClient

logger = get_logger(__name__)

PAYMENT_EXPIRY_MINUTES = 10


class PaymentService:
    """Business logic for payment operations.

    Coordinates payment initiation, confirmation, and expiry.
    Handles rollback of slots and appointments on payment failure.
    """

    def __init__(self):
        """Initialize with Supabase client and EcoCash client."""
        self.db = get_supabase_client()
        self.ecocash = EcoCashClient()

    async def handle_ecocash_callback(self, payload: dict) -> dict:
        """Process an EcoCash payment callback/notification.

        Looks up the payment by sourceReference, updates status,
        and completes or cancels the booking accordingly.

        Args:
            payload: The EcoCash callback payload dict.

        Returns:
            A dict with the processing result.
        """
        source_ref = payload.get("sourceReference", "")
        ecocash_status = payload.get("status", "").upper()

        if not source_ref:
            logger.warning("ecocash_callback_missing_ref", payload=str(payload))
            return {"status": "error", "message": "Missing sourceReference"}

        # Look up payment by source_reference
        result = (
            self.db.table("payments")
            .select("*, appointments(*), clinics(*)")
            .eq("source_reference", source_ref)
            .execute()
        )

        if not result.data:
            logger.warning("ecocash_callback_unknown_ref", source_reference=source_ref)
            return {"status": "error", "message": "Unknown sourceReference"}

        payment = result.data[0]
        clinic_id = payment["clinic_id"]
        payment_id = payment["id"]
        appointment_id = payment.get("appointment_id")

        if payment["status"] in ("paid", "refunded"):
            logger.info("ecocash_callback_already_processed", payment_id=payment_id)
            return {"status": "ok", "message": "Already processed"}

        if ecocash_status in ("COMPLETED", "SUCCESS", "PAID"):
            return await self._confirm_payment(payment, clinic_id)
        elif ecocash_status in ("FAILED", "CANCELLED", "REJECTED"):
            return await self._fail_payment(
                payment, clinic_id, reason=f"EcoCash status: {ecocash_status}"
            )
        else:
            logger.warning(
                "ecocash_callback_unknown_status",
                ecocash_status=ecocash_status,
                payment_id=payment_id,
            )
            return {"status": "ok", "message": f"Unhandled status: {ecocash_status}"}

    async def _confirm_payment(self, payment: dict, clinic_id: str) -> dict:
        """Confirm a payment and complete the booking.

        Args:
            payment: The payment record dict.
            clinic_id: The clinic UUID.

        Returns:
            A dict with confirmation result.
        """
        payment_id = payment["id"]
        appointment_id = payment.get("appointment_id")
        now = datetime.now(timezone.utc).isoformat()

        # Update payment status
        self.db.table("payments").update({
            "status": "paid",
            "confirmed_at": now,
        }).eq("id", payment_id).eq("clinic_id", clinic_id).execute()

        # Confirm appointment
        if appointment_id:
            appt_result = (
                self.db.table("appointments")
                .select("*, slots(*)")
                .eq("id", appointment_id)
                .eq("clinic_id", clinic_id)
                .execute()
            )

            if appt_result.data:
                appointment = appt_result.data[0]

                self.db.table("appointments").update({
                    "status": "confirmed",
                    "confirmed_at": now,
                }).eq("id", appointment_id).eq("clinic_id", clinic_id).execute()

                # Mark slot as booked
                slot_id = appointment.get("slot_id")
                if slot_id:
                    self.db.table("slots").update({
                        "status": "booked",
                    }).eq("id", slot_id).eq("clinic_id", clinic_id).execute()

                # Schedule reminder
                self._schedule_reminder(clinic_id, appointment)

                # Send confirmation message to patient
                await self._send_confirmation_message(payment, appointment, clinic_id)

        logger.info(
            "payment_confirmed",
            clinic_id=clinic_id,
            payment_id=payment_id,
            appointment_id=appointment_id,
        )
        return {"status": "ok", "message": "Payment confirmed"}

    async def _fail_payment(
        self, payment: dict, clinic_id: str, reason: str = ""
    ) -> dict:
        """Fail a payment and rollback the booking.

        Releases the slot lock and cancels the appointment.

        Args:
            payment: The payment record dict.
            clinic_id: The clinic UUID.
            reason: Failure reason string.

        Returns:
            A dict with failure result.
        """
        payment_id = payment["id"]
        appointment_id = payment.get("appointment_id")

        # Update payment status
        self.db.table("payments").update({
            "status": "failed",
            "failure_reason": reason,
        }).eq("id", payment_id).eq("clinic_id", clinic_id).execute()

        # Cancel appointment and release slot
        if appointment_id:
            appt_result = (
                self.db.table("appointments")
                .select("slot_id")
                .eq("id", appointment_id)
                .eq("clinic_id", clinic_id)
                .execute()
            )

            if appt_result.data:
                slot_id = appt_result.data[0].get("slot_id")

                self.db.table("appointments").update({
                    "status": "cancelled",
                }).eq("id", appointment_id).eq("clinic_id", clinic_id).execute()

                if slot_id:
                    self.db.table("slots").update({
                        "status": "available",
                        "locked_until": None,
                        "locked_by_session": None,
                    }).eq("id", slot_id).eq("clinic_id", clinic_id).execute()

        # Notify patient
        msisdn = payment.get("customer_msisdn", "")
        if msisdn:
            whatsapp_to = f"whatsapp:+{msisdn}" if not msisdn.startswith("whatsapp:") else msisdn
            await send_whatsapp_message(
                to=whatsapp_to,
                body=templates.payment_failed_message(reason),
                clinic_id=clinic_id,
            )

        logger.info(
            "payment_failed",
            clinic_id=clinic_id,
            payment_id=payment_id,
            reason=reason,
        )
        return {"status": "ok", "message": "Payment failed, booking cancelled"}

    async def expire_stale_payments(self) -> int:
        """Expire payments that have been pending for more than 10 minutes.

        Called by the cron job. Finds pending/processing payments older than
        PAYMENT_EXPIRY_MINUTES, marks them expired, releases slots,
        cancels appointments, and notifies patients.

        Returns:
            Number of payments expired.
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=PAYMENT_EXPIRY_MINUTES)).isoformat()

        # Find stale payments
        result = (
            self.db.table("payments")
            .select("*")
            .in_("status", ["pending", "processing"])
            .lt("initiated_at", cutoff)
            .execute()
        )

        expired_count = 0
        for payment in (result.data or []):
            try:
                clinic_id = payment["clinic_id"]

                # Mark payment expired
                self.db.table("payments").update({
                    "status": "expired",
                    "failure_reason": "Payment window expired",
                }).eq("id", payment["id"]).eq("clinic_id", clinic_id).execute()

                # Cancel appointment and release slot
                appointment_id = payment.get("appointment_id")
                if appointment_id:
                    appt_result = (
                        self.db.table("appointments")
                        .select("slot_id")
                        .eq("id", appointment_id)
                        .eq("clinic_id", clinic_id)
                        .execute()
                    )
                    if appt_result.data:
                        slot_id = appt_result.data[0].get("slot_id")
                        self.db.table("appointments").update({
                            "status": "cancelled",
                        }).eq("id", appointment_id).eq("clinic_id", clinic_id).execute()

                        if slot_id:
                            self.db.table("slots").update({
                                "status": "available",
                                "locked_until": None,
                                "locked_by_session": None,
                            }).eq("id", slot_id).eq("clinic_id", clinic_id).execute()

                # Notify patient
                msisdn = payment.get("customer_msisdn", "")
                if msisdn:
                    whatsapp_to = f"whatsapp:+{msisdn}" if not msisdn.startswith("whatsapp:") else msisdn
                    await send_whatsapp_message(
                        to=whatsapp_to,
                        body=templates.payment_expired_message(),
                        clinic_id=clinic_id,
                    )

                expired_count += 1

            except Exception as exc:
                logger.error(
                    "payment_expiry_error",
                    payment_id=payment["id"],
                    error=str(exc),
                )

        if expired_count > 0:
            logger.info("payments_expired", count=expired_count)
        return expired_count

    async def _send_confirmation_message(
        self, payment: dict, appointment: dict, clinic_id: str
    ) -> None:
        """Send booking confirmation message to the patient.

        Args:
            payment: The payment record.
            appointment: The appointment record.
            clinic_id: The clinic UUID.
        """
        msisdn = payment.get("customer_msisdn", "")
        if not msisdn:
            return

        # Get patient name
        patient_name = None
        patient_id = appointment.get("patient_id")
        if patient_id:
            patient_result = (
                self.db.table("patients")
                .select("name")
                .eq("id", patient_id)
                .eq("clinic_id", clinic_id)
                .execute()
            )
            if patient_result.data:
                patient_name = patient_result.data[0].get("name")

        # Get clinic name
        clinic_result = (
            self.db.table("clinics")
            .select("name")
            .eq("id", clinic_id)
            .execute()
        )
        clinic_name = clinic_result.data[0]["name"] if clinic_result.data else "Medical Centre"

        # Get service name
        service_name = "Consultation"
        service_id = appointment.get("service_id")
        if service_id:
            svc_result = (
                self.db.table("services")
                .select("name")
                .eq("id", service_id)
                .eq("clinic_id", clinic_id)
                .execute()
            )
            if svc_result.data:
                service_name = svc_result.data[0]["name"]

        # Get practitioner name
        practitioner_name = None
        practitioner_id = appointment.get("practitioner_id")
        if practitioner_id:
            prac_result = (
                self.db.table("practitioners")
                .select("name")
                .eq("id", practitioner_id)
                .eq("clinic_id", clinic_id)
                .execute()
            )
            if prac_result.data:
                practitioner_name = prac_result.data[0]["name"]

        # Get slot details
        slot_date = ""
        start_time = ""
        slot_id = appointment.get("slot_id")
        if slot_id:
            slot_result = (
                self.db.table("slots")
                .select("slot_date, start_time")
                .eq("id", slot_id)
                .eq("clinic_id", clinic_id)
                .execute()
            )
            if slot_result.data:
                slot_date = slot_result.data[0].get("slot_date", "")
                start_time = slot_result.data[0].get("start_time", "")

        msg = templates.payment_confirmed_message(
            patient_name=patient_name,
            booking_reference=appointment.get("booking_reference", ""),
            service_name=service_name,
            practitioner_name=practitioner_name,
            slot_date=slot_date,
            start_time=start_time,
            clinic_name=clinic_name,
        )

        whatsapp_to = f"whatsapp:+{msisdn}" if not msisdn.startswith("whatsapp:") else msisdn
        await send_whatsapp_message(
            to=whatsapp_to,
            body=msg,
            clinic_id=clinic_id,
        )

    def _schedule_reminder(self, clinic_id: str, appointment: dict) -> None:
        """Schedule a 24-hour reminder for an appointment.

        Args:
            clinic_id: The clinic UUID.
            appointment: The appointment record.
        """
        try:
            slot_id = appointment.get("slot_id")
            if not slot_id:
                return

            slot_result = (
                self.db.table("slots")
                .select("slot_date, start_time")
                .eq("id", slot_id)
                .eq("clinic_id", clinic_id)
                .execute()
            )

            if not slot_result.data:
                return

            slot = slot_result.data[0]
            slot_date = slot.get("slot_date", "")
            slot_start = slot.get("start_time", "")

            if slot_date and slot_start:
                appt_dt = datetime.fromisoformat(f"{slot_date}T{slot_start}")
                reminder_dt = appt_dt - timedelta(hours=24)
                if reminder_dt > datetime.now(timezone.utc):
                    self.db.table("reminders").insert({
                        "appointment_id": appointment["id"],
                        "clinic_id": clinic_id,
                        "scheduled_for": reminder_dt.isoformat(),
                        "status": "pending",
                    }).execute()
                    logger.info(
                        "reminder_scheduled",
                        clinic_id=clinic_id,
                        appointment_id=appointment["id"],
                        scheduled_for=reminder_dt.isoformat(),
                    )
        except Exception as exc:
            logger.error(
                "reminder_scheduling_failed",
                clinic_id=clinic_id,
                appointment_id=appointment.get("id"),
                error=str(exc),
            )
