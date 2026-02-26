"""Bookings business logic service.

Handles slot management, appointment queries, and booking operations.
Business logic lives here — route handlers call this service.
"""

from datetime import date

from app.core.logging import get_logger
from app.modules.bookings.repository import BookingRepository
from app.modules.bookings.schemas import SlotCreate, SlotBulkCreate

logger = get_logger(__name__)


class BookingService:
    """Business logic for booking and slot operations.

    Coordinates between route handlers and the repository layer.
    """

    def __init__(self):
        """Initialize with a BookingRepository instance."""
        self.repo = BookingRepository()

    def list_available_slots(
        self,
        clinic_id: str,
        from_date: date | None = None,
        to_date: date | None = None,
        service_id: str | None = None,
    ) -> list[dict]:
        """List available slots for a clinic.

        Args:
            clinic_id: The clinic UUID.
            from_date: Optional start date filter.
            to_date: Optional end date filter.
            service_id: Optional service ID filter.

        Returns:
            List of available slot records.
        """
        return self.repo.get_available_slots(
            clinic_id=clinic_id,
            from_date=from_date,
            to_date=to_date,
            service_id=service_id,
        )

    def create_slot(self, clinic_id: str, data: SlotCreate) -> dict:
        """Create a single time slot.

        Args:
            clinic_id: The clinic UUID.
            data: Validated slot creation data.

        Returns:
            The created slot record.
        """
        slot_dict = {
            "slot_date": data.slot_date.isoformat(),
            "start_time": data.start_time.isoformat(),
            "end_time": data.end_time.isoformat(),
            "practitioner_id": data.practitioner_id,
            "service_id": data.service_id,
        }
        return self.repo.create_slot(clinic_id, slot_dict)

    def create_slots_bulk(self, clinic_id: str, data: SlotBulkCreate) -> list[dict]:
        """Create multiple time slots in bulk.

        Args:
            clinic_id: The clinic UUID.
            data: Validated bulk slot creation data.

        Returns:
            List of created slot records.
        """
        slots = []
        for slot_time in data.slots:
            slots.append({
                "slot_date": data.slot_date.isoformat(),
                "start_time": slot_time.get("start_time", ""),
                "end_time": slot_time.get("end_time", ""),
                "practitioner_id": data.practitioner_id,
                "service_id": data.service_id,
            })
        return self.repo.create_slots_bulk(clinic_id, slots)

    def list_appointments(
        self,
        clinic_id: str,
        status: str | None = None,
    ) -> list[dict]:
        """List appointments for a clinic.

        Args:
            clinic_id: The clinic UUID.
            status: Optional status filter.

        Returns:
            List of appointment records.
        """
        return self.repo.get_appointments(clinic_id, status=status)

    def get_appointment_by_reference(
        self, clinic_id: str, booking_ref: str
    ) -> dict | None:
        """Get an appointment by its booking reference.

        Args:
            clinic_id: The clinic UUID.
            booking_ref: The booking reference string.

        Returns:
            The appointment record or None.
        """
        return self.repo.get_appointment_by_reference(clinic_id, booking_ref)

    def release_expired_locks(self) -> int:
        """Release all expired slot locks.

        Called by the cron job.

        Returns:
            Number of slots released.
        """
        return self.repo.release_expired_locks()
