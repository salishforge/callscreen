"""Tests for message templates."""

import pytest

from callscreen.messaging.templates.call_notification import render_call_notification
from callscreen.messaging.templates.urgent_alert import render_urgent_alert
from callscreen.messaging.templates.voicemail_notification import render_voicemail_notification


class TestCallNotificationTemplate:
    """Call notification template tests."""

    def test_basic_render(self):
        result = render_call_notification(
            caller_name="John Doe",
            caller_number="+15551234567",
            intent="schedule appointment",
            trust_score=0.85,
        )
        assert "subject" in result
        assert "text" in result
        assert "html" in result
        assert "John Doe" in result["subject"]
        assert "+15551234567" in result["subject"]

    def test_text_body_content(self):
        result = render_call_notification(
            caller_name="Jane",
            caller_number="+15550000000",
            intent="billing inquiry",
            trust_score=0.6,
            summary="Caller wants to discuss a billing issue.",
            timestamp="2026-04-07 10:30 AM",
        )
        assert "Jane" in result["text"]
        assert "billing inquiry" in result["text"]
        assert "60%" in result["text"]
        assert "billing issue" in result["text"]
        assert "10:30 AM" in result["text"]

    def test_html_body_escapes_special_chars(self):
        result = render_call_notification(
            caller_name="<script>alert('xss')</script>",
            caller_number="+1555",
            intent="test & verify",
            trust_score=0.5,
        )
        assert "<script>" not in result["html"]
        assert "&lt;script&gt;" in result["html"]
        assert "&amp;" in result["html"]

    def test_trust_score_percentage(self):
        result = render_call_notification(
            caller_name="Test",
            caller_number="+1",
            intent="test",
            trust_score=0.0,
        )
        assert "0%" in result["text"]


class TestVoicemailNotificationTemplate:
    """Voicemail notification template tests."""

    def test_basic_render(self):
        result = render_voicemail_notification(
            caller_name="Dr. Smith",
            caller_number="+15559876543",
            summary="Calling about your lab results.",
            duration=125,
        )
        assert "subject" in result
        assert "text" in result
        assert "html" in result
        assert "Dr. Smith" in result["subject"]
        assert "2m 5s" in result["subject"]

    def test_short_duration_format(self):
        result = render_voicemail_notification(
            caller_name="Bob",
            caller_number="+1",
            summary="Quick message.",
            duration=30,
        )
        assert "30s" in result["subject"]
        assert "0m" not in result["subject"]

    def test_audio_url_in_output(self):
        result = render_voicemail_notification(
            caller_name="Caller",
            caller_number="+1",
            summary="Test",
            duration=10,
            audio_url="https://example.com/audio.wav",
        )
        assert "https://example.com/audio.wav" in result["text"]
        assert "Listen to Voicemail" in result["html"]

    def test_html_escapes_summary(self):
        result = render_voicemail_notification(
            caller_name="A",
            caller_number="+1",
            summary="<img src=x onerror=alert(1)>",
            duration=5,
        )
        assert "<img" not in result["html"]
        assert "&lt;img" in result["html"]


class TestUrgentAlertTemplate:
    """Urgent alert template tests."""

    def test_basic_render(self):
        result = render_urgent_alert(
            caller_name="Emergency Contact",
            caller_number="+15551112222",
            reason="Medical appointment callback",
        )
        assert "URGENT" in result["subject"]
        assert "Emergency Contact" in result["subject"]
        assert "Medical appointment callback" in result["subject"]

    def test_text_body_has_urgency_notice(self):
        result = render_urgent_alert(
            caller_name="Test",
            caller_number="+1",
            reason="Family emergency",
            summary="Needs immediate callback.",
        )
        assert "immediate attention" in result["text"]
        assert "Family emergency" in result["text"]
        assert "Needs immediate callback." in result["text"]

    def test_html_has_red_styling(self):
        result = render_urgent_alert(
            caller_name="Test",
            caller_number="+1",
            reason="Test reason",
        )
        assert "#e74c3c" in result["html"]
        assert "URGENT" in result["html"]
