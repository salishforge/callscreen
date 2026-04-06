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
