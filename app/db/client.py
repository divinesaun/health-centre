"""Supabase service-role client singleton.

Provides a single shared Supabase client instance that uses the service_role
key, which bypasses RLS. This client is server-side only — the key must never
be sent to any client or logged.
"""

from supabase import Client, create_client

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_supabase_client: Client | None = None


def get_supabase_client() -> Client:
    """Return the singleton Supabase service-role client.

    The client uses the service_role key which bypasses Row Level Security.
    This is appropriate for server-side operations only.

    Returns:
        The shared Supabase client instance.
    """
    global _supabase_client
    if _supabase_client is None:
        settings = get_settings()
        _supabase_client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_ROLE_KEY,
        )
        logger.info("supabase_client_initialized")
    return _supabase_client
