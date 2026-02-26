"""Custom exception hierarchy for MediBook.

All application-specific exceptions inherit from MediBookException.
Each exception carries a human-readable message and optional context dict
for structured logging.
"""


class MediBookException(Exception):
    """Base exception for all MediBook errors.

    Args:
        message: Human-readable error description.
        context: Optional dict of contextual data for logging.
    """

    def __init__(self, message: str = "An unexpected error occurred", context: dict | None = None):
        self.message = message
        self.context = context or {}
        super().__init__(self.message)


class ClinicNotFoundError(MediBookException):
    """Raised when a clinic cannot be resolved by WhatsApp number or ID."""

    def __init__(self, message: str = "Clinic not found", context: dict | None = None):
        super().__init__(message, context)


class SlotNotAvailableError(MediBookException):
    """Raised when the requested slot is no longer available."""

    def __init__(self, message: str = "Slot is not available", context: dict | None = None):
        super().__init__(message, context)


class SlotAlreadyLockedError(MediBookException):
    """Raised when attempting to lock a slot that is already locked."""

    def __init__(self, message: str = "Slot is already locked", context: dict | None = None):
        super().__init__(message, context)


class PaymentInitiationError(MediBookException):
    """Raised when EcoCash payment initiation fails."""

    def __init__(self, message: str = "Payment initiation failed", context: dict | None = None):
        super().__init__(message, context)


class PaymentExpiredError(MediBookException):
    """Raised when a payment window has expired."""

    def __init__(self, message: str = "Payment has expired", context: dict | None = None):
        super().__init__(message, context)


class InvalidTwilioSignatureError(MediBookException):
    """Raised when Twilio HMAC signature validation fails."""

    def __init__(self, message: str = "Invalid Twilio signature", context: dict | None = None):
        super().__init__(message, context)


class SessionExpiredError(MediBookException):
    """Raised when a conversation session has expired."""

    def __init__(self, message: str = "Session has expired", context: dict | None = None):
        super().__init__(message, context)


class ServiceNotFoundError(MediBookException):
    """Raised when a requested clinic service does not exist."""

    def __init__(self, message: str = "Service not found", context: dict | None = None):
        super().__init__(message, context)


class PatientDataError(MediBookException):
    """Raised when patient data is invalid or cannot be processed."""

    def __init__(self, message: str = "Patient data error", context: dict | None = None):
        super().__init__(message, context)


class CronAuthError(MediBookException):
    """Raised when a cron job request fails authentication."""

    def __init__(self, message: str = "Cron authentication failed", context: dict | None = None):
        super().__init__(message, context)


class RateLimitExceededError(MediBookException):
    """Raised when a patient exceeds the message rate limit."""

    def __init__(self, message: str = "Rate limit exceeded", context: dict | None = None):
        super().__init__(message, context)
