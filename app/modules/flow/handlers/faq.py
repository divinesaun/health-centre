"""FAQ handler for answering common patient questions.

Handles FAQ menu display and individual FAQ responses.
All FAQ content is sourced from the templates module.
"""

from app.core.logging import get_logger
from app.modules.flow.states import ConversationState
from app.modules.flow import templates

logger = get_logger(__name__)


async def handle_faq(
    clinic_id: str,
    clinic: dict,
    patient_whatsapp: str,
    message_body: str,
    context: dict,
) -> tuple[ConversationState, list[str], dict]:
    """Handle FAQ interactions.

    Shows the FAQ menu or responds to a specific FAQ selection.
    After answering, the patient can reply MENU to return to the main menu.

    Args:
        clinic_id: The clinic UUID.
        clinic: The full clinic record dict.
        patient_whatsapp: The patient's WhatsApp number.
        message_body: The patient's message text.
        context: The current session context dict.

    Returns:
        Tuple of (new_state, response_messages, updated_context).
    """
    clinic_name = clinic.get("name", "Medical Centre")
    body = message_body.strip()

    # If entering FAQ from menu, show the FAQ list
    if not context.get("in_faq"):
        context["in_faq"] = True
        msg = templates.faq_message(clinic_name)
        return ConversationState.IDLE, [msg], context

    # Handle FAQ selections
    faq_responses = {
        "1": templates.faq_hours_message(),
        "2": templates.faq_cancel_message(),
        "3": templates.faq_payment_message(),
        "4": templates.faq_reschedule_message(),
    }

    if body in faq_responses:
        context["in_faq"] = False
        return ConversationState.IDLE, [faq_responses[body]], {}

    # Invalid FAQ selection — re-show menu
    msg = templates.invalid_input_message(templates.faq_message(clinic_name))
    return ConversationState.IDLE, [msg], context
