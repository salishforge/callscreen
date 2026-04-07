"""Message schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class MessageDetailResponse(BaseModel):
    id: uuid.UUID
    call_id: uuid.UUID
    content: str
    summary: str | None = None
    priority: str
    category: str
    delivery_status: str
    delivered_via: str | None = None
    delivered_at: datetime | None = None
    read_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageListResponse(BaseModel):
    messages: list[MessageDetailResponse]
    page: int
    per_page: int


class MessageCreateInternal(BaseModel):
    """Used by internal services to create messages (not exposed via API)."""

    call_id: uuid.UUID
    user_id: uuid.UUID
    content: str
    summary: str | None = None
    priority: str = "normal"
    category: str = "other"
    audio_ref: str | None = None


class DeliveryStatusResponse(BaseModel):
    """Delivery tracking information for a single delivery attempt."""

    id: uuid.UUID
    message_id: uuid.UUID
    channel: str
    recipient: str
    status: str
    error_message: str | None = None
    sent_at: datetime | None = None
    delivered_at: datetime | None = None

    model_config = {"from_attributes": True}
