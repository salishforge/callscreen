"""Tests for configurable call forwarding."""

import pytest

from callscreen.config import Settings
from callscreen.core.twiml import (
    forward_sip_twiml,
    forward_twiml,
    simultaneous_ring_twiml,
)
from callscreen.models.settings import ForwardMode, UserSettings
from callscreen.api.v1.webhooks import _build_forward_twiml, _build_emergency_forward_twiml


# =============================================================================
# TwiML Builder Tests — forward_sip_twiml
# =============================================================================


@pytest.mark.unit
def test_forward_sip_twiml_sip_element():
    result = forward_sip_twiml("sip:user@pbx.local")
    assert "<Sip>sip:user@pbx.local</Sip>" in result


@pytest.mark.unit
def test_forward_sip_twiml_dial_wrapper():
    result = forward_sip_twiml("sip:user@pbx.local")
    assert "<Dial" in result
    assert "</Dial>" in result


@pytest.mark.unit
def test_forward_sip_twiml_default_timeout():
    result = forward_sip_twiml("sip:user@pbx.local")
    assert 'timeout="30"' in result


@pytest.mark.unit
def test_forward_sip_twiml_custom_timeout():
    result = forward_sip_twiml("sip:user@pbx.local", timeout=45)
    assert 'timeout="45"' in result


@pytest.mark.unit
def test_forward_sip_twiml_without_caller_id():
    result = forward_sip_twiml("sip:user@pbx.local")
    assert "callerId" not in result


@pytest.mark.unit
def test_forward_sip_twiml_with_caller_id():
    result = forward_sip_twiml("sip:user@pbx.local", caller_id="+15551234567")
    assert 'callerId="+15551234567"' in result


@pytest.mark.unit
def test_forward_sip_twiml_hold_message():
    result = forward_sip_twiml("sip:user@pbx.local")
    assert "Please hold while we connect your call." in result


@pytest.mark.unit
def test_forward_sip_twiml_xss_in_uri():
    result = forward_sip_twiml('sip:"><script>alert(1)</script>')
    assert "<script>" not in result
    assert "&quot;" in result


# =============================================================================
# TwiML Builder Tests — simultaneous_ring_twiml
# =============================================================================


@pytest.mark.unit
def test_simultaneous_ring_twiml_multiple_numbers():
    result = simultaneous_ring_twiml(["+15551111111", "+15552222222"])
    assert "<Number>+15551111111</Number>" in result
    assert "<Number>+15552222222</Number>" in result


@pytest.mark.unit
def test_simultaneous_ring_twiml_with_sip():
    result = simultaneous_ring_twiml(["+15551111111"], sip_uri="sip:user@pbx.local")
    assert "<Number>+15551111111</Number>" in result
    assert "<Sip>sip:user@pbx.local</Sip>" in result


@pytest.mark.unit
def test_simultaneous_ring_twiml_sip_only():
    result = simultaneous_ring_twiml([], sip_uri="sip:user@pbx.local")
    assert "<Number>" not in result
    assert "<Sip>sip:user@pbx.local</Sip>" in result


@pytest.mark.unit
def test_simultaneous_ring_twiml_default_timeout():
    result = simultaneous_ring_twiml(["+15551111111"])
    assert 'timeout="30"' in result


@pytest.mark.unit
def test_simultaneous_ring_twiml_custom_timeout():
    result = simultaneous_ring_twiml(["+15551111111"], timeout=60)
    assert 'timeout="60"' in result


@pytest.mark.unit
def test_simultaneous_ring_twiml_with_caller_id():
    result = simultaneous_ring_twiml(["+15551111111"], caller_id="+15559999999")
    assert 'callerId="+15559999999"' in result


@pytest.mark.unit
def test_simultaneous_ring_twiml_hold_message():
    result = simultaneous_ring_twiml(["+15551111111"])
    assert "Please hold while we connect your call." in result


# =============================================================================
# Config Property Tests
# =============================================================================


@pytest.mark.unit
def test_config_forward_destination_defaults_to_twilio_number():
    settings = Settings(
        twilio_phone_number="+18001234567",
        callscreen_forward_number="",
        callscreen_forward_sip_uri="",
    )
    assert settings.forward_destination == "+18001234567"


@pytest.mark.unit
def test_config_forward_destination_prefers_explicit_number():
    settings = Settings(
        twilio_phone_number="+18001234567",
        callscreen_forward_number="+15559876543",
        callscreen_forward_sip_uri="",
    )
    assert settings.forward_destination == "+15559876543"


@pytest.mark.unit
def test_config_forward_destination_prefers_sip():
    settings = Settings(
        twilio_phone_number="+18001234567",
        callscreen_forward_number="+15559876543",
        callscreen_forward_sip_uri="sip:user@pbx.local",
    )
    assert settings.forward_destination == "sip:user@pbx.local"


