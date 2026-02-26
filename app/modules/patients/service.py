"""Patients business logic service.

Handles patient lookup and creation operations.
Business logic lives here — route handlers and flow handlers call this service.
"""

from app.core.logging import get_logger
from app.modules.patients.repository import PatientRepository

logger = get_logger(__name__)


class PatientService:
    """Business logic for patient operations.

    Coordinates between handlers and the repository layer.
    """

    def __init__(self):
        """Initialize with a PatientRepository instance."""
        self.repo = PatientRepository()

    def get_or_create_patient(
        self, clinic_id: str, whatsapp_number: str, name: str | None = None
    ) -> dict:
        """Get or create a patient record.

        Args:
            clinic_id: The clinic UUID.
            whatsapp_number: Patient WhatsApp number.
            name: Optional patient name from WhatsApp profile.

        Returns:
            The patient record dict.
        """
        return self.repo.get_or_create(clinic_id, whatsapp_number, name)

    def get_patient(self, clinic_id: str, patient_id: str) -> dict | None:
        """Get a patient by ID.

        Args:
            clinic_id: The clinic UUID.
            patient_id: The patient UUID.

        Returns:
            The patient record or None.
        """
        return self.repo.get_by_id(clinic_id, patient_id)

    def list_patients(self, clinic_id: str) -> list[dict]:
        """List all patients for a clinic.

        Args:
            clinic_id: The clinic UUID.

        Returns:
            List of patient records.
        """
        return self.repo.list_patients(clinic_id)
