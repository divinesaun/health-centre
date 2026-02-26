"""Conversation state enum for the flow engine.

Defines all possible states in the patient conversation state machine.
State transitions are enforced by the flow engine — handlers return
the next state, they do not set it directly.
"""

from enum import Enum


class ConversationState(str, Enum):
    """All possible states in a patient conversation.

    Each state maps to a specific handler in the flow/handlers/ directory.
    The string value is stored in the conversation_sessions.state column.
    """

    IDLE = "IDLE"
    SELECTING_SERVICE = "SELECTING_SERVICE"
    SELECTING_SLOT = "SELECTING_SLOT"
    CONFIRMING_DETAILS = "CONFIRMING_DETAILS"
    AWAITING_PAYMENT = "AWAITING_PAYMENT"
    PAYMENT_PROCESSING = "PAYMENT_PROCESSING"
    BOOKING_COMPLETE = "BOOKING_COMPLETE"
