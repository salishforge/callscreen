"""Call management endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from callscreen.core.storage import generate_presigned_url
from callscreen.db.session import get_db
from callscreen.models.call import CallRecord
from callscreen.schemas.call import CallDetailResponse, CallListResponse
from callscreen.security.auth import get_current_user

logger = logging.getLogger("callscreen.api.calls")

router = APIRouter()


class TranscriptResponse(BaseModel):
    """Response for the transcript endpoint."""

    call_id: str
    call_sid: str
    transcript: str | None = None
    ai_summary: str | None = None


class RecordingURLResponse(BaseModel):
    """Response for the recording URL endpoint."""

    call_id: str
    call_sid: str
    recording_url: str | None = None
    expires_in: int = 3600


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


@router.get("/{call_id}/transcript", response_model=TranscriptResponse)
async def get_call_transcript(
    call_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get the transcript and AI summary for a call."""
    result = await db.execute(
        select(CallRecord).where(
            CallRecord.id == call_id,
            CallRecord.user_id == current_user.id,
        )
    )
    call = result.scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    return TranscriptResponse(
        call_id=str(call.id),
        call_sid=call.call_sid,
        transcript=call.transcript,
        ai_summary=call.ai_summary,
    )


@router.get("/{call_id}/recording-url", response_model=RecordingURLResponse)
async def get_call_recording_url(
    call_id: str,
    expires_in: int = Query(3600, ge=60, le=86400),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get a presigned S3 URL for recording playback.

    The URL is temporary and expires after the specified duration.
    """
    result = await db.execute(
        select(CallRecord).where(
            CallRecord.id == call_id,
            CallRecord.user_id == current_user.id,
        )
    )
    call = result.scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    if not call.recording_ref:
        raise HTTPException(status_code=404, detail="No recording available for this call")

    try:
        url = generate_presigned_url(call.recording_ref, expires_in=expires_in)
    except Exception:
        logger.exception("Failed to generate presigned URL for call_id=%s", call_id)
        raise HTTPException(
            status_code=500, detail="Failed to generate recording URL"
        )

    return RecordingURLResponse(
        call_id=str(call.id),
        call_sid=call.call_sid,
        recording_url=url,
        expires_in=expires_in,
    )
