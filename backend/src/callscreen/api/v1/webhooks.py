"""Twilio webhook handlers."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from callscreen.security.twilio_validator import validate_twilio_signature

logger = logging.getLogger("callscreen.webhooks")

router = APIRouter()


@router.post("/voice/incoming")
async def incoming_call(
    request: Request,
    _sig=Depends(validate_twilio_signature),
):
    """Handle incoming voice call from Twilio."""
    form = await request.form()
    call_sid = form.get("CallSid", "")
    from_number = form.get("From", "")
    to_number = form.get("To", "")
    stir_verstat = form.get("StirVerstat", "")

    logger.info(
        "Incoming call: sid=%s from=%s to=%s stir=%s",
        call_sid,
        from_number,
        to_number,
        stir_verstat,
    )

    # Phase 1: Basic greeting with DTMF gather
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather numDigits="1" action="/api/v1/webhooks/voice/gather" method="POST" timeout="10">
        <Say voice="alice">
            Hello. You have reached an automated call screening service.
            Press 1 to be connected, or press 2 to leave a message.
        </Say>
    </Gather>
    <Say voice="alice">We did not receive a response. Goodbye.</Say>
    <Hangup/>
</Response>"""

    return Response(content=twiml, media_type="application/xml")


@router.post("/voice/gather")
async def gather_handler(
    request: Request,
    _sig=Depends(validate_twilio_signature),
):
    """Handle DTMF input from caller."""
    form = await request.form()
    digits = form.get("Digits", "")
    call_sid = form.get("CallSid", "")

    logger.info("DTMF input: sid=%s digits=%s", call_sid, digits)

    if digits == "1":
        # Forward to user's phone (configured in settings)
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Please hold while we connect your call.</Say>
    <Dial timeout="30">
        <Number/>
    </Dial>
</Response>"""
    elif digits == "2":
        # Voicemail
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Please leave your message after the tone. Press pound when finished.</Say>
    <Record maxLength="120" action="/api/v1/webhooks/voice/recording" method="POST" finishOnKey="#"/>
</Response>"""
    else:
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Invalid selection. Goodbye.</Say>
    <Hangup/>
</Response>"""

    return Response(content=twiml, media_type="application/xml")


@router.post("/voice/status")
async def call_status(
    request: Request,
    _sig=Depends(validate_twilio_signature),
):
    """Handle call status callback."""
    form = await request.form()
    call_sid = form.get("CallSid", "")
    call_status = form.get("CallStatus", "")
    logger.info("Call status: sid=%s status=%s", call_sid, call_status)
    return Response(content="", status_code=204)


@router.post("/voice/recording")
async def recording_callback(
    request: Request,
    _sig=Depends(validate_twilio_signature),
):
    """Handle recording status callback."""
    form = await request.form()
    call_sid = form.get("CallSid", "")
    recording_url = form.get("RecordingUrl", "")
    recording_sid = form.get("RecordingSid", "")
    logger.info(
        "Recording ready: sid=%s recording_sid=%s url=%s",
        call_sid,
        recording_sid,
        recording_url,
    )
    # TODO: Download, encrypt, store in S3 (Sprint 1.2 completion)
    return Response(content="", status_code=204)


@router.post("/voice/fallback")
async def fallback(request: Request):
    """Fallback handler when primary webhook fails.

    Forwards call directly to user's phone for safety.
    No signature validation here to ensure it always works.
    """
    logger.warning("Fallback webhook triggered - forwarding call directly")
    twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">We are experiencing technical difficulties. Connecting you now.</Say>
    <Dial timeout="30">
        <Number/>
    </Dial>
</Response>"""
    return Response(content=twiml, media_type="application/xml")
