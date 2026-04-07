"""Message management endpoints."""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from callscreen.db.session import get_db
from callscreen.messaging.adapters.base import DeliveryResult
from callscreen.messaging.delivery_service import deliver_message_to_channel
from callscreen.models.message import Message
from callscreen.schemas.message import MessageDetailResponse, MessageListResponse
from callscreen.security.auth import get_current_user

logger = logging.getLogger("callscreen.api.messages")

router = APIRouter()


class ForwardRequest(BaseModel):
    """Body for the manual-forward endpoint."""

    channel: str
    recipient: str


class ForwardResponse(BaseModel):
    success: bool
    channel: str
    recipient: str
    error: str | None = None


class UnreadCountResponse(BaseModel):
    count: int


@router.get("/unread/count", response_model=UnreadCountResponse)
async def unread_count(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return the count of unread messages for the current user."""
    result = await db.execute(
        select(func.count())
        .select_from(Message)
        .where(
            Message.user_id == current_user.id,
            Message.read_at.is_(None),
        )
    )
    count = result.scalar() or 0
    return UnreadCountResponse(count=count)


@router.get("", response_model=MessageListResponse)
async def list_messages(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    priority: str | None = Query(None, pattern="^(urgent|normal|low)$"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List messages for the current user."""
    offset = (page - 1) * per_page
    query = (
        select(Message)
        .where(Message.user_id == current_user.id)
        .order_by(Message.created_at.desc())
    )
    if priority:
        query = query.where(Message.priority == priority)
    query = query.offset(offset).limit(per_page)

    result = await db.execute(query)
    messages = result.scalars().all()

    return MessageListResponse(
        messages=[MessageDetailResponse.model_validate(m) for m in messages],
        page=page,
        per_page=per_page,
    )


@router.get("/{message_id}", response_model=MessageDetailResponse)
async def get_message(
    message_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get message detail."""
    result = await db.execute(
        select(Message).where(
            Message.id == message_id,
            Message.user_id == current_user.id,
        )
    )
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    return MessageDetailResponse.model_validate(message)


@router.post("/{message_id}/forward", response_model=ForwardResponse)
async def forward_message(
    message_id: str,
    body: ForwardRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Manually forward a message to a specific channel and recipient."""
    result = await db.execute(
        select(Message).where(
            Message.id == message_id,
            Message.user_id == current_user.id,
        )
    )
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    delivery_result: DeliveryResult = await deliver_message_to_channel(
        message=message,
        channel=body.channel,
        recipient=body.recipient,
        db=db,
    )

    return ForwardResponse(
        success=delivery_result.success,
        channel=delivery_result.channel,
        recipient=delivery_result.recipient,
        error=delivery_result.error,
    )


@router.patch("/{message_id}/read")
async def mark_read(
    message_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Mark a message as read."""
    result = await db.execute(
        select(Message).where(
            Message.id == message_id,
            Message.user_id == current_user.id,
        )
    )
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    message.read_at = datetime.now(UTC)  # type: ignore[assignment]
    await db.flush()
    return {"status": "ok"}
