"""Payment API endpoints.

Includes the EcoCash callback endpoint and cron job endpoints for
payment expiry, slot lock release, and the consolidated run-all-jobs
endpoint for Vercel Hobby plan (single cron job).
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request

from app.core.logging import get_logger
from app.db.client import get_supabase_client
from app.dependencies import require_cron_auth
from app.modules.bookings.service import BookingService
from app.modules.payments.schemas import EcoCashCallbackPayload
from app.modules.payments.service import PaymentService
from app.modules.reminders.service import ReminderService

logger = get_logger(__name__)

router = APIRouter(tags=["payments"])


@router.post("/payments/ecocash/callback")
async def ecocash_callback(payload: EcoCashCallbackPayload):
    """Receive an EcoCash payment callback/notification.

    Called by the EcoCash API when a payment status changes.
    Processes the callback and completes or cancels the booking.

    Args:
        payload: The EcoCash callback payload.

    Returns:
        Processing result dict.
    """
    service = PaymentService()
    result = await service.handle_ecocash_callback(payload.model_dump())
    return result


@router.get("/jobs/expire-payments")
async def expire_payments_job(request: Request, _auth=Depends(require_cron_auth)):
    """Cron job: Expire stale payments and release locked slots.

    Runs every 3 minutes via Vercel cron. Finds payments pending for
    more than 10 minutes, marks them expired, releases slots, cancels
    appointments, and notifies patients.

    Args:
        request: The incoming request.
        _auth: Cron authentication (injected).

    Returns:
        Dict with number of expired payments.
    """
    payment_service = PaymentService()
    expired_count = await payment_service.expire_stale_payments()

    # Also release expired slot locks
    booking_service = BookingService()
    released_count = booking_service.release_expired_locks()

    logger.info(
        "expire_payments_job_completed",
        expired_payments=expired_count,
        released_slots=released_count,
    )
    return {
        "status": "ok",
        "expired_payments": expired_count,
        "released_slots": released_count,
    }


@router.get("/jobs/expire-sessions")
async def expire_sessions_job(request: Request, _auth=Depends(require_cron_auth)):
    """Cron job: Clean up expired conversation sessions.

    Resets expired sessions to IDLE state with empty context.

    Args:
        request: The incoming request.
        _auth: Cron authentication (injected).

    Returns:
        Dict with number of sessions reset.
    """
    count = await _reset_expired_sessions()
    return {"status": "ok", "sessions_reset": count}


async def _reset_expired_sessions() -> int:
    """Reset all expired conversation sessions to IDLE.

    Returns:
        Number of sessions reset.
    """
    db = get_supabase_client()
    now = datetime.now(timezone.utc).isoformat()

    result = (
        db.table("conversation_sessions")
        .update({"state": "IDLE", "context": {}})
        .lt("expires_at", now)
        .neq("state", "IDLE")
        .execute()
    )

    count = len(result.data) if result.data else 0
    if count > 0:
        logger.info("sessions_expired", count=count)
    return count


@router.get("/jobs/run-all")
async def run_all_jobs(request: Request, _auth=Depends(require_cron_auth)):
    """Consolidated cron job for Vercel Hobby plan.

    Runs all three maintenance tasks in sequence:
    1. Send due appointment reminders
    2. Expire stale payments and release locked slots
    3. Reset expired conversation sessions

    Schedule hourly (Vercel Hobby limit: 1 cron, minimum 1-hour interval).

    Args:
        request: The incoming request.
        _auth: Cron authentication (injected).

    Returns:
        Dict with counts from all three tasks.
    """
    reminder_service = ReminderService()
    reminders_sent = await reminder_service.send_due_reminders()

    payment_service = PaymentService()
    expired_payments = await payment_service.expire_stale_payments()

    booking_service = BookingService()
    released_slots = booking_service.release_expired_locks()

    sessions_reset = await _reset_expired_sessions()

    logger.info(
        "run_all_jobs_completed",
        reminders_sent=reminders_sent,
        expired_payments=expired_payments,
        released_slots=released_slots,
        sessions_reset=sessions_reset,
    )
    return {
        "status": "ok",
        "reminders_sent": reminders_sent,
        "expired_payments": expired_payments,
        "released_slots": released_slots,
        "sessions_reset": sessions_reset,
    }
