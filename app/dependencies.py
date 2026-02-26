"""FastAPI dependency injection providers.

Centralized dependency functions used across route handlers.
All dependencies are injected via FastAPI's Depends() mechanism.
"""

from fastapi import Depends, Header, Request

from app.config import Settings, get_settings
from app.core.exceptions import ClinicNotFoundError, CronAuthError, InvalidTwilioSignatureError
from app.core.security import verify_cron_secret, verify_supabase_jwt
from app.db.client import get_supabase_client

from supabase import Client

_cached_clinic_id: str | None = None


def get_db() -> Client:
    """Provide the Supabase client as a dependency.

    Returns:
        The Supabase service-role client instance.
    """
    return get_supabase_client()


def get_config() -> Settings:
    """Provide the application settings as a dependency.

    Returns:
        The application Settings instance.
    """
    return get_settings()


async def require_cron_auth(request: Request) -> None:
    """Dependency that enforces cron job authentication.

    All /jobs/* endpoints must include this dependency.
    Verifies the Authorization: Bearer {CRON_SECRET} header.

    Args:
        request: The incoming FastAPI request.

    Raises:
        CronAuthError: If the cron secret is missing or invalid.
    """
    verify_cron_secret(request)


def get_clinic_id() -> str:
    """Resolve and cache the single Divine Comfort Clinic's UUID.

    In single-tenant mode there is only one clinic. This dependency
    looks it up by the configured CLINIC_WHATSAPP_NUMBER and caches
    the result for the lifetime of the process.

    Returns:
        The clinic UUID string.

    Raises:
        ClinicNotFoundError: If the clinic has not been seeded yet.
    """
    global _cached_clinic_id
    if _cached_clinic_id is not None:
        return _cached_clinic_id

    settings = get_settings()
    db = get_supabase_client()
    clean_number = settings.CLINIC_WHATSAPP_NUMBER.replace("+", "")

    result = (
        db.table("clinics")
        .select("id")
        .eq("whatsapp_number", clean_number)
        .eq("is_active", True)
        .execute()
    )

    if not result.data:
        raise ClinicNotFoundError(
            message="Divine Comfort Clinic not found — start the app to auto-seed",
            context={"whatsapp_number": clean_number},
        )

    _cached_clinic_id = result.data[0]["id"]
    return _cached_clinic_id


async def require_admin_auth(
    authorization: str = Header(..., alias="Authorization"),
) -> dict:
    """Dependency that enforces admin JWT authentication.

    All /admin/* and /clinics/* endpoints must include this dependency.
    Verifies the JWT against Supabase's JWKS endpoint.

    Args:
        authorization: The Authorization header value.

    Returns:
        The decoded JWT payload containing user info.

    Raises:
        ValueError: If the JWT is invalid.
    """
    if not authorization.startswith("Bearer "):
        raise ValueError("Invalid authorization header format")

    token = authorization.removeprefix("Bearer ").strip()
    return await verify_supabase_jwt(token)
