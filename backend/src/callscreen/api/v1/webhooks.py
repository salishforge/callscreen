"""Twilio webhook handlers."""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from callscreen.config import Settings, get_settings
from callscreen.core.call_state import CallStateMachine
from callscreen.core.emergency import is_emergency_number
from callscreen.core.twiml import (
    emergency_forward_twiml,
    forward_sip_twiml,
    forward_twiml,
    greeting_twiml,
    reject_twiml,
    simultaneous_ring_twiml,
    voicemail_twiml,
)
from callscreen.db.session import get_db
from callscreen.models.call import CallStatus
from callscreen.models.contact import Contact, ContactType
from callscreen.models.settings import ForwardMode, UserSettings
from callscreen.models.user import User
from callscreen.security.twilio_validator import validate_twilio_signature

logger = logging.getLogger("callscreen.webhooks")

router = APIRouter()

GATHER_URL = "/api/v1/webhooks/voice/gather"
RECORDING_URL = "/api/v1/webhooks/voice/recording"


async def _lookup_contact(
    db: AsyncSession, from_number: str,
) -> Contact | None:
    """Look up a contact by phone number."""
    result = await db.execute(
        select(Contact).where(Contact.phone_number == from_number).limit(1)
    )
    return result.scalar_one_or_none()


async def _get_user_settings(
    db: AsyncSession, to_number: str,
) -> UserSettings | None:
    """Look up user settings for the Twilio number being called.

    Finds the user who owns this Twilio number (matched via User.phone_number
    or the global CALLSCREEN config) and returns their forwarding settings.
    """
    # Try to find user whose phone_number matches the Twilio number
    result = await db.execute(
        select(UserSettings)
        .join(User, User.id == UserSettings.user_id)
        .where(User.phone_number == to_number)
        .limit(1)
    )
    settings = result.scalar_one_or_none()
    if settings:
        return settings

    # Fall back: return the first user's settings (single-user deployment)
    result = await db.execute(select(UserSettings).limit(1))
    return result.scalar_one_or_none()


def _build_forward_twiml(
    user_settings: UserSettings | None,
    app_settings: Settings,
    caller_id: str = "",
) -> str:
    """Build the correct forwarding TwiML based on user + app configuration.

    Resolution order:
    1. Per-user settings (forward_mode, forward_phone_number, forward_sip_uri)
    2. App-level env vars (CALLSCREEN_FORWARD_NUMBER, CALLSCREEN_FORWARD_SIP_URI)
    3. Fallback to twilio_phone_number (backward-compatible)
    """
    # Determine forwarding parameters from user settings or app config
    mode = ForwardMode.PHONE
    phone = ""
    sip_uri = ""
    timeout = app_settings.callscreen_forward_timeout
    sim_ring: list[str] = []

    if user_settings:
        mode = ForwardMode(user_settings.forward_mode)
        phone = user_settings.forward_phone_number
        sip_uri = user_settings.forward_sip_uri
        timeout = user_settings.forward_timeout or timeout
        if user_settings.simultaneous_ring_numbers:
            sim_ring = [
                n.strip()
                for n in user_settings.simultaneous_ring_numbers.split(",")
                if n.strip()
            ]

    # Fall back to app-level config if user settings are empty
    if not phone:
        phone = app_settings.callscreen_forward_number
    if not sip_uri:
        sip_uri = app_settings.callscreen_forward_sip_uri
    if not sim_ring:
        sim_ring = app_settings.simultaneous_ring_numbers

    # If still no explicit forwarding destination, use the Twilio number itself
    if not phone and not sip_uri:
        phone = app_settings.twilio_phone_number

    # Build TwiML based on mode
    if mode == ForwardMode.SIMULTANEOUS:
        numbers = [phone] + sim_ring if phone else sim_ring
        return simultaneous_ring_twiml(
            numbers=numbers,
            sip_uri=sip_uri,
            caller_id=caller_id,
            timeout=timeout,
        )
    elif mode == ForwardMode.SIP and sip_uri:
        return forward_sip_twiml(
            sip_uri=sip_uri,
            caller_id=caller_id,
            timeout=timeout,
        )
    else:
        # Default: PHONE mode
        return forward_twiml(
            phone_number=phone,
            caller_id=caller_id,
            timeout=timeout,
        )


def _build_emergency_forward_twiml(
    user_settings: UserSettings | None,
    app_settings: Settings,
) -> str:
    """Build emergency forwarding TwiML.

    Emergency calls always use the most direct path. SIP is avoided
    for reliability — PSTN phone number is strongly preferred.
    """
    phone = ""
    if user_settings:
        phone = user_settings.forward_phone_number
    if not phone:
        phone = app_settings.callscreen_forward_number
    if not phone:
        phone = app_settings.twilio_phone_number

    return emergency_forward_twiml(phone)


