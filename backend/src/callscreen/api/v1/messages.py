"""Message management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from callscreen.db.session import get_db
from callscreen.models.message import Message
from callscreen.schemas.message import MessageDetailResponse, MessageListResponse
from callscreen.security.auth import get_current_user

router = APIRouter()


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


@router.patch("/{message_id}/read")
async def mark_read(
    message_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Mark a message as read."""
    from datetime import UTC, datetime

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
