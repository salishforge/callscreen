"""User settings schemas."""

from pydantic import BaseModel


class SettingsResponse(BaseModel):
    preferred_channel: str = "email"
    greeting_message: str = ""
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    quiet_hours_timezone: str = "America/New_York"
    caretaker_fork_enabled: bool = False
    caretaker_fork_priority: str = "urgent"
    persona_preferences: dict | None = None
    screening_strictness: str = "moderate"

    model_config = {"from_attributes": True}


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
