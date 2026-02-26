"""Twilio webhook payload models.

Pydantic models for validating and parsing inbound Twilio WhatsApp
webhook payloads. Input is sanitised: HTML stripped, length limited.
"""

import re
from typing import Optional

from pydantic import BaseModel, field_validator


def strip_html(value: str) -> str:
    """Remove HTML tags from a string.

    Args:
        value: The input string potentially containing HTML.

    Returns:
        The string with all HTML tags removed.
    """
    return re.sub(r"<[^>]+>", "", value)


class TwilioInboundMessage(BaseModel):
    """Model for an inbound Twilio WhatsApp message.

    Attributes:
        MessageSid: Unique Twilio message identifier.
        From_: Sender WhatsApp number (e.g. 'whatsapp:+263...').
        To: Recipient WhatsApp number (clinic's number).
        Body: Message body text from the patient.
        NumMedia: Number of media attachments.
        ProfileName: WhatsApp profile name of the sender.
    """

    MessageSid: str
    From_: str  # 'From' is a reserved word; Twilio sends as 'From'
    To: str
    Body: str = ""
    NumMedia: str = "0"
    ProfileName: Optional[str] = None

    @field_validator("Body")
    @classmethod
    def sanitise_body(cls, v: str) -> str:
        """Strip HTML and limit body to 500 characters.

        Args:
            v: The raw message body.

        Returns:
            The sanitised message body.
        """
        cleaned = strip_html(v).strip()
        return cleaned[:500]

    @field_validator("From_", mode="before")
    @classmethod
    def validate_from(cls, v: str) -> str:
        """Ensure the From number is in WhatsApp format.

        Args:
            v: The raw From number.

        Returns:
            The validated From number.
        """
        if not v.startswith("whatsapp:"):
            return f"whatsapp:{v}"
        return v


class TwilioWebhookForm(BaseModel):
    """Parsed form data from a Twilio webhook POST request.

    Twilio sends data as application/x-www-form-urlencoded.
    This model maps the form fields to typed attributes.

    Attributes:
        MessageSid: Unique Twilio message identifier.
        From_: Sender WhatsApp number.
        To: Recipient WhatsApp number.
        Body: Sanitised message body.
        NumMedia: Number of media attachments.
        ProfileName: WhatsApp profile name of the sender.
    """

    MessageSid: str = ""
    From_: str = ""
    To: str = ""
    Body: str = ""
    NumMedia: str = "0"
    ProfileName: Optional[str] = None

    @field_validator("Body")
    @classmethod
    def sanitise_body(cls, v: str) -> str:
        """Strip HTML and limit body to 500 characters."""
        cleaned = strip_html(v).strip()
        return cleaned[:500]
