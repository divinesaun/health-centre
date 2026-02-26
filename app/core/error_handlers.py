"""FastAPI exception handler registrations.

Registers global exception handlers for the custom exception hierarchy.
Level 1 error handling — catches all exceptions at the request level.
Never exposes internal errors to clients or patients.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    ClinicNotFoundError,
    CronAuthError,
    InvalidTwilioSignatureError,
    MediBookException,
    RateLimitExceededError,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Register all custom exception handlers on the FastAPI app.

    Args:
        app: The FastAPI application instance.
    """

    @app.exception_handler(InvalidTwilioSignatureError)
    async def handle_invalid_twilio_signature(
        request: Request, exc: InvalidTwilioSignatureError
    ) -> JSONResponse:
        """Handle invalid Twilio signature — HTTP 403.

        Logs as a security event with the source IP address.
        """
        client_ip = request.client.host if request.client else "unknown"
        logger.warning(
            "invalid_twilio_signature",
            source_ip=client_ip,
            path=str(request.url.path),
            **exc.context,
        )
        return JSONResponse(status_code=403, content={"error": "Forbidden"})

    @app.exception_handler(ClinicNotFoundError)
    async def handle_clinic_not_found(
        request: Request, exc: ClinicNotFoundError
    ) -> JSONResponse:
        """Handle clinic not found — HTTP 404.

        No WhatsApp response is sent for unknown numbers.
        """
        logger.warning("clinic_not_found", **exc.context)
        return JSONResponse(status_code=404, content={"error": "Clinic not found"})

    @app.exception_handler(CronAuthError)
    async def handle_cron_auth_error(
        request: Request, exc: CronAuthError
    ) -> JSONResponse:
        """Handle cron authentication failure — HTTP 401."""
        logger.warning("cron_auth_failed", **exc.context)
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})

    @app.exception_handler(RateLimitExceededError)
    async def handle_rate_limit_exceeded(
        request: Request, exc: RateLimitExceededError
    ) -> JSONResponse:
        """Handle rate limit exceeded — HTTP 429."""
        logger.warning("rate_limit_exceeded", **exc.context)
        return JSONResponse(
            status_code=429, content={"error": "Too many requests"}
        )

    @app.exception_handler(MediBookException)
    async def handle_medibook_exception(
        request: Request, exc: MediBookException
    ) -> JSONResponse:
        """Handle any other MediBook exception — HTTP 400."""
        logger.error("medibook_error", error=exc.message, **exc.context)
        return JSONResponse(
            status_code=400, content={"error": "Request could not be processed"}
        )

    @app.exception_handler(Exception)
    async def handle_unhandled_exception(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Handle all unhandled exceptions — HTTP 500.

        Logs full traceback with context but never exposes internals to clients.
        """
        logger.error(
            "unhandled_exception",
            error=str(exc),
            path=str(request.url.path),
            method=request.method,
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"},
        )