@pytest.mark.unit
def test_config_simultaneous_ring_empty():
    settings = Settings(callscreen_simultaneous_ring="")
    assert settings.simultaneous_ring_numbers == []


@pytest.mark.unit
def test_config_simultaneous_ring_parses():
    settings = Settings(
        callscreen_simultaneous_ring="+15551111111,+15552222222, +15553333333"
    )
    assert settings.simultaneous_ring_numbers == [
        "+15551111111",
        "+15552222222",
        "+15553333333",
    ]


# =============================================================================
# _build_forward_twiml — Resolution Logic
# =============================================================================


def _make_settings(**overrides) -> Settings:
    """Build a Settings object with defaults for testing."""
    defaults = dict(
        twilio_phone_number="+18001234567",
        callscreen_forward_number="",
        callscreen_forward_sip_uri="",
        callscreen_forward_timeout=30,
        callscreen_simultaneous_ring="",
    )
    defaults.update(overrides)
    return Settings(**defaults)


class _FakeUserSettings:
    """Lightweight stand-in for UserSettings that doesn't need SQLAlchemy instrumentation."""

    def __init__(self, **kwargs):
        defaults = dict(
            forward_mode=ForwardMode.PHONE.value,
            forward_phone_number="",
            forward_sip_uri="",
            forward_timeout=30,
            simultaneous_ring_numbers="",
            greeting_message="",
        )
        defaults.update(kwargs)
        for k, v in defaults.items():
            self.__dict__[k] = v


def _make_user_settings(**overrides):
    """Build a fake UserSettings for testing forwarding logic."""
    return _FakeUserSettings(**overrides)


@pytest.mark.unit
def test_build_forward_no_user_settings_uses_app_config():
    """No user settings -> falls back to app-level CALLSCREEN_FORWARD_NUMBER."""
    app = _make_settings(callscreen_forward_number="+15559999999")
    twiml = _build_forward_twiml(None, app)
    assert "<Number>+15559999999</Number>" in twiml


@pytest.mark.unit
def test_build_forward_no_user_settings_falls_back_to_twilio_number():
    """No user settings, no app-level forward -> falls back to twilio_phone_number."""
    app = _make_settings()
    twiml = _build_forward_twiml(None, app)
    assert "<Number>+18001234567</Number>" in twiml


@pytest.mark.unit
def test_build_forward_user_phone_overrides_app():
    """Per-user forward_phone_number takes priority over app-level."""
    app = _make_settings(callscreen_forward_number="+15559999999")
    us = _make_user_settings(forward_phone_number="+15551111111")
    twiml = _build_forward_twiml(us, app)
    assert "<Number>+15551111111</Number>" in twiml


@pytest.mark.unit
def test_build_forward_sip_mode():
    """SIP mode uses <Sip> element."""
    app = _make_settings()
    us = _make_user_settings(
        forward_mode=ForwardMode.SIP.value,
        forward_sip_uri="sip:extension@unifi.local",
    )
    twiml = _build_forward_twiml(us, app)
    assert "<Sip>sip:extension@unifi.local</Sip>" in twiml
    assert "<Number>" not in twiml


@pytest.mark.unit
def test_build_forward_sip_falls_back_to_app_sip():
    """SIP mode with empty user SIP URI falls back to app-level."""
    app = _make_settings(callscreen_forward_sip_uri="sip:default@pbx.local")
    us = _make_user_settings(forward_mode=ForwardMode.SIP.value, forward_sip_uri="")
    twiml = _build_forward_twiml(us, app)
    assert "<Sip>sip:default@pbx.local</Sip>" in twiml


@pytest.mark.unit
def test_build_forward_simultaneous_mode():
    """Simultaneous mode rings multiple numbers."""
    app = _make_settings()
    us = _make_user_settings(
        forward_mode=ForwardMode.SIMULTANEOUS.value,
        forward_phone_number="+15551111111",
        simultaneous_ring_numbers="+15552222222,+15553333333",
    )
    twiml = _build_forward_twiml(us, app)
    assert "<Number>+15551111111</Number>" in twiml
    assert "<Number>+15552222222</Number>" in twiml
    assert "<Number>+15553333333</Number>" in twiml


@pytest.mark.unit
def test_build_forward_simultaneous_with_sip():
    """Simultaneous mode can mix phone numbers and SIP."""
    app = _make_settings()
    us = _make_user_settings(
        forward_mode=ForwardMode.SIMULTANEOUS.value,
        forward_phone_number="+15551111111",
        forward_sip_uri="sip:user@pbx.local",
    )
    twiml = _build_forward_twiml(us, app)
    assert "<Number>+15551111111</Number>" in twiml
    assert "<Sip>sip:user@pbx.local</Sip>" in twiml


