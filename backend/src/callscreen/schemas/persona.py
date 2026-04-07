"""Persona request/response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class EngagementRules(BaseModel):
    min_trust_score: float = 0.0
    max_trust_score: float = 0.2
    target_duration_seconds: int = 300
    max_duration_seconds: int = 600


class PersonaCreate(BaseModel):
    name: str = Field(..., max_length=100)
    description: str = ""
    system_prompt: str
    voice_id: str = ""
    speech_rate: float = 1.0
    engagement_rules: EngagementRules | None = None


class PersonaUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    voice_id: str | None = None
    speech_rate: float | None = None
    is_active: bool | None = None
    engagement_rules: EngagementRules | None = None


class PersonaResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    system_prompt: str
    voice_id: str
    speech_rate: float
    is_builtin: bool
    is_active: bool
    engagement_rules: dict | None = None
    created_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
