"""Clinics repository layer.

All database queries for clinics are centralized here. Every query
on a clinic-scoped table includes clinic_id in the WHERE clause.
"""

from datetime import datetime, timezone

from app.core.exceptions import ClinicNotFoundError
from app.core.logging import get_logger
from app.db.client import get_supabase_client

logger = get_logger(__name__)


class ClinicRepository:
    """Repository for clinic CRUD operations.

    Enforces clinic_id isolation on all queries.
    """

    def __init__(self):
        """Initialize with the Supabase client."""
        self.db = get_supabase_client()

    def get_all(self, active_only: bool = True) -> list[dict]:
        """Retrieve all clinics, optionally filtered by active status.

        Args:
            active_only: If True, only return active clinics.

        Returns:
            List of clinic records.
        """
        query = self.db.table("clinics").select(
            "id, name, whatsapp_number, timezone, is_active, "
            "subscription_tier, greeting_message, created_at, updated_at"
        )
        if active_only:
            query = query.eq("is_active", True)
        result = query.order("name").execute()
        return result.data or []

    def get_by_id(self, clinic_id: str) -> dict:
        """Retrieve a clinic by its UUID.

        Args:
            clinic_id: The clinic UUID.

        Returns:
            The clinic record dict.

        Raises:
            ClinicNotFoundError: If no clinic is found with the given ID.
        """
        result = (
            self.db.table("clinics")
            .select("*")
            .eq("id", clinic_id)
            .execute()
        )
        if not result.data:
            raise ClinicNotFoundError(
                message=f"Clinic {clinic_id} not found",
                context={"clinic_id": clinic_id},
            )
        return result.data[0]

    def get_by_whatsapp(self, whatsapp_number: str) -> dict:
        """Retrieve a clinic by its WhatsApp number.

        Args:
            whatsapp_number: The clinic's WhatsApp number (without prefix).

        Returns:
            The clinic record dict.

        Raises:
            ClinicNotFoundError: If no clinic matches the number.
        """
        clean = whatsapp_number.replace("whatsapp:", "").replace("+", "")
        result = (
            self.db.table("clinics")
            .select("*")
            .eq("whatsapp_number", clean)
            .eq("is_active", True)
            .execute()
        )
        if not result.data:
            raise ClinicNotFoundError(
                message=f"No active clinic found for {clean}",
                context={"whatsapp_number": clean},
            )
        return result.data[0]

    def create(self, data: dict) -> dict:
        """Create a new clinic.

        Args:
            data: Dict of clinic fields to insert.

        Returns:
            The created clinic record.
        """
        result = self.db.table("clinics").insert(data).execute()
        if result.data:
            logger.info("clinic_created", clinic_id=result.data[0]["id"], name=data.get("name"))
            return result.data[0]
        raise RuntimeError("Failed to create clinic")

    def update(self, clinic_id: str, data: dict) -> dict:
        """Update an existing clinic.

        Args:
            clinic_id: The clinic UUID.
            data: Dict of fields to update.

        Returns:
            The updated clinic record.

        Raises:
            ClinicNotFoundError: If no clinic is found with the given ID.
        """
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        result = (
            self.db.table("clinics")
            .update(data)
            .eq("id", clinic_id)
            .execute()
        )
        if not result.data:
            raise ClinicNotFoundError(
                message=f"Clinic {clinic_id} not found",
                context={"clinic_id": clinic_id},
            )
        logger.info("clinic_updated", clinic_id=clinic_id)
        return result.data[0]

    def get_services(self, clinic_id: str, active_only: bool = True) -> list[dict]:
        """Retrieve all services for a clinic.

        Args:
            clinic_id: The clinic UUID.
            active_only: If True, only return active services.

        Returns:
            List of service records.
        """
        query = (
            self.db.table("services")
            .select("*")
            .eq("clinic_id", clinic_id)
        )
        if active_only:
            query = query.eq("is_active", True)
        result = query.order("display_order").execute()
        return result.data or []

    def create_service(self, clinic_id: str, data: dict) -> dict:
        """Create a new service for a clinic.

        Args:
            clinic_id: The clinic UUID.
            data: Dict of service fields.

        Returns:
            The created service record.
        """
        data["clinic_id"] = clinic_id
        result = self.db.table("services").insert(data).execute()
        if result.data:
            logger.info("service_created", clinic_id=clinic_id, service_id=result.data[0]["id"])
            return result.data[0]
        raise RuntimeError("Failed to create service")
