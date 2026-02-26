"""Application configuration via pydantic-settings.

All secrets and environment variables are loaded here.
Access via `get_settings()` dependency or direct import.
No secret is ever hardcoded — every value comes from environment variables.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """MediBook application settings.

    Attributes:
        SUPABASE_URL: Supabase project URL.
        SUPABASE_PUBLISHABLE_KEY: Supabase publishable/service key.
        TWILIO_ACCOUNT_SID: Twilio account SID.
        TWILIO_AUTH_TOKEN: Twilio auth token.
        TWILIO_WHATSAPP_NUMBER: Default Twilio WhatsApp sender number.
        ECOCASH_API_KEY: EcoCash API key.
        ECOCASH_BASE_URL: EcoCash API base URL.
        ECOCASH_SANDBOX: Whether to use EcoCash sandbox mode.
        APP_ENV: Application environment (development, staging, production).
        SECRET_KEY: Application secret key for signing.
        CRON_SECRET: Secret for authenticating cron job requests.
        LOG_LEVEL: Logging level.
        VERCEL_URL: Vercel deployment URL.
        CLINIC_NAME: The single clinic's display name.
        CLINIC_ADDRESS: The clinic's physical address.
        CLINIC_WHATSAPP_NUMBER: The clinic's WhatsApp number (without whatsapp: prefix).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # Supabase
    SUPABASE_URL: str
    SUPABASE_PUBLISHABLE_KEY: str

    # Twilio
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    TWILIO_WHATSAPP_NUMBER: str = "whatsapp:+14155238886"

    # EcoCash
    ECOCASH_API_KEY: str
    ECOCASH_BASE_URL: str = "https://developers.ecocash.co.zw/api/ecocash_pay"
    ECOCASH_SANDBOX: bool = True

    # App
    APP_ENV: Literal["development", "staging", "production"] = "development"
    SECRET_KEY: str
    CRON_SECRET: str
    LOG_LEVEL: str = "INFO"

    # Vercel
    VERCEL_URL: str = "http://localhost:8000"

    # Clinic (single-tenant)
    CLINIC_NAME: str = "Divine Comfort Clinic"
    CLINIC_ADDRESS: str = "Harare, Zimbabwe"
    CLINIC_WHATSAPP_NUMBER: str = "+14155238886"


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings singleton.

    Returns:
        Settings: The application settings instance.
    """
    return Settings()
