"""Payment API endpoints.

Includes the EcoCash callback endpoint and cron job endpoints for
payment expiry and slot lock release.
"""

from fastapi import APIRouter, Depends, Request

from app.core.logging import get_logger
from app.dependencies import require_cron_auth
from app.modules.bookings.service import BookingService
from app.modules.payments.schemas import EcoCashCallbackPayload
from app.modules.payments.service import PaymentService

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

    Runs every 10 minutes via Vercel cron. Resets expired sessions
    to IDLE state with empty context.

    Args:
        request: The incoming request.
        _auth: Cron authentication (injected).

    Returns:
        Dict with number of sessions reset.
    """
    from datetime import datetime, timezone

    from app.db.client import get_supabase_client

    db = get_supabase_client()
    now = datetime.now(timezone.utc).isoformat()

    result = (
        db.table("conversation_sessions")
        .update({
            "state": "IDLE",
            "context": {},
        })
        .lt("expires_at", now)
        .neq("state", "IDLE")
        .execute()
    )

    count = len(result.data) if result.data else 0
    if count > 0:
        logger.info("sessions_expired", count=count)

    return {"status": "ok", "sessions_reset": count}
