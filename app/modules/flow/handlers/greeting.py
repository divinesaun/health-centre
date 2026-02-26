"""Greeting handler for the IDLE state.

Handles the first message from a patient in a new or reset session.
Upserts the patient record and sends the branded greeting with main menu.
"""

from app.core.logging import get_logger
from app.db.client import get_supabase_client
from app.modules.flow.states import ConversationState
from app.modules.flow import templates

logger = get_logger(__name__)


async def handle_idle(
    clinic_id: str,
    clinic: dict,
    patient_whatsapp: str,
    message_body: str,
    context: dict,
    profile_name: str | None = None,
) -> tuple[ConversationState, list[str], dict]:
    """Handle a message when the patient is in IDLE state.

    Upserts the patient record, retrieves the patient name if available,
    and sends the branded greeting with the main menu.

    Args:
        clinic_id: The clinic UUID.
        clinic: The full clinic record dict.
        patient_whatsapp: The patient's WhatsApp number.
        message_body: The patient's message text.
        context: The current session context dict.
        profile_name: The WhatsApp profile name, if available.

    Returns:
        Tuple of (new_state, response_messages, updated_context).
    """
    db = get_supabase_client()
    clinic_name = clinic.get("name", "Medical Centre")

    # Strip whatsapp: prefix for storage
    clean_number = patient_whatsapp.replace("whatsapp:", "")

    # Upsert patient record
    patient_name = profile_name
    existing = (
        db.table("patients")
        .select("id, name")
        .eq("clinic_id", clinic_id)
        .eq("whatsapp_number", clean_number)
        .execute()
    )

    if existing.data:
        patient = existing.data[0]
        patient_name = patient.get("name") or profile_name
        # Update name if we have a profile name and patient has no name
        if profile_name and not patient.get("name"):
            db.table("patients").update({"name": profile_name}).eq(
                "id", patient["id"]
            ).eq("clinic_id", clinic_id).execute()
        context["patient_id"] = patient["id"]
    else:
        result = (
            db.table("patients")
            .insert(
                {
                    "clinic_id": clinic_id,
                    "whatsapp_number": clean_number,
                    "name": profile_name,
                }
            )
            .execute()
        )
        if result.data:
            context["patient_id"] = result.data[0]["id"]

    context["patient_name"] = patient_name

    greeting = templates.greeting_message(clinic_name, patient_name)

    logger.info(
        "greeting_sent",
        clinic_id=clinic_id,
        patient_whatsapp=patient_whatsapp,
    )

    return ConversationState.SELECTING_SERVICE, [greeting], context
