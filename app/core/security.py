"""Security utilities for MediBook.

Provides JWT verification for admin endpoints using Supabase JWKS,
API key hashing, and cron job authentication.
"""

import hashlib
import hmac
from datetime import datetime, timezone

import httpx
from fastapi import Request

from app.config import get_settings
from app.core.exceptions import CronAuthError
from app.core.logging import get_logger

logger = get_logger(__name__)


async def verify_supabase_jwt(token: str) -> dict:
    """Verify a Supabase JWT token against the JWKS endpoint.

    Args:
        token: The JWT bearer token string.

    Returns:
        The decoded token payload as a dict.

    Raises:
        ValueError: If the token is invalid or verification fails.
    """
    settings = get_settings()
    jwks_url = f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(jwks_url)
            resp.raise_for_status()

        # Use Supabase's gotrue to verify — for production, use python-jose or PyJWT
        # with the JWKS keys. Simplified verification via Supabase client.
        from supabase import create_client

        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_PUBLISHABLE_KEY)
        user_response = supabase.auth.get_user(token)

        if user_response and user_response.user:
            return {
                "sub": user_response.user.id,
                "email": user_response.user.email,
                "role": user_response.user.role,
            }
        raise ValueError("Invalid token: no user found")

    except Exception as exc:
        logger.warning("jwt_verification_failed", error=str(exc))
        raise ValueError(f"JWT verification failed: {exc}") from exc


def hash_api_key(api_key: str) -> str:
    """Hash an API key using SHA-256 for secure storage.

    Args:
        api_key: The plaintext API key.

    Returns:
        The hex-encoded SHA-256 hash of the API key.
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


def verify_api_key(plaintext: str, hashed: str) -> bool:
    """Verify an API key against its stored hash using constant-time comparison.

    Args:
        plaintext: The plaintext API key to verify.
        hashed: The stored SHA-256 hash to compare against.

    Returns:
        True if the key matches, False otherwise.
    """
    return hmac.compare_digest(hash_api_key(plaintext), hashed)


def verify_cron_secret(request: Request) -> None:
    """Verify the cron job authorization header.

    All /jobs/* endpoints must call this to authenticate cron requests.
    The Authorization header must contain 'Bearer {CRON_SECRET}'.

    Args:
        request: The incoming FastAPI request.

    Raises:
        CronAuthError: If the authorization header is missing or invalid.
    """
    settings = get_settings()
    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        logger.warning("cron_auth_missing_header", path=str(request.url.path))
        raise CronAuthError(
            message="Missing or invalid Authorization header",
            context={"path": str(request.url.path)},
        )

    token = auth_header.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(token, settings.CRON_SECRET):
        logger.warning("cron_auth_invalid_secret", path=str(request.url.path))
        raise CronAuthError(
            message="Invalid cron secret",
            context={"path": str(request.url.path)},
        )
