"""FastAPI application factory for MediBook.

Creates and configures the FastAPI app with middleware, exception handlers,
and router registration. This is the main entry point imported by api/index.py
for Vercel serverless deployment.
"""

from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import get_settings
from app.core.error_handlers import register_exception_handlers
from app.core.logging import get_logger, setup_logging

logger = get_logger(__name__)

APP_NAME = "MediBook"
APP_VERSION = "1.0.0"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware that adds security headers to all responses.

    Adds Strict-Transport-Security and other security headers
    to enforce HTTPS-only access.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """Add security headers to the response.

        Args:
            request: The incoming request.
            call_next: The next middleware/handler in the chain.

        Returns:
            The response with security headers added.
        """
        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = (
            "max-age=63072000; includeSubDomains; preload"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Initializes logging, registers middleware, exception handlers,
    and all route modules.

    Returns:
        The configured FastAPI application instance.
    """
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL)

    application = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        description="WhatsApp Appointment Booking for Divine Comfort Clinic — Harare, Zimbabwe",
        docs_url="/docs" if settings.APP_ENV != "production" else None,
        redoc_url="/redoc" if settings.APP_ENV != "production" else None,
    )

    # --- Middleware ---
    application.add_middleware(SecurityHeadersMiddleware)

    # --- Exception Handlers ---
    register_exception_handlers(application)

    # --- Routers ---
    from app.modules.webhook.router import router as webhook_router
    from app.modules.clinics.router import router as clinics_router
    from app.modules.bookings.router import router as bookings_router
    from app.modules.payments.router import router as payments_router
    from app.modules.reminders.router import router as reminders_router

    application.include_router(webhook_router)
    application.include_router(clinics_router)
    application.include_router(bookings_router)
    application.include_router(payments_router)
    application.include_router(reminders_router)

    # --- Auto-seed clinic on startup ---
    _ensure_clinic_exists(settings)

    # --- Health / Root ---
    @application.get("/", tags=["health"])
    async def root():
        """Health check endpoint.

        Returns:
            App name and version confirming the service is running.
        """
        return {
            "app": APP_NAME,
            "version": APP_VERSION,
            "clinic": settings.CLINIC_NAME,
            "status": "healthy",
        }

    logger.info(
        "app_initialized",
        app=APP_NAME,
        version=APP_VERSION,
        clinic=settings.CLINIC_NAME,
        env=settings.APP_ENV,
    )
    return application


def _ensure_clinic_exists(settings) -> None:
    """Auto-seed Divine Comfort Clinic if it does not yet exist in the database.

    Looks up the clinic by its configured WhatsApp number. If not found,
    inserts a new row. If found, updates the name/address if they differ.

    Args:
        settings: The application Settings instance.
    """
    try:
        from app.db.client import get_supabase_client

        db = get_supabase_client()
        clean_number = settings.CLINIC_WHATSAPP_NUMBER.replace("+", "")

        result = (
            db.table("clinics")
            .select("id, name, whatsapp_number")
            .eq("whatsapp_number", clean_number)
            .execute()
        )

        if result.data:
            clinic = result.data[0]
            # Update name if it changed
            if clinic["name"] != settings.CLINIC_NAME:
                db.table("clinics").update({
                    "name": settings.CLINIC_NAME,
                }).eq("id", clinic["id"]).execute()
            logger.info("clinic_seed_exists", clinic_id=clinic["id"], name=settings.CLINIC_NAME)
        else:
            insert_result = db.table("clinics").insert({
                "name": settings.CLINIC_NAME,
                "whatsapp_number": clean_number,
                "twilio_account_sid": settings.TWILIO_ACCOUNT_SID,
                "twilio_auth_token": settings.TWILIO_AUTH_TOKEN,
                "timezone": "Africa/Harare",
                "is_active": True,
                "subscription_tier": "premium",
                "greeting_message": f"Welcome to {settings.CLINIC_NAME}!",
            }).execute()

            if insert_result.data:
                logger.info(
                    "clinic_seeded",
                    clinic_id=insert_result.data[0]["id"],
                    name=settings.CLINIC_NAME,
                )
    except Exception as exc:
        logger.warning("clinic_seed_failed", error=str(exc))


app = create_app()
