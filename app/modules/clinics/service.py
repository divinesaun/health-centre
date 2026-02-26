"""Clinics business logic service.

Handles clinic and service CRUD operations. Business logic lives here,
not in route handlers. The service calls the repository for DB access.
"""

from app.core.logging import get_logger
from app.modules.clinics.repository import ClinicRepository
from app.modules.clinics.schemas import ClinicCreate, ClinicUpdate, ServiceCreate

logger = get_logger(__name__)


class ClinicService:
    """Business logic for clinic management operations.

    Coordinates between route handlers and the repository layer.
    """

    def __init__(self):
        """Initialize with a ClinicRepository instance."""
        self.repo = ClinicRepository()

    def list_clinics(self, active_only: bool = True) -> list[dict]:
        """List all clinics.

        Args:
            active_only: If True, only return active clinics.

        Returns:
            List of clinic records.
        """
        return self.repo.get_all(active_only=active_only)

    def get_clinic(self, clinic_id: str) -> dict:
        """Get a single clinic by ID.

        Args:
            clinic_id: The clinic UUID.

        Returns:
            The clinic record.

        Raises:
            ClinicNotFoundError: If the clinic does not exist.
        """
        return self.repo.get_by_id(clinic_id)

    def create_clinic(self, data: ClinicCreate) -> dict:
        """Create a new clinic.

        Args:
            data: Validated clinic creation data.

        Returns:
            The created clinic record.
        """
        clinic_dict = data.model_dump(exclude_none=True)
        result = self.repo.create(clinic_dict)
        logger.info("clinic_created_via_service", clinic_id=result["id"])
        return result

    def update_clinic(self, clinic_id: str, data: ClinicUpdate) -> dict:
        """Update an existing clinic.

        Args:
            clinic_id: The clinic UUID.
            data: Validated clinic update data.

        Returns:
            The updated clinic record.

        Raises:
            ClinicNotFoundError: If the clinic does not exist.
        """
        update_dict = data.model_dump(exclude_none=True)
        if not update_dict:
            return self.repo.get_by_id(clinic_id)
        return self.repo.update(clinic_id, update_dict)

    def list_services(self, clinic_id: str, active_only: bool = True) -> list[dict]:
        """List all services for a clinic.

        Args:
            clinic_id: The clinic UUID.
            active_only: If True, only return active services.

        Returns:
            List of service records.
        """
        # Verify clinic exists first
        self.repo.get_by_id(clinic_id)
        return self.repo.get_services(clinic_id, active_only=active_only)

    def create_service(self, clinic_id: str, data: ServiceCreate) -> dict:
        """Create a new service for a clinic.

        Args:
            clinic_id: The clinic UUID.
            data: Validated service creation data.

        Returns:
            The created service record.
        """
        # Verify clinic exists first
        self.repo.get_by_id(clinic_id)
        service_dict = data.model_dump(exclude_none=True)
        return self.repo.create_service(clinic_id, service_dict)
