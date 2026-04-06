"""Call record schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class CallDetailResponse(BaseModel):
    id: uuid.UUID
    call_sid: str
    from_number: str
    to_number: str
    status: str
    disposition: str | None = None
    trust_score: float | None = None
    stir_attestation: str = "unknown"
    caller_name: str | None = None
    caller_intent: str | None = None
    ai_summary: str | None = None
    duration_seconds: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CallListResponse(BaseModel):
    calls: list[CallDetailResponse]
    page: int
    per_page: int
