"""TwiML response builder for Twilio voice call control."""

from callscreen.security.validators import sanitize_for_twiml


def greeting_twiml(message: str, gather_url: str, timeout: int = 10) -> str:
    """Build TwiML for greeting with DTMF gathering."""
    sanitized_message = sanitize_for_twiml(message)
    sanitized_url = sanitize_for_twiml(gather_url)
    
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather numDigits="1" action="{sanitized_url}" method="POST" timeout="{timeout}">
        <Say voice="alice">{sanitized_message}</Say>
    </Gather>
    <Say voice="alice">We did not receive a response. Goodbye.</Say>
    <Hangup/>
</Response>"""
    return twiml


def forward_twiml(phone_number: str, caller_id: str = '', timeout: int = 30) -> str:
    """Build TwiML for forwarding call to a phone number."""
    sanitized_number = sanitize_for_twiml(phone_number)
    sanitized_caller_id = sanitize_for_twiml(caller_id)

    if sanitized_caller_id:
        dial_open = f'<Dial timeout="{timeout}" callerId="{sanitized_caller_id}">'
    else:
        dial_open = f'<Dial timeout="{timeout}">'

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Please hold while we connect your call.</Say>
    {dial_open}
        <Number>{sanitized_number}</Number>
    </Dial>
</Response>"""
    return twiml


def reject_twiml(reason: str = 'rejected') -> str:
    """Build TwiML for rejecting a call."""
    valid_reasons = {'rejected', 'busy'}
    if reason not in valid_reasons:
        reason = 'rejected'
    
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Reject reason="{reason}"/>
</Response>"""
    return twiml


def voicemail_twiml(record_url: str, max_length: int = 120) -> str:
    """Build TwiML for voicemail recording."""
    sanitized_url = sanitize_for_twiml(record_url)
    
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Please leave your message after the tone. Press pound when finished.</Say>
    <Record maxLength="{max_length}" action="{sanitized_url}" method="POST" finishOnKey="#"/>
</Response>"""
    return twiml


def hold_twiml(message: str = 'Please hold while we process your call.', music_url: str | None = None) -> str:
    """Build TwiML for hold with message or music loop."""
    sanitized_message = sanitize_for_twiml(message)
    
    if music_url:
        sanitized_music_url = sanitize_for_twiml(music_url)
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play loop="10">{sanitized_music_url}</Play>
</Response>"""
    else:
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">{sanitized_message}</Say>
    <Play loop="10">https://api.twilio.com/cowbell.mp3</Play>
</Response>"""
    
    return twiml


def screening_twiml(message: str, stream_url: str) -> str:
    """Build TwiML for AI screening with bidirectional media stream."""
    sanitized_message = sanitize_for_twiml(message)
    sanitized_stream_url = sanitize_for_twiml(stream_url)
    
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">{sanitized_message}</Say>
    <Connect>
        <Stream url="{sanitized_stream_url}" bidirectional="true"/>
    </Connect>
</Response>"""
    return twiml


def forward_sip_twiml(sip_uri: str, caller_id: str = '', timeout: int = 30) -> str:
    """Build TwiML for forwarding call to a SIP URI (VoIP/PBX endpoint).

    Used for direct SIP forwarding to systems like UniFi Talk, FreePBX,
    Asterisk, or any SIP-capable endpoint.
    """
    sanitized_uri = sanitize_for_twiml(sip_uri)
    sanitized_caller_id = sanitize_for_twiml(caller_id)

    if sanitized_caller_id:
        dial_open = f'<Dial timeout="{timeout}" callerId="{sanitized_caller_id}">'
    else:
        dial_open = f'<Dial timeout="{timeout}">'

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Please hold while we connect your call.</Say>
    {dial_open}
        <Sip>{sanitized_uri}</Sip>
    </Dial>
</Response>"""
    return twiml


def simultaneous_ring_twiml(
    numbers: list[str],
    sip_uri: str = '',
    caller_id: str = '',
    timeout: int = 30,
) -> str:
    """Build TwiML for ringing multiple endpoints simultaneously.

    Twilio dials all endpoints at once; first to pick up wins.
    Can mix PSTN numbers and a SIP URI in a single Dial.
    """
    sanitized_caller_id = sanitize_for_twiml(caller_id)

    if sanitized_caller_id:
        dial_open = f'<Dial timeout="{timeout}" callerId="{sanitized_caller_id}">'
    else:
        dial_open = f'<Dial timeout="{timeout}">'

    endpoints = ""
    for number in numbers:
        sanitized = sanitize_for_twiml(number)
        endpoints += f"\n        <Number>{sanitized}</Number>"

    if sip_uri:
        sanitized_uri = sanitize_for_twiml(sip_uri)
        endpoints += f"\n        <Sip>{sanitized_uri}</Sip>"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Please hold while we connect your call.</Say>
    {dial_open}{endpoints}
    </Dial>
</Response>"""
    return twiml


def emergency_forward_twiml(phone_number: str) -> str:
    """Build TwiML for immediate emergency call forwarding."""
    sanitized_number = sanitize_for_twiml(phone_number)

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Dial timeout="30">
        <Number>{sanitized_number}</Number>
    </Dial>
</Response>"""
    return twiml