@router.post("/voice/incoming")
async def incoming_call(
    request: Request,
    _sig=Depends(validate_twilio_signature),
    db: AsyncSession = Depends(get_db),
):
    """Handle incoming voice call from Twilio."""
    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    from_number = str(form.get("From", ""))
    to_number = str(form.get("To", ""))
    stir_verstat = str(form.get("StirVerstat", ""))

    logger.info(
        "Incoming call: sid=%s from=%s to=%s stir=%s",
        call_sid,
        from_number,
        to_number,
        stir_verstat,
    )

    settings = get_settings()

    # 1. Emergency callback — unconditional forward, zero DB dependency
    if is_emergency_number(from_number):
        logger.warning("Emergency callback detected from %s — immediate forward", from_number)
        # Emergency: use app-level config only (no DB dependency)
        phone = settings.callscreen_forward_number or settings.twilio_phone_number
        twiml = emergency_forward_twiml(phone)
        return Response(content=twiml, media_type="application/xml")

    # 2. Initialize call state
    await CallStateMachine.create(call_sid, from_number, to_number)

    # 3. Load user forwarding settings for this number
    user_settings = await _get_user_settings(db, to_number)

    # 4. Triage — check whitelist/blocklist
    await CallStateMachine.transition(call_sid, CallStatus.TRIAGE)
    contact = await _lookup_contact(db, from_number)

    if contact and contact.contact_type == ContactType.WHITELIST:
        logger.info("Whitelist match for %s — forwarding", from_number)
        await CallStateMachine.transition(call_sid, CallStatus.FORWARDING)
        twiml = _build_forward_twiml(user_settings, settings, caller_id=from_number)
        return Response(content=twiml, media_type="application/xml")

    if contact and contact.contact_type == ContactType.BLOCKLIST:
        logger.info("Blocklist match for %s — rejecting", from_number)
        await CallStateMachine.transition(call_sid, CallStatus.BLOCKING)
        twiml = reject_twiml("rejected")
        return Response(content=twiml, media_type="application/xml")

    # 5. Unknown caller — STIR/SHAKEN metadata, then screen via DTMF
    if stir_verstat:
        await CallStateMachine.set_metadata(call_sid, "stir_attestation", stir_verstat)

    await CallStateMachine.transition(call_sid, CallStatus.NUMBER_LOOKUP)
    await CallStateMachine.transition(call_sid, CallStatus.SCREENING)

    # Use per-user greeting if available
    greeting = (
        "Hello. You have reached an automated call screening service. "
        "Press 1 to be connected, or press 2 to leave a message."
    )
    if user_settings and user_settings.greeting_message:
        greeting = (
            f"{user_settings.greeting_message} "
            "Press 1 to be connected, or press 2 to leave a message."
        )

    twiml = greeting_twiml(greeting, GATHER_URL)
    return Response(content=twiml, media_type="application/xml")


@router.post("/voice/gather")
async def gather_handler(
    request: Request,
    _sig=Depends(validate_twilio_signature),
    db: AsyncSession = Depends(get_db),
):
    """Handle DTMF input from caller."""
    form = await request.form()
    digits = str(form.get("Digits", ""))
    call_sid = str(form.get("CallSid", ""))
    to_number = str(form.get("To", ""))

    logger.info("DTMF input: sid=%s digits=%s", call_sid, digits)

    settings = get_settings()

    if digits == "1":
        user_settings = await _get_user_settings(db, to_number)
        await CallStateMachine.transition(call_sid, CallStatus.DECIDING)
        await CallStateMachine.transition(call_sid, CallStatus.FORWARDING)
        twiml = _build_forward_twiml(user_settings, settings)
    elif digits == "2":
        await CallStateMachine.transition(call_sid, CallStatus.DECIDING)
        await CallStateMachine.transition(call_sid, CallStatus.MESSAGING)
        twiml = voicemail_twiml(RECORDING_URL)
    else:
        await CallStateMachine.transition(call_sid, CallStatus.FAILED)
        twiml = reject_twiml("rejected")

    return Response(content=twiml, media_type="application/xml")


@router.post("/voice/status")
async def call_status(
    request: Request,
    _sig=Depends(validate_twilio_signature),
):
    """Handle call status callback."""
    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    status = str(form.get("CallStatus", ""))
    logger.info("Call status: sid=%s status=%s", call_sid, status)

    if status in ("completed", "no-answer", "busy", "canceled"):
        try:
            await CallStateMachine.transition(call_sid, CallStatus.COMPLETED)
        except ValueError:
            pass  # Already completed or no state found

    return Response(content="", status_code=204)


@router.post("/voice/recording")
async def recording_callback(
    request: Request,
    background_tasks: BackgroundTasks,
    _sig=Depends(validate_twilio_signature),
    db: AsyncSession = Depends(get_db),
):
    """Handle recording status callback.

    Kicks off a background task to download, encrypt, and store the
    recording in S3, then update the DB.
    """
    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    recording_url = str(form.get("RecordingUrl", ""))
    recording_sid = str(form.get("RecordingSid", ""))
    logger.info(
        "Recording ready: sid=%s recording_sid=%s url=%s",
        call_sid,
        recording_sid,
        recording_url,
    )

    if recording_url and recording_sid:
        from callscreen.core.recording import process_twilio_recording

        background_tasks.add_task(
            process_twilio_recording,
            call_sid=call_sid,
            recording_url=recording_url,
            recording_sid=recording_sid,
            db=db,
        )

    return Response(content="", status_code=204)


@router.post("/voice/fallback")
async def fallback(request: Request):
    """Fallback handler when primary webhook fails.

    Forwards call directly to user's phone for safety.
    No signature validation — must always work.
    No DB dependency — uses app-level config only.
    """
    logger.warning("Fallback webhook triggered - forwarding call directly")
    settings = get_settings()
    phone = settings.callscreen_forward_number or settings.twilio_phone_number
    twiml = emergency_forward_twiml(phone)
    return Response(content=twiml, media_type="application/xml")
