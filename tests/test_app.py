"""Comprehensive tests for MediBook — Divine Comfort Clinic.

Tests cover:
- App factory and health endpoint
- Config loading
- Exception hierarchy
- Logging and PII redaction
- Template message generation
- Conversation state machine routing
- Schema validation
- Dependency injection
"""

import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import date, time, datetime, timezone, timedelta

# Ensure test env vars are set before importing app modules
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_PUBLISHABLE_KEY", "test-key")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "ACtest")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "test-auth-token")
os.environ.setdefault("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
os.environ.setdefault("ECOCASH_API_KEY", "test-ecocash-key")
os.environ.setdefault("ECOCASH_BASE_URL", "https://test.ecocash.co.zw")
os.environ.setdefault("SECRET_KEY", "test-secret-key-long-enough")
os.environ.setdefault("CRON_SECRET", "test-cron-secret")
os.environ.setdefault("CLINIC_NAME", "Divine Comfort Clinic")
os.environ.setdefault("CLINIC_ADDRESS", "Harare, Zimbabwe")
os.environ.setdefault("CLINIC_WHATSAPP_NUMBER", "+14155238886")


# ── 1. Config Tests ──────────────────────────────────────────────────────────


class TestConfig:
    """Test application configuration loading."""

    def test_settings_loads_defaults(self):
        from app.config import Settings

        s = Settings()
        assert s.CLINIC_NAME == "Divine Comfort Clinic"
        assert s.CLINIC_ADDRESS == "Harare, Zimbabwe"
        assert s.APP_ENV == "development"
        assert s.LOG_LEVEL == "INFO"

    def test_settings_singleton(self):
        from app.config import get_settings

        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2


# ── 2. Exception Hierarchy Tests ─────────────────────────────────────────────


class TestExceptions:
    """Test the custom exception hierarchy."""

    def test_base_exception(self):
        from app.core.exceptions import MediBookException

        exc = MediBookException("test error", {"key": "value"})
        assert exc.message == "test error"
        assert exc.context == {"key": "value"}
        assert str(exc) == "test error"

    def test_clinic_not_found(self):
        from app.core.exceptions import ClinicNotFoundError

        exc = ClinicNotFoundError()
        assert exc.message == "Clinic not found"
        assert isinstance(exc, Exception)

    def test_rate_limit_exceeded(self):
        from app.core.exceptions import RateLimitExceededError

        exc = RateLimitExceededError(
            message="Too fast", context={"patient": "123"}
        )
        assert exc.message == "Too fast"
        assert exc.context["patient"] == "123"

    def test_payment_initiation_error(self):
        from app.core.exceptions import PaymentInitiationError

        exc = PaymentInitiationError(
            message="Payment failed", context={"source_reference": "abc"}
        )
        assert "Payment failed" in str(exc)

    def test_all_exceptions_inherit_from_base(self):
        from app.core.exceptions import (
            MediBookException,
            ClinicNotFoundError,
            SlotNotAvailableError,
            SlotAlreadyLockedError,
            PaymentInitiationError,
            PaymentExpiredError,
            InvalidTwilioSignatureError,
            SessionExpiredError,
            ServiceNotFoundError,
            PatientDataError,
            CronAuthError,
            RateLimitExceededError,
        )

        exceptions = [
            ClinicNotFoundError,
            SlotNotAvailableError,
            SlotAlreadyLockedError,
            PaymentInitiationError,
            PaymentExpiredError,
            InvalidTwilioSignatureError,
            SessionExpiredError,
            ServiceNotFoundError,
            PatientDataError,
            CronAuthError,
            RateLimitExceededError,
        ]
        for exc_class in exceptions:
            assert issubclass(exc_class, MediBookException)


# ── 3. Logging & PII Redaction Tests ─────────────────────────────────────────


class TestLogging:
    """Test structured logging and PII masking."""

    def test_mask_phone_number(self):
        from app.core.logging import _mask_phone_number

        assert _mask_phone_number("+263774222475") == "*********2475"
        assert _mask_phone_number("1234") == "****"  # <= 4 chars returns all asterisks
        assert _mask_phone_number("123") == "****"
        assert _mask_phone_number("263774222475") == "********2475"

    def test_redact_sensitive_fields(self):
        from app.core.logging import _redact_sensitive_fields

        event = {
            "api_key": "secret123",
            "auth_token": "token456",
            "patient_whatsapp": "+263774222475",
            "normal_field": "hello",
        }
        result = _redact_sensitive_fields(None, None, event)
        assert result["api_key"] == "[REDACTED]"
        assert result["auth_token"] == "[REDACTED]"
        assert "2475" in result["patient_whatsapp"]
        assert "*" in result["patient_whatsapp"]
        assert result["normal_field"] == "hello"

    def test_get_logger_returns_bound_logger(self):
        from app.core.logging import get_logger

        logger = get_logger("test")
        assert logger is not None


# ── 4. Template Tests ────────────────────────────────────────────────────────


class TestTemplates:
    """Test WhatsApp message template generation."""

    def test_greeting_message_with_name(self):
        from app.modules.flow.templates import greeting_message

        msg = greeting_message("Divine Comfort Clinic", "John")
        assert "Divine Comfort Clinic" in msg
        assert "John" in msg
        assert "1️⃣" in msg
        assert "2️⃣" in msg
        assert "3️⃣" in msg

    def test_greeting_message_without_name(self):
        from app.modules.flow.templates import greeting_message

        msg = greeting_message("Divine Comfort Clinic")
        assert "Divine Comfort Clinic" in msg
        assert "Hi," in msg

    def test_service_list_message(self):
        from app.modules.flow.templates import service_list_message

        services = [
            {"name": "General Consultation", "booking_fee_usd": 3.00},
            {"name": "Eye Test", "booking_fee_usd": 5.00},
        ]
        msg = service_list_message("Divine Comfort Clinic", services)
        assert "General Consultation" in msg
        assert "$3.00" in msg
        assert "Eye Test" in msg
        assert "$5.00" in msg

    def test_slot_list_message(self):
        from app.modules.flow.templates import slot_list_message

        slots = [
            {"slot_date": "2026-03-01", "start_time": "08:00", "end_time": "08:30"},
            {"slot_date": "2026-03-01", "start_time": "09:00", "end_time": "09:30", "practitioner_name": "Dr. Moyo"},
        ]
        msg = slot_list_message(slots)
        assert "08:00" in msg
        assert "Dr. Moyo" in msg

    def test_booking_summary_message(self):
        from app.modules.flow.templates import booking_summary_message

        msg = booking_summary_message(
            service_name="General Consultation",
            practitioner_name="Dr. Moyo",
            slot_date="2026-03-01",
            start_time="08:00",
            booking_fee=3.00,
        )
        assert "General Consultation" in msg
        assert "Dr. Moyo" in msg
        assert "$3.00" in msg
        assert "YES" in msg

    def test_payment_initiated_message(self):
        from app.modules.flow.templates import payment_initiated_message

        msg = payment_initiated_message(3.00, "USD")
        assert "USD 3.00" in msg
        assert "10 minutes" in msg

    def test_payment_confirmed_message(self):
        from app.modules.flow.templates import payment_confirmed_message

        msg = payment_confirmed_message(
            patient_name="John",
            booking_reference="MED-12345",
            service_name="General Consultation",
            practitioner_name="Dr. Moyo",
            slot_date="2026-03-01",
            start_time="08:00",
            clinic_name="Divine Comfort Clinic",
        )
        assert "MED-12345" in msg
        assert "John" in msg
        assert "Confirmed" in msg

    def test_cancel_message(self):
        from app.modules.flow.templates import cancel_message

        msg = cancel_message()
        assert "cancelled" in msg.lower()

    def test_error_recovery_message(self):
        from app.modules.flow.templates import error_recovery_message

        msg = error_recovery_message()
        assert "wrong" in msg.lower()

    def test_faq_message(self):
        from app.modules.flow.templates import faq_message

        msg = faq_message("Divine Comfort Clinic")
        assert "Divine Comfort Clinic" in msg
        assert "operating hours" in msg.lower()

    def test_rate_limit_message(self):
        from app.modules.flow.templates import rate_limit_message

        msg = rate_limit_message()
        assert "too quickly" in msg.lower()

    def test_no_slots_message(self):
        from app.modules.flow.templates import no_slots_message

        msg = no_slots_message()
        assert "no available slots" in msg.lower()

    def test_payment_expired_message(self):
        from app.modules.flow.templates import payment_expired_message

        msg = payment_expired_message()
        assert "expired" in msg.lower()

    def test_payment_failed_message(self):
        from app.modules.flow.templates import payment_failed_message

        msg = payment_failed_message("Insufficient funds")
        assert "Insufficient funds" in msg

    def test_reminder_message(self):
        from app.modules.flow.templates import reminder_message

        msg = reminder_message(
            patient_name="Jane",
            booking_reference="MED-99999",
            service_name="Dental Check-up",
            slot_date="2026-03-05",
            start_time="14:00",
            clinic_name="Divine Comfort Clinic",
        )
        assert "Jane" in msg
        assert "MED-99999" in msg
        assert "Divine Comfort Clinic" in msg


# ── 5. Conversation State Tests ──────────────────────────────────────────────


class TestConversationStates:
    """Test conversation state enum."""

    def test_all_states_exist(self):
        from app.modules.flow.states import ConversationState

        expected = [
            "IDLE",
            "SELECTING_SERVICE",
            "SELECTING_SLOT",
            "CONFIRMING_DETAILS",
            "AWAITING_PAYMENT",
            "PAYMENT_PROCESSING",
        ]
        for state_name in expected:
            assert hasattr(ConversationState, state_name)
            assert ConversationState[state_name].value == state_name


# ── 6. Schema Validation Tests ───────────────────────────────────────────────


class TestSchemas:
    """Test Pydantic schema validation."""

    def test_slot_create_valid(self):
        from app.modules.bookings.schemas import SlotCreate

        slot = SlotCreate(
            slot_date=date(2026, 3, 1),
            start_time=time(8, 0),
            end_time=time(8, 30),
        )
        assert slot.slot_date == date(2026, 3, 1)

    def test_slot_bulk_create_valid(self):
        from app.modules.bookings.schemas import SlotBulkCreate

        bulk = SlotBulkCreate(
            slot_date=date(2026, 3, 1),
            slots=[{"start_time": "08:00", "end_time": "08:30"}],
        )
        assert len(bulk.slots) == 1

    def test_slot_bulk_create_empty_fails(self):
        from app.modules.bookings.schemas import SlotBulkCreate
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SlotBulkCreate(slot_date=date(2026, 3, 1), slots=[])

    def test_webhook_form_schema(self):
        from app.modules.webhook.schemas import TwilioWebhookForm

        form = TwilioWebhookForm(
            MessageSid="SM123",
            From_="whatsapp:+263774222475",
            To="whatsapp:+14155238886",
            Body="Hello",
            NumMedia="0",
        )
        assert form.From_ == "whatsapp:+263774222475"
        assert form.Body == "Hello"

    def test_ecocash_callback_schema(self):
        from app.modules.payments.schemas import EcoCashCallbackPayload

        payload = EcoCashCallbackPayload(
            sourceReference="abc-123",
            status="COMPLETED",
        )
        assert payload.sourceReference == "abc-123"

    def test_clinic_update_schema(self):
        from app.modules.clinics.schemas import ClinicUpdate

        update = ClinicUpdate(name="Updated Clinic Name")
        dumped = update.model_dump(exclude_none=True)
        assert dumped["name"] == "Updated Clinic Name"
        assert "whatsapp_number" not in dumped


# ── 7. App Factory & Health Endpoint Tests ───────────────────────────────────


class TestAppFactory:
    """Test FastAPI app creation and health endpoint."""

    def test_app_creates_successfully(self):
        """Test that the app factory returns a FastAPI instance."""
        with patch("app.main._ensure_clinic_exists"):
            from app.main import create_app

            application = create_app()
            assert application.title == "MediBook"
            assert application.version == "1.0.0"

    def test_health_endpoint(self):
        """Test the health check endpoint returns correct data."""
        from fastapi.testclient import TestClient

        with patch("app.main._ensure_clinic_exists"):
            from app.main import create_app

            application = create_app()
            client = TestClient(application)
            response = client.get("/")
            assert response.status_code == 200
            data = response.json()
            assert data["app"] == "MediBook"
            assert data["clinic"] == "Divine Comfort Clinic"
            assert data["status"] == "healthy"

    def test_routers_are_registered(self):
        """Test that all module routers are registered."""
        with patch("app.main._ensure_clinic_exists"):
            from app.main import create_app

            application = create_app()
            routes = [r.path for r in application.routes]
            assert "/webhook/twilio" in routes
            assert "/clinic/" in routes
            assert "/clinic/services" in routes
            assert "/bookings/slots" in routes
            assert "/bookings/appointments" in routes
            assert "/payments/ecocash/callback" in routes
            assert "/jobs/send-reminders" in routes
            assert "/jobs/expire-payments" in routes
            assert "/jobs/expire-sessions" in routes


# ── 8. Security Tests ────────────────────────────────────────────────────────


class TestSecurity:
    """Test security utilities."""

    def test_hash_api_key(self):
        from app.core.security import hash_api_key

        h1 = hash_api_key("test-key")
        h2 = hash_api_key("test-key")
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_verify_api_key_correct(self):
        from app.core.security import hash_api_key, verify_api_key

        hashed = hash_api_key("my-secret")
        assert verify_api_key("my-secret", hashed) is True

    def test_verify_api_key_wrong(self):
        from app.core.security import hash_api_key, verify_api_key

        hashed = hash_api_key("my-secret")
        assert verify_api_key("wrong-secret", hashed) is False

    def test_cron_auth_missing_header(self):
        from app.core.security import verify_cron_secret
        from app.core.exceptions import CronAuthError

        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.url.path = "/jobs/test"

        with pytest.raises(CronAuthError):
            verify_cron_secret(mock_request)

    def test_cron_auth_invalid_secret(self):
        from app.core.security import verify_cron_secret
        from app.core.exceptions import CronAuthError

        mock_request = MagicMock()
        mock_request.headers = {"Authorization": "Bearer wrong-secret"}
        mock_request.url.path = "/jobs/test"

        with pytest.raises(CronAuthError):
            verify_cron_secret(mock_request)

    def test_cron_auth_valid_secret(self):
        from app.core.security import verify_cron_secret

        mock_request = MagicMock()
        mock_request.headers = {"Authorization": "Bearer test-cron-secret"}
        mock_request.url.path = "/jobs/test"

        # Should not raise
        verify_cron_secret(mock_request)


# ── 9. Error Handler Tests ───────────────────────────────────────────────────


class TestErrorHandlers:
    """Test that exception handlers return correct HTTP status codes."""

    def test_unhandled_exception_returns_500(self):
        from fastapi.testclient import TestClient

        with patch("app.main._ensure_clinic_exists"):
            from app.main import create_app

            application = create_app()

            @application.get("/test-error")
            async def raise_error():
                raise RuntimeError("Test unhandled error")

            client = TestClient(application, raise_server_exceptions=False)
            response = client.get("/test-error")
            assert response.status_code == 500
            assert response.json()["error"] == "Internal server error"

    def test_rate_limit_returns_429(self):
        from fastapi.testclient import TestClient
        from app.core.exceptions import RateLimitExceededError

        with patch("app.main._ensure_clinic_exists"):
            from app.main import create_app

            application = create_app()

            @application.get("/test-rate-limit")
            async def raise_rate_limit():
                raise RateLimitExceededError(
                    context={"patient_whatsapp": "123"}
                )

            client = TestClient(application, raise_server_exceptions=False)
            response = client.get("/test-rate-limit")
            assert response.status_code == 429

    def test_clinic_not_found_returns_404(self):
        from fastapi.testclient import TestClient
        from app.core.exceptions import ClinicNotFoundError

        with patch("app.main._ensure_clinic_exists"):
            from app.main import create_app

            application = create_app()

            @application.get("/test-clinic-404")
            async def raise_clinic_not_found():
                raise ClinicNotFoundError(
                    context={"whatsapp_number": "123"}
                )

            client = TestClient(application, raise_server_exceptions=False)
            response = client.get("/test-clinic-404")
            assert response.status_code == 404


# ── 10. Flow Engine Unit Tests ───────────────────────────────────────────────


class TestFlowEngineExpiry:
    """Test session expiry logic in the flow engine."""

    def test_is_expired_with_past_date(self):
        from app.modules.flow.engine import FlowEngine

        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        assert FlowEngine._is_expired(past) is True

    def test_is_expired_with_future_date(self):
        from app.modules.flow.engine import FlowEngine

        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        assert FlowEngine._is_expired(future) is False

    def test_is_expired_with_invalid_date(self):
        from app.modules.flow.engine import FlowEngine

        assert FlowEngine._is_expired("not-a-date") is True

    def test_is_expired_with_z_suffix(self):
        from app.modules.flow.engine import FlowEngine

        past = (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        assert FlowEngine._is_expired(past) is True


# ── 11. Booking Reference Generation ─────────────────────────────────────────


class TestBookingReference:
    """Test booking reference generation."""

    def test_format(self):
        from app.modules.flow.handlers.booking import _generate_booking_reference

        ref = _generate_booking_reference()
        assert ref.startswith("MED-")
        assert len(ref) == 9  # MED- + 5 digits

    def test_uniqueness(self):
        from app.modules.flow.handlers.booking import _generate_booking_reference

        refs = {_generate_booking_reference() for _ in range(100)}
        # With 5-digit numbers, 100 samples should be mostly unique
        assert len(refs) > 90


# ── 12. Vercel Configuration Test ────────────────────────────────────────────


class TestVercelConfig:
    """Test that Vercel deployment configuration is correct."""

    def test_vercel_json_structure(self):
        import json

        with open("vercel.json") as f:
            config = json.load(f)

        assert config["version"] == 2
        assert config["builds"][0]["src"] == "api/index.py"
        assert config["builds"][0]["use"] == "@vercel/python"
        assert config["routes"][0]["dest"] == "api/index.py"

    def test_cron_jobs_configured(self):
        import json

        with open("vercel.json") as f:
            config = json.load(f)

        cron_paths = {c["path"] for c in config["crons"]}
        assert "/jobs/send-reminders" in cron_paths
        assert "/jobs/expire-sessions" in cron_paths
        assert "/jobs/expire-payments" in cron_paths


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
