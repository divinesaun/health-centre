"""Patients repository layer.

All database queries for patients are centralized here.
Every query enforces clinic_id isolation in the WHERE clause.
"""

from app.core.logging import get_logger
from app.db.client import get_supabase_client

logger = get_logger(__name__)


class PatientRepository:
    """Repository for patient database operations.

    Enforces clinic_id isolation on every query.
    """

    def __init__(self):
        """Initialize with the Supabase client."""
        self.db = get_supabase_client()

    def get_or_create(
        self, clinic_id: str, whatsapp_number: str, name: str | None = None
    ) -> dict:
        """Get an existing patient or create a new one.

        Performs an upsert based on (clinic_id, whatsapp_number) unique constraint.

        Args:
            clinic_id: The clinic UUID.
            whatsapp_number: Patient WhatsApp number (without prefix).
            name: Optional patient name.

        Returns:
            The patient record dict.
        """
        clean_number = whatsapp_number.replace("whatsapp:", "").replace("+", "")

        # Try to find existing patient
        result = (
            self.db.table("patients")
            .select("*")
            .eq("clinic_id", clinic_id)
            .eq("whatsapp_number", clean_number)
            .execute()
        )

        if result.data:
            patient = result.data[0]
            # Update name if we have one and patient doesn't
            if name and not patient.get("name"):
                self.db.table("patients").update({"name": name}).eq(
                    "id", patient["id"]
                ).eq("clinic_id", clinic_id).execute()
                patient["name"] = name
            return patient

        # Create new patient
        insert_result = (
            self.db.table("patients")
            .insert({
                "clinic_id": clinic_id,
                "whatsapp_number": clean_number,
                "name": name,
            })
            .execute()
        )

        if insert_result.data:
            logger.info("patient_created", clinic_id=clinic_id)
            return insert_result.data[0]

        raise RuntimeError("Failed to create patient record")

    def get_by_id(self, clinic_id: str, patient_id: str) -> dict | None:
        """Retrieve a patient by ID within a clinic.

        Args:
            clinic_id: The clinic UUID.
            patient_id: The patient UUID.

        Returns:
            The patient record or None if not found.
        """
        result = (
            self.db.table("patients")
            .select("*")
            .eq("id", patient_id)
            .eq("clinic_id", clinic_id)
            .execute()
        )
        return result.data[0] if result.data else None

    def get_by_whatsapp(self, clinic_id: str, whatsapp_number: str) -> dict | None:
        """Retrieve a patient by WhatsApp number within a clinic.

        Args:
            clinic_id: The clinic UUID.
            whatsapp_number: Patient WhatsApp number.

        Returns:
            The patient record or None if not found.
        """
        clean = whatsapp_number.replace("whatsapp:", "").replace("+", "")
        result = (
            self.db.table("patients")
            .select("*")
            .eq("clinic_id", clinic_id)
            .eq("whatsapp_number", clean)
            .execute()
        )
        return result.data[0] if result.data else None

    def list_patients(self, clinic_id: str, limit: int = 50) -> list[dict]:
        """List all patients for a clinic.

        Args:
            clinic_id: The clinic UUID.
            limit: Max number of patients to return.

        Returns:
            List of patient records.
        """
        result = (
            self.db.table("patients")
            .select("id, clinic_id, whatsapp_number, name, created_at")
            .eq("clinic_id", clinic_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