@pytest.mark.unit
def test_build_forward_custom_timeout():
    """Per-user timeout overrides default."""
    app = _make_settings()
    us = _make_user_settings(forward_phone_number="+15551111111", forward_timeout=45)
    twiml = _build_forward_twiml(us, app)
    assert 'timeout="45"' in twiml


@pytest.mark.unit
def test_build_forward_caller_id_passthrough():
    """Caller ID is passed through to TwiML."""
    app = _make_settings()
    us = _make_user_settings(forward_phone_number="+15551111111")
    twiml = _build_forward_twiml(us, app, caller_id="+15559876543")
    assert 'callerId="+15559876543"' in twiml


# =============================================================================
# _build_emergency_forward_twiml — Safety Tests
# =============================================================================


@pytest.mark.unit
def test_emergency_forward_uses_user_phone():
    """Emergency forward uses user's configured phone."""
    app = _make_settings(callscreen_forward_number="+15559999999")
    us = _make_user_settings(forward_phone_number="+15551111111")
    twiml = _build_emergency_forward_twiml(us, app)
    assert "<Number>+15551111111</Number>" in twiml


@pytest.mark.unit
def test_emergency_forward_falls_back_to_app_number():
    """Emergency forward falls back to app-level when no user config."""
    app = _make_settings(callscreen_forward_number="+15559999999")
    twiml = _build_emergency_forward_twiml(None, app)
    assert "<Number>+15559999999</Number>" in twiml


@pytest.mark.unit
def test_emergency_forward_falls_back_to_twilio_number():
    """Emergency forward falls back to Twilio number as last resort."""
    app = _make_settings()
    twiml = _build_emergency_forward_twiml(None, app)
    assert "<Number>+18001234567</Number>" in twiml


@pytest.mark.unit
def test_emergency_forward_never_uses_sip():
    """Emergency forwarding must use PSTN, never SIP (reliability)."""
    app = _make_settings()
    us = _make_user_settings(
        forward_mode=ForwardMode.SIP.value,
        forward_sip_uri="sip:user@pbx.local",
        forward_phone_number="+15551111111",
    )
    twiml = _build_emergency_forward_twiml(us, app)
    assert "<Number>+15551111111</Number>" in twiml
    assert "<Sip>" not in twiml


# =============================================================================
# Schema Validation Tests
# =============================================================================


@pytest.mark.unit
def test_settings_update_validates_forward_mode():
    from callscreen.schemas.settings import SettingsUpdate

    with pytest.raises(Exception):
        SettingsUpdate(forward_mode="invalid_mode")


@pytest.mark.unit
def test_settings_update_accepts_valid_modes():
    from callscreen.schemas.settings import SettingsUpdate

    for mode in ("phone", "sip", "simultaneous"):
        s = SettingsUpdate(forward_mode=mode)
        assert s.forward_mode == mode


@pytest.mark.unit
def test_settings_update_validates_phone_e164():
    from callscreen.schemas.settings import SettingsUpdate

    with pytest.raises(Exception):
        SettingsUpdate(forward_phone_number="5551234567")  # Missing +


@pytest.mark.unit
def test_settings_update_accepts_e164():
    from callscreen.schemas.settings import SettingsUpdate

    s = SettingsUpdate(forward_phone_number="+15551234567")
    assert s.forward_phone_number == "+15551234567"


@pytest.mark.unit
def test_settings_update_validates_sip_prefix():
    from callscreen.schemas.settings import SettingsUpdate

    with pytest.raises(Exception):
        SettingsUpdate(forward_sip_uri="user@pbx.local")  # Missing sip:


@pytest.mark.unit
def test_settings_update_accepts_sip_uri():
    from callscreen.schemas.settings import SettingsUpdate

    s = SettingsUpdate(forward_sip_uri="sip:user@pbx.local")
    assert s.forward_sip_uri == "sip:user@pbx.local"


@pytest.mark.unit
def test_settings_update_validates_timeout_range():
    from callscreen.schemas.settings import SettingsUpdate

    with pytest.raises(Exception):
        SettingsUpdate(forward_timeout=3)  # Too low

    with pytest.raises(Exception):
        SettingsUpdate(forward_timeout=200)  # Too high


@pytest.mark.unit
def test_settings_update_accepts_valid_timeout():
    from callscreen.schemas.settings import SettingsUpdate

    s = SettingsUpdate(forward_timeout=45)
    assert s.forward_timeout == 45


@pytest.mark.unit
def test_settings_update_allows_empty_forward_phone():
    """Empty string resets forwarding to default."""
    from callscreen.schemas.settings import SettingsUpdate

    s = SettingsUpdate(forward_phone_number="")
    assert s.forward_phone_number == ""


@pytest.mark.unit
def test_settings_update_allows_empty_sip_uri():
    """Empty string resets SIP forwarding."""
    from callscreen.schemas.settings import SettingsUpdate

    s = SettingsUpdate(forward_sip_uri="")
    assert s.forward_sip_uri == ""
