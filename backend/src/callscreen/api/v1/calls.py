"""Call management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from callscreen.db.session import get_db
from callscreen.models.call import CallRecord
from callscreen.schemas.call import CallDetailResponse, CallListResponse
from callscreen.security.auth import get_current_user

router = APIRouter()


@router.get("", response_model=CallListResponse)
async def list_calls(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List calls for the current user."""
    offset = (page - 1) * per_page
    query = (
        select(CallRecord)
        .where(CallRecord.user_id == current_user.id)
        .order_by(CallRecord.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    result = await db.execute(query)
    calls = result.scalars().all()

    return CallListResponse(
        calls=[CallDetailResponse.model_validate(c) for c in calls],
        page=page,
        per_page=per_page,
    )


@router.get("/{call_id}", response_model=CallDetailResponse)
async def get_call(
    call_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get call detail with transcript and summary."""
    result = await db.execute(
        select(CallRecord).where(
            CallRecord.id == call_id,
            CallRecord.user_id == current_user.id,
        )
    )
    call = result.scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    return CallDetailResponse.model_validate(call)
