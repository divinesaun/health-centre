"""Reminders API endpoints.

Includes the cron job endpoint for sending due reminders.
All /jobs/* endpoints require cron secret authentication.
"""

from fastapi import APIRouter, Depends, Request

from app.core.logging import get_logger
from app.dependencies import require_cron_auth
from app.modules.reminders.service import ReminderService

logger = get_logger(__name__)

router = APIRouter(tags=["reminders"])


@router.get("/jobs/send-reminders")
async def send_reminders_job(request: Request, _auth=Depends(require_cron_auth)):
    """Cron job: Send due appointment reminders.

    Runs every 5 minutes via Vercel cron. Finds pending reminders
    where scheduled_for <= NOW() and sends WhatsApp messages.

    Args:
        request: The incoming request.
        _auth: Cron authentication (injected).

    Returns:
        Dict with number of reminders sent.
    """
    service = ReminderService()
    sent_count = await service.send_due_reminders()

    logger.info("send_reminders_job_completed", sent_count=sent_count)
    return {"status": "ok", "reminders_sent": sent_count}
