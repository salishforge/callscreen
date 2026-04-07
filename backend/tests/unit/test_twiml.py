"""Tests for TwiML response builders."""

import pytest

from callscreen.core.twiml import (
    emergency_forward_twiml,
    forward_twiml,
    greeting_twiml,
    hold_twiml,
    reject_twiml,
    screening_twiml,
    voicemail_twiml,
)


# -- greeting_twiml ----------------------------------------------------------


@pytest.mark.unit
def test_greeting_twiml_xml_declaration():
    result = greeting_twiml("Hello caller", "/gather")
    assert '<?xml version="1.0" encoding="UTF-8"?>' in result


@pytest.mark.unit
def test_greeting_twiml_response_wrapper():
    result = greeting_twiml("Hello caller", "/gather")
    assert "<Response>" in result
    assert "</Response>" in result


@pytest.mark.unit
def test_greeting_twiml_gather_num_digits():
    result = greeting_twiml("Hello caller", "/gather")
    assert 'numDigits="1"' in result


@pytest.mark.unit
def test_greeting_twiml_gather_action_url():
    result = greeting_twiml("Hello", "/handle-key")
    assert 'action="/handle-key"' in result


@pytest.mark.unit
def test_greeting_twiml_gather_method_post():
    result = greeting_twiml("Hello", "/gather")
    assert 'method="POST"' in result


@pytest.mark.unit
def test_greeting_twiml_default_timeout():
    result = greeting_twiml("Hello", "/gather")
    assert 'timeout="10"' in result


@pytest.mark.unit
def test_greeting_twiml_custom_timeout():
    result = greeting_twiml("Hello", "/gather", timeout=5)
    assert 'timeout="5"' in result


@pytest.mark.unit
def test_greeting_twiml_say_message():
    result = greeting_twiml("Press 1 to accept", "/gather")
    assert "Press 1 to accept" in result


@pytest.mark.unit
def test_greeting_twiml_alice_voice():
    result = greeting_twiml("Hello", "/gather")
    assert 'voice="alice"' in result


@pytest.mark.unit
def test_greeting_twiml_fallback_hangup():
    result = greeting_twiml("Hello", "/gather")
    assert "<Hangup/>" in result
    assert "We did not receive a response. Goodbye." in result


@pytest.mark.unit
def test_greeting_twiml_xss_in_message():
    result = greeting_twiml('<script>alert("xss")</script>', "/gather")
    assert "<script>" not in result
    assert "&lt;script&gt;" in result
    assert "&quot;" in result


@pytest.mark.unit
def test_greeting_twiml_xss_in_url():
    result = greeting_twiml("Hello", '/gather?x="><script>alert(1)</script>')
    assert "<script>" not in result
    assert "&quot;" in result


# -- forward_twiml ------------------------------------------------------------


@pytest.mark.unit
def test_forward_twiml_dial_element():
    result = forward_twiml("+15551234567")
    assert "<Dial" in result
    assert "</Dial>" in result


@pytest.mark.unit
def test_forward_twiml_phone_number():
    result = forward_twiml("+15551234567")
    assert "<Number>+15551234567</Number>" in result


@pytest.mark.unit
def test_forward_twiml_default_timeout():
    result = forward_twiml("+15551234567")
    assert 'timeout="30"' in result


@pytest.mark.unit
def test_forward_twiml_custom_timeout():
    result = forward_twiml("+15551234567", timeout=60)
    assert 'timeout="60"' in result


@pytest.mark.unit
def test_forward_twiml_without_caller_id():
    result = forward_twiml("+15551234567")
    assert "callerId" not in result


@pytest.mark.unit
def test_forward_twiml_with_caller_id():
    result = forward_twiml("+15551234567", caller_id="+15559876543")
    assert 'callerId="+15559876543"' in result


@pytest.mark.unit
def test_forward_twiml_hold_message():
    result = forward_twiml("+15551234567")
    assert "Please hold while we connect your call." in result


@pytest.mark.unit
def test_forward_twiml_xss_in_phone_number():
    result = forward_twiml('<script>alert("x")</script>')
    assert "<script>" not in result
    assert "&lt;script&gt;" in result


@pytest.mark.unit
def test_forward_twiml_xss_in_caller_id():
    result = forward_twiml("+15551234567", caller_id='"><img src=x>')
    assert "<img" not in result
    assert "&lt;img" in result


# -- reject_twiml -------------------------------------------------------------


@pytest.mark.unit
def test_reject_twiml_default_reason():
    result = reject_twiml()
    assert '<Reject reason="rejected"/>' in result


@pytest.mark.unit
def test_reject_twiml_rejected():
    result = reject_twiml("rejected")
    assert 'reason="rejected"' in result


@pytest.mark.unit
def test_reject_twiml_busy():
    result = reject_twiml("busy")
    assert 'reason="busy"' in result


@pytest.mark.unit
def test_reject_twiml_invalid_reason_defaults_to_rejected():
    result = reject_twiml("invalid-reason")
    assert 'reason="rejected"' in result


@pytest.mark.unit
def test_reject_twiml_empty_string_defaults_to_rejected():
    result = reject_twiml("")
    assert 'reason="rejected"' in result


@pytest.mark.unit
def test_reject_twiml_response_wrapper():
    result = reject_twiml()
    assert "<Response>" in result
    assert "</Response>" in result


# -- voicemail_twiml ----------------------------------------------------------


