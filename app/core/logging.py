"""Structured JSON logger for MediBook.

Uses structlog with automatic PII redaction. Fields named api_key,
auth_token, pin, password, service_role_key are redacted from all log output.
Patient WhatsApp numbers are masked to show only last 4 digits.
"""

import logging
import re
import sys
from typing import Any

import structlog

REDACTED_FIELDS = {"api_key", "auth_token", "pin", "password", "service_role_key"}
PHONE_PATTERN = re.compile(r"(\d{2,})\d{4}$")


def _mask_phone_number(phone: str) -> str:
    """Mask a phone number to show only last 4 digits.

    Args:
        phone: Full phone number string.

    Returns:
        Masked phone string with only last 4 digits visible.
    """
    if len(phone) <= 4:
        return "****"
    return "*" * (len(phone) - 4) + phone[-4:]


def _redact_sensitive_fields(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Structlog processor that redacts sensitive fields from log entries.

    Args:
        logger: The logger instance (unused).
        method_name: The log method name (unused).
        event_dict: The event dictionary to process.

    Returns:
        The event dictionary with sensitive fields redacted.
    """
    for key in list(event_dict.keys()):
        if key.lower() in REDACTED_FIELDS:
            event_dict[key] = "[REDACTED]"
        elif key == "patient_whatsapp" and isinstance(event_dict[key], str):
            event_dict[key] = _mask_phone_number(event_dict[key])
    return event_dict


def setup_logging(log_level: str = "INFO") -> None:
    """Configure structured logging for the application.

    Sets up structlog with JSON rendering, timestamps, and PII redaction.
    Should be called once during application startup.

    Args:
        log_level: The logging level string (DEBUG, INFO, WARNING, ERROR).
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.UnicodeDecoder(),
            _redact_sensitive_fields,
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )


def get_logger(name: str = "medibook") -> structlog.stdlib.BoundLogger:
    """Get a named structured logger instance.

    Args:
        name: Logger name, typically the module name.

    Returns:
        A bound structlog logger instance.
    """
    return structlog.get_logger(name)
