"""User settings schemas."""

from datetime import time
from enum import Enum

from pydantic import BaseModel, field_serializer, field_validator


class ForwardMode(str, Enum):
    """Call forwarding mode."""
    PHONE = "phone"
    SIP = "sip"
    SIMULTANEOUS = "simultaneous"


class SettingsResponse(BaseModel):
    preferred_channel: str = "email"
    greeting_message: str = ""
    quiet_hours_start: time | str | None = None
    quiet_hours_end: time | str | None = None
    quiet_hours_timezone: str = "America/New_York"
    caretaker_fork_enabled: bool = False
    caretaker_fork_priority: str = "urgent"
    persona_preferences: dict | None = None
    screening_strictness: str = "moderate"

    # Call forwarding
    forward_mode: str = ForwardMode.PHONE.value
    forward_phone_number: str = ""
    forward_sip_uri: str = ""
    forward_timeout: int = 30
    simultaneous_ring_numbers: str = ""

    model_config = {"from_attributes": True}

    @field_serializer("quiet_hours_start", "quiet_hours_end")
    @classmethod
    def serialize_time(cls, v: time | str | None) -> str | None:
        if v is None:
            return None
        if isinstance(v, time):
            return v.strftime("%H:%M")
        return v


class SettingsUpdate(BaseModel):
    preferred_channel: str | None = None
    greeting_message: str | None = None
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    quiet_hours_timezone: str | None = None
    caretaker_fork_enabled: bool | None = None
    caretaker_fork_priority: str | None = None
    persona_preferences: dict | None = None
    screening_strictness: str | None = None

    # Call forwarding
    forward_mode: str | None = None
    forward_phone_number: str | None = None
    forward_sip_uri: str | None = None
    forward_timeout: int | None = None
    simultaneous_ring_numbers: str | None = None

    @field_validator("forward_mode")
    @classmethod
    def validate_forward_mode(cls, v: str | None) -> str | None:
        if v is not None:
            valid = {m.value for m in ForwardMode}
            if v not in valid:
                raise ValueError(f"forward_mode must be one of {valid}")
        return v

    @field_validator("forward_phone_number")
    @classmethod
    def validate_forward_phone(cls, v: str | None) -> str | None:
        if v is not None and v != "":
            v = v.strip()
            if not v.startswith("+"):
                raise ValueError("forward_phone_number must be in E.164 format (e.g., +15551234567)")
        return v

    @field_validator("forward_sip_uri")
    @classmethod
    def validate_sip_uri(cls, v: str | None) -> str | None:
        if v is not None and v != "":
            v = v.strip()
            if not v.startswith("sip:"):
                raise ValueError("forward_sip_uri must start with 'sip:' (e.g., sip:user@pbx.local)")
        return v

    @field_validator("forward_timeout")
    @classmethod
    def validate_forward_timeout(cls, v: int | None) -> int | None:
        if v is not None:
            if v < 5 or v > 120:
                raise ValueError("forward_timeout must be between 5 and 120 seconds")
        return v