@pytest.mark.unit
def test_voicemail_twiml_record_element():
    result = voicemail_twiml("/recording-complete")
    assert "<Record" in result


@pytest.mark.unit
def test_voicemail_twiml_finish_on_key():
    result = voicemail_twiml("/recording-complete")
    assert 'finishOnKey="#"' in result


@pytest.mark.unit
def test_voicemail_twiml_action_url():
    result = voicemail_twiml("/recording-complete")
    assert 'action="/recording-complete"' in result


@pytest.mark.unit
def test_voicemail_twiml_method_post():
    result = voicemail_twiml("/recording-complete")
    assert 'method="POST"' in result


@pytest.mark.unit
def test_voicemail_twiml_default_max_length():
    result = voicemail_twiml("/done")
    assert 'maxLength="120"' in result


@pytest.mark.unit
def test_voicemail_twiml_custom_max_length():
    result = voicemail_twiml("/done", max_length=60)
    assert 'maxLength="60"' in result


@pytest.mark.unit
def test_voicemail_twiml_prompt_message():
    result = voicemail_twiml("/done")
    assert "Please leave your message after the tone" in result
    assert "Press pound when finished" in result


@pytest.mark.unit
def test_voicemail_twiml_xss_in_url():
    result = voicemail_twiml('/done"><script>alert(1)</script>')
    assert "<script>" not in result
    assert "&quot;" in result


# -- hold_twiml ---------------------------------------------------------------


@pytest.mark.unit
def test_hold_twiml_default_message():
    result = hold_twiml()
    assert "Please hold while we process your call." in result


@pytest.mark.unit
def test_hold_twiml_custom_message():
    result = hold_twiml(message="Hang tight!")
    assert "Hang tight!" in result


@pytest.mark.unit
def test_hold_twiml_default_uses_say_and_play():
    result = hold_twiml()
    assert "<Say" in result
    assert "<Play" in result


@pytest.mark.unit
def test_hold_twiml_default_loop_attribute():
    result = hold_twiml()
    assert 'loop="10"' in result


@pytest.mark.unit
def test_hold_twiml_default_fallback_music():
    result = hold_twiml()
    assert "https://api.twilio.com/cowbell.mp3" in result


@pytest.mark.unit
def test_hold_twiml_with_music_url():
    result = hold_twiml(music_url="https://example.com/hold.mp3")
    assert "https://example.com/hold.mp3" in result
    assert 'loop="10"' in result


@pytest.mark.unit
def test_hold_twiml_with_music_url_no_say():
    result = hold_twiml(music_url="https://example.com/hold.mp3")
    assert "<Say" not in result


@pytest.mark.unit
def test_hold_twiml_xss_in_message():
    result = hold_twiml(message='<img onerror="alert(1)">')
    assert "<img" not in result
    assert "&lt;img" in result


# -- screening_twiml ----------------------------------------------------------


@pytest.mark.unit
def test_screening_twiml_say_element():
    result = screening_twiml("Screening your call", "wss://stream.example.com")
    assert "<Say" in result
    assert "Screening your call" in result


@pytest.mark.unit
def test_screening_twiml_connect_stream_structure():
    result = screening_twiml("Hello", "wss://stream.example.com")
    assert "<Connect>" in result
    assert "</Connect>" in result
    assert "<Stream" in result


@pytest.mark.unit
def test_screening_twiml_stream_url():
    result = screening_twiml("Hello", "wss://stream.example.com/ws")
    assert 'url="wss://stream.example.com/ws"' in result


@pytest.mark.unit
def test_screening_twiml_bidirectional():
    result = screening_twiml("Hello", "wss://stream.example.com")
    assert 'bidirectional="true"' in result


@pytest.mark.unit
def test_screening_twiml_xss_in_stream_url():
    result = screening_twiml("Hello", 'wss://evil.com"><script>x</script>')
    assert "<script>" not in result
    assert "&quot;" in result


@pytest.mark.unit
def test_screening_twiml_xss_in_message():
    result = screening_twiml("Hello & <goodbye>", "wss://stream.example.com")
    assert "&amp;" in result
    assert "&lt;goodbye&gt;" in result


# -- emergency_forward_twiml --------------------------------------------------


@pytest.mark.unit
def test_emergency_forward_twiml_dial_element():
    result = emergency_forward_twiml("+15551234567")
    assert "<Dial" in result
    assert "</Dial>" in result


@pytest.mark.unit
def test_emergency_forward_twiml_phone_number():
    result = emergency_forward_twiml("+15551234567")
    assert "<Number>+15551234567</Number>" in result


@pytest.mark.unit
def test_emergency_forward_twiml_no_say():
    result = emergency_forward_twiml("+15551234567")
    assert "<Say" not in result


@pytest.mark.unit
def test_emergency_forward_twiml_timeout():
    result = emergency_forward_twiml("+15551234567")
    assert 'timeout="30"' in result


@pytest.mark.unit
def test_emergency_forward_twiml_minimal_response():
    """Emergency forwarding must be minimal -- Dial only, no extra elements."""
    result = emergency_forward_twiml("+15551234567")
    assert "<Gather" not in result
    assert "<Record" not in result
    assert "<Hangup" not in result
    assert "<Play" not in result


@pytest.mark.unit
def test_emergency_forward_twiml_xss_in_number():
    result = emergency_forward_twiml('<script>alert("x")</script>')
    assert "<script>" not in result
    assert "&lt;script&gt;" in result
