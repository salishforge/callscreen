"""Number intelligence response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class NumberIntelResponse(BaseModel):
    """API response schema for number intelligence data."""

    id: uuid.UUID
    phone_number: str
    carrier_name: str | None = None
    line_type: str = "unknown"
    cnam: str | None = None
    nomorobo_score: int | None = None
    ftc_complaint_count: int | None = None
    stir_attestation: str | None = None
    is_medical_provider: bool = False
    medical_provider_name: str | None = None
    community_blocklist_hit: bool = False
    composite_trust_score: float | None = None
    call_count: int = 0
    last_seen: datetime | None = None
    last_updated: datetime | None = None

    model_config = {"from_attributes": True}
