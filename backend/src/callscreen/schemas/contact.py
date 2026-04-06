"""Contact schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class ContactCreate(BaseModel):
    phone_number: str
    name: str
    contact_type: str  # whitelist, blocklist, known
    category: str | None = "other"
    notes: str | None = ""


class ContactUpdate(BaseModel):
    phone_number: str | None = None
    name: str | None = None
    contact_type: str | None = None
    category: str | None = None
    trust_override: float | None = None
    notes: str | None = None


class ContactResponse(BaseModel):
    id: uuid.UUID
    phone_number: str
    name: str
    contact_type: str
    category: str
    trust_override: float | None = None
    notes: str
    created_at: datetime

    model_config = {"from_attributes": True}
