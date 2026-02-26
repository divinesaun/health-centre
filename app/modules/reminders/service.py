"""Reminders business logic service.

Handles sending appointment reminders 24 hours before appointments.
Called by the cron job every 5 minutes.
"""

from datetime import datetime, timedelta, timezone

from app.core.logging import get_logger
from app.core.twilio_client import send_whatsapp_message
from app.db.client import get_supabase_client
from app.modules.flow import templates

logger = get_logger(__name__)


class ReminderService:
    """Business logic for appointment reminder operations.

    Queries pending reminders due within the next 5 minutes,
    sends WhatsApp messages, and updates reminder status.
    """

    def __init__(self):
        """Initialize with a Supabase client."""
        self.db = get_supabase_client()

    async def send_due_reminders(self) -> int:
        """Send all reminders that are due now.

        Finds pending reminders where scheduled_for <= NOW(),
        sends the WhatsApp reminder message, and marks them as sent.

        Returns:
            Number of reminders sent.
        """
        now = datetime.now(timezone.utc).isoformat()

        # Find due reminders
        result = (
            self.db.table("reminders")
            .select("*")
            .eq("status", "pending")
            .lte("scheduled_for", now)
            .execute()
        )

        sent_count = 0
        for reminder in (result.data or []):
            try:
                await self._send_single_reminder(reminder)
                sent_count += 1
            except Exception as exc:
                logger.error(
                    "reminder_send_failed",
                    reminder_id=reminder["id"],
                    clinic_id=reminder.get("clinic_id"),
                    error=str(exc),
                )
                # Mark as failed
                self.db.table("reminders").update({
                    "status": "failed",
                }).eq("id", reminder["id"]).eq(
                    "clinic_id", reminder["clinic_id"]
                ).execute()

        if sent_count > 0:
            logger.info("reminders_sent", count=sent_count)
        return sent_count

    async def _send_single_reminder(self, reminder: dict) -> None:
        """Send a single appointment reminder.

        Looks up the appointment, patient, slot, service, and clinic details
        to compose and send the reminder message.

        Args:
            reminder: The reminder record dict.

        Raises:
            Exception: If any step fails during message composition or sending.
        """
        clinic_id = reminder["clinic_id"]
        appointment_id = reminder["appointment_id"]

        # Get appointment
        appt_result = (
            self.db.table("appointments")
            .select("*")
            .eq("id", appointment_id)
            .eq("clinic_id", clinic_id)
            .execute()
        )
        if not appt_result.data:
            logger.warning(
                "reminder_appointment_not_found",
                reminder_id=reminder["id"],
                appointment_id=appointment_id,
            )
            return

        appointment = appt_result.data[0]

        # Skip if appointment is cancelled
        if appointment["status"] in ("cancelled", "no_show"):
            self.db.table("reminders").update({
                "status": "sent",
                "sent_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", reminder["id"]).eq("clinic_id", clinic_id).execute()
            return

        # Get patient
        patient_name = None
        patient_whatsapp = None
        patient_id = appointment.get("patient_id")
        if patient_id:
            patient_result = (
                self.db.table("patients")
                .select("name, whatsapp_number")
                .eq("id", patient_id)
                .eq("clinic_id", clinic_id)
                .execute()
            )
            if patient_result.data:
                patient_name = patient_result.data[0].get("name")
                patient_whatsapp = patient_result.data[0].get("whatsapp_number")

        if not patient_whatsapp:
            logger.warning(
                "reminder_no_patient_whatsapp",
                reminder_id=reminder["id"],
                appointment_id=appointment_id,
            )
            return

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

        # Get clinic name
        clinic_result = (
            self.db.table("clinics")
            .select("name")
            .eq("id", clinic_id)
            .execute()
        )
        clinic_name = clinic_result.data[0]["name"] if clinic_result.data else "Medical Centre"

        # Compose and send reminder
        msg = templates.reminder_message(
            patient_name=patient_name,
            booking_reference=appointment.get("booking_reference", ""),
            service_name=service_name,
            slot_date=slot_date,
            start_time=start_time,
            clinic_name=clinic_name,
        )

        whatsapp_to = f"whatsapp:+{patient_whatsapp}" if not patient_whatsapp.startswith("+") else f"whatsapp:{patient_whatsapp}"

        sid = await send_whatsapp_message(
            to=whatsapp_to,
            body=msg,
            clinic_id=clinic_id,
        )

        # Mark reminder as sent
        now = datetime.now(timezone.utc).isoformat()
        status = "sent" if sid else "failed"
        self.db.table("reminders").update({
            "status": status,
            "sent_at": now,
        }).eq("id", reminder["id"]).eq("clinic_id", clinic_id).execute()

        logger.info(
            "reminder_sent",
            clinic_id=clinic_id,
            appointment_id=appointment_id,
            patient_whatsapp=patient_whatsapp,
            status=status,
        )
