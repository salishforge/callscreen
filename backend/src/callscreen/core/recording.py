"""Recording processing flow.

Downloads Twilio recordings, encrypts them, uploads to S3, and
optionally transcribes and summarizes via STT/LLM.
"""

import logging

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from callscreen.ai.llm import summarize_voicemail
from callscreen.config import get_settings
from callscreen.core.storage import upload_recording
from callscreen.models.call import CallRecord

logger = logging.getLogger("callscreen.recording")


async def process_twilio_recording(
    call_sid: str,
    recording_url: str,
    recording_sid: str,
    db: AsyncSession,
) -> str:
    """Download a Twilio recording, encrypt, upload to S3, update DB.

    Args:
        call_sid: Twilio Call SID.
        recording_url: URL to fetch the recording from Twilio.
        recording_sid: Twilio Recording SID.
        db: Async database session.

    Returns:
        The S3 object key where the recording was stored.

    Raises:
        httpx.HTTPStatusError: If the Twilio download fails.
        Exception: For any other unexpected errors.
    """
    settings = get_settings()

    # 1. Download recording from Twilio
    download_url = f"{recording_url}.wav"
    logger.info(
        "Downloading recording: call_sid=%s recording_sid=%s url=%s",
        call_sid,
        recording_sid,
        download_url,
    )

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            auth = settings.twilio_api_credentials
            response = await client.get(download_url, auth=auth)
            response.raise_for_status()
            audio_data = response.content
    except httpx.HTTPStatusError as e:
        logger.error(
            "Failed to download recording %s: HTTP %d",
            recording_sid,
            e.response.status_code,
        )
        raise
    except Exception:
        logger.exception("Unexpected error downloading recording %s", recording_sid)
        raise

    logger.info(
        "Downloaded recording: recording_sid=%s size=%d bytes",
        recording_sid,
        len(audio_data),
    )

    # 2. Upload to S3 (encrypted by default)
    try:
        s3_key = upload_recording(
            call_sid=call_sid,
            audio_data=audio_data,
            content_type="audio/wav",
            encrypt=True,
        )
    except Exception:
        logger.exception("Failed to upload recording to S3 for call_sid=%s", call_sid)
        raise

    logger.info(
        "Uploaded recording to S3: call_sid=%s key=%s",
        call_sid,
        s3_key,
    )

    # 3. Update CallRecord in the database
    try:
        result = await db.execute(
            select(CallRecord).where(CallRecord.call_sid == call_sid).limit(1)
        )
        call_record = result.scalar_one_or_none()
        if call_record:
            call_record.recording_ref = s3_key
            await db.commit()
            logger.info("Updated CallRecord recording_ref for call_sid=%s", call_sid)
        else:
            logger.warning("No CallRecord found for call_sid=%s", call_sid)
    except Exception:
        logger.exception("Failed to update DB for call_sid=%s", call_sid)
        # Don't re-raise: the recording is already in S3, so DB failure
        # should not lose the recording reference.

    # 4. Optionally transcribe and summarize
    await _transcribe_and_summarize(call_sid, audio_data, db)

    return s3_key


async def _transcribe_and_summarize(
    call_sid: str,
    audio_data: bytes,
    db: AsyncSession,
) -> None:
    """Attempt to transcribe and summarize a recording.

    Failures are logged but do not propagate -- the recording itself
    is already safely stored.
    """
    try:
        from callscreen.voice.stt.deepgram_provider import DeepgramSTTProvider

        stt = DeepgramSTTProvider()
        transcript_result = await stt.transcribe_file(audio_data, "audio/wav")
        transcript_text = transcript_result.full_text
    except Exception:
        logger.info(
            "STT transcription skipped for call_sid=%s (provider unavailable or failed)",
            call_sid,
        )
        return

    if not transcript_text.strip():
        logger.info("Empty transcript for call_sid=%s", call_sid)
        return

    # Save transcript to DB
    try:
        result = await db.execute(
            select(CallRecord).where(CallRecord.call_sid == call_sid).limit(1)
        )
        call_record = result.scalar_one_or_none()
        if call_record:
            call_record.transcript = transcript_text

            # Generate summary
            try:
                summary = await summarize_voicemail(transcript_text)
                call_record.ai_summary = summary
            except Exception:
                logger.info(
                    "Summarization skipped for call_sid=%s", call_sid
                )

            await db.commit()
            logger.info("Saved transcript for call_sid=%s", call_sid)
    except Exception:
        logger.exception(
            "Failed to save transcript to DB for call_sid=%s", call_sid
        )
