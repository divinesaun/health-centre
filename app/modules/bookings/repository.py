"""Bookings repository layer.

All database queries for slots and appointments are centralized here.
Every query enforces clinic_id isolation in the WHERE clause.
"""

from datetime import date, datetime, timedelta, timezone

from app.core.exceptions import SlotAlreadyLockedError, SlotNotAvailableError
from app.core.logging import get_logger
from app.db.client import get_supabase_client

logger = get_logger(__name__)


class BookingRepository:
    """Repository for slot and appointment database operations.

    Enforces clinic_id isolation on every query.
    """

    def __init__(self):
        """Initialize with the Supabase client."""
        self.db = get_supabase_client()

    def get_available_slots(
        self,
        clinic_id: str,
        from_date: date | None = None,
        to_date: date | None = None,
        service_id: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Retrieve available slots for a clinic within a date range.

        Args:
            clinic_id: The clinic UUID.
            from_date: Start date filter (default today).
            to_date: End date filter (default 7 days from now).
            service_id: Optional service ID filter.
            limit: Max number of slots to return.

        Returns:
            List of available slot records.
        """
        start = from_date or date.today()
        end = to_date or (date.today() + timedelta(days=7))

        query = (
            self.db.table("slots")
            .select("*")
            .eq("clinic_id", clinic_id)
            .eq("status", "available")
            .gte("slot_date", start.isoformat())
            .lte("slot_date", end.isoformat())
            .order("slot_date")
            .order("start_time")
            .limit(limit)
        )

        if service_id:
            query = query.eq("service_id", service_id)

        result = query.execute()
        return result.data or []

    def lock_slot(self, clinic_id: str, slot_id: str, session_id: str) -> bool:
        """Atomically lock a slot for booking.

        Only succeeds if the slot is currently 'available'. Sets a 10-minute
        lock expiry. Returns True on success, False if the slot was already taken.

        Args:
            clinic_id: The clinic UUID.
            slot_id: The slot UUID.
            session_id: The conversation session ID locking the slot.

        Returns:
            True if the lock was acquired, False otherwise.
        """
        lock_until = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()

        result = (
            self.db.table("slots")
            .update({
                "status": "locked",
                "locked_until": lock_until,
                "locked_by_session": session_id,
            })
            .eq("id", slot_id)
            .eq("status", "available")
            .eq("clinic_id", clinic_id)
            .execute()
        )

        success = bool(result.data)
        if success:
            logger.info("slot_locked", clinic_id=clinic_id, slot_id=slot_id)
        else:
            logger.info("slot_lock_failed", clinic_id=clinic_id, slot_id=slot_id)
        return success

    def release_slot(self, clinic_id: str, slot_id: str) -> None:
        """Release a locked slot back to available status.

        Args:
            clinic_id: The clinic UUID.
            slot_id: The slot UUID.
        """
        self.db.table("slots").update({
            "status": "available",
            "locked_until": None,
            "locked_by_session": None,
        }).eq("id", slot_id).eq("clinic_id", clinic_id).execute()

        logger.info("slot_released", clinic_id=clinic_id, slot_id=slot_id)

    def confirm_slot(self, clinic_id: str, slot_id: str) -> None:
        """Mark a slot as booked after payment confirmation.

        Args:
            clinic_id: The clinic UUID.
            slot_id: The slot UUID.
        """
        self.db.table("slots").update({
            "status": "booked",
        }).eq("id", slot_id).eq("clinic_id", clinic_id).execute()

    def release_expired_locks(self) -> int:
        """Release all slots with expired locks.

        Called by the cron job. Updates locked slots where locked_until < NOW().

        Returns:
            Number of slots released.
        """
        now = datetime.now(timezone.utc).isoformat()
        result = (
            self.db.table("slots")
            .update({
                "status": "available",
                "locked_until": None,
                "locked_by_session": None,
            })
            .eq("status", "locked")
            .lt("locked_until", now)
            .execute()
        )
        count = len(result.data) if result.data else 0
        if count > 0:
            logger.info("expired_locks_released", count=count)
        return count

    def create_slot(self, clinic_id: str, data: dict) -> dict:
        """Create a new time slot for a clinic.

        Args:
            clinic_id: The clinic UUID.
            data: Slot data dict.

        Returns:
            The created slot record.
        """
        data["clinic_id"] = clinic_id
        result = self.db.table("slots").insert(data).execute()
        if result.data:
            return result.data[0]
        raise RuntimeError("Failed to create slot")

    def create_slots_bulk(self, clinic_id: str, slots: list[dict]) -> list[dict]:
        """Create multiple time slots in bulk for a clinic.

        Args:
            clinic_id: The clinic UUID.
            slots: List of slot data dicts.

        Returns:
            List of created slot records.
        """
        for slot in slots:
            slot["clinic_id"] = clinic_id
        result = self.db.table("slots").insert(slots).execute()
        return result.data or []

    def get_appointments(
        self,
        clinic_id: str,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Retrieve appointments for a clinic.

        Args:
            clinic_id: The clinic UUID.
            status: Optional status filter.
            limit: Max number of appointments to return.

        Returns:
            List of appointment records.
        """
        query = (
            self.db.table("appointments")
            .select("*")
            .eq("clinic_id", clinic_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        if status:
            query = query.eq("status", status)
        result = query.execute()
        return result.data or []

    def get_appointment_by_reference(self, clinic_id: str, booking_ref: str) -> dict | None:
        """Retrieve an appointment by its booking reference.

        Args:
            clinic_id: The clinic UUID.
            booking_ref: The booking reference string.

        Returns:
            The appointment record or None if not found.
        """
        result = (
            self.db.table("appointments")
            .select("*")
            .eq("clinic_id", clinic_id)
            .eq("booking_reference", booking_ref)
            .execute()
        )
        return result.data[0] if result.data else None
