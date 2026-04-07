"""Deepgram Nova-2 STT provider implementation."""

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from deepgram import AsyncDeepgramClient

from callscreen.voice.stt.base import STTProvider, TranscriptResult, TranscriptSegment

logger = logging.getLogger("callscreen.voice.stt.deepgram")

# Mapping from common MIME types to Deepgram encoding names
_MIME_TO_ENCODING: dict[str, str] = {
    "audio/mulaw": "mulaw",
    "audio/x-mulaw": "mulaw",
    "audio/basic": "mulaw",
    "audio/l16": "linear16",
    "audio/x-raw": "linear16",
}


class DeepgramSTTProvider(STTProvider):
    """Speech-to-text using Deepgram Nova-2 via the official SDK.

    Supports both streaming (WebSocket) and batch (file) transcription.
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = AsyncDeepgramClient(api_key=api_key)

    # ------------------------------------------------------------------
    # Streaming transcription
    # ------------------------------------------------------------------

    async def transcribe_stream(
        self, audio_stream: AsyncIterator[bytes]
    ) -> AsyncIterator[TranscriptSegment]:
        """Open a Deepgram WebSocket and stream audio chunks through it.

        Uses nova-2, en-US, smart_format, punctuation enabled, diarize off.
        Yields TranscriptSegment objects as results arrive.
        """
        segments: asyncio.Queue[TranscriptSegment | None] = asyncio.Queue()
        error_holder: list[Exception] = []

        try:
            async for socket_client in self._client.listen.v1.connect(
                model="nova-2",
                language="en-US",
                smart_format=True,
                punctuate=True,
                diarize=False,
                encoding="mulaw",
                sample_rate=8000,
                channels=1,
                interim_results=True,
            ):
                # Register event handlers ---------------------------------
                from deepgram.core.events import EventType

                def _on_message(result: Any) -> None:
                    try:
                        channel = result.channel
                        if not channel or not channel.alternatives:
                            return
                        alt = channel.alternatives[0]
                        text = alt.transcript or ""
                        if not text.strip():
                            return
                        segment = TranscriptSegment(
                            text=text,
                            confidence=alt.confidence if alt.confidence is not None else 0.0,
                            is_final=bool(result.is_final),
                            start_time=float(result.start) if result.start else 0.0,
                            end_time=(
                                float(result.start) + float(result.duration)
                                if result.start is not None and result.duration is not None
                                else 0.0
                            ),
                        )
                        segments.put_nowait(segment)
                    except Exception:
                        logger.exception("Error processing Deepgram streaming result")

                def _on_error(error: Any) -> None:
                    logger.error("Deepgram streaming error: %s", error)
                    error_holder.append(
                        RuntimeError(f"Deepgram streaming error: {error}")
                    )
                    segments.put_nowait(None)

                def _on_close(_: Any) -> None:
                    segments.put_nowait(None)

                socket_client.on(EventType.MESSAGE, _on_message)
                socket_client.on(EventType.ERROR, _on_error)
                socket_client.on(EventType.CLOSE, _on_close)

                await socket_client.start_listening()

                # Feed audio in a background task
                async def _feed_audio() -> None:
                    try:
                        async for chunk in audio_stream:
                            if chunk:
                                socket_client.send_media(chunk)
                    except Exception:
                        logger.exception("Error feeding audio to Deepgram")
                    finally:
                        try:
                            socket_client.send_close_stream()
                        except Exception:
                            logger.debug("Error sending close stream", exc_info=True)

                feed_task = asyncio.create_task(_feed_audio())

                try:
                    while True:
                        segment = await segments.get()
                        if segment is None:
                            break
                        yield segment
                finally:
                    feed_task.cancel()
                    try:
                        await feed_task
                    except asyncio.CancelledError:
                        pass

                if error_holder:
                    raise error_holder[0]

                # Only use the first connection from the async iterator
                break

        except Exception:
            logger.exception("Deepgram streaming transcription failed")
            raise

    # ------------------------------------------------------------------
    # Batch transcription
    # ------------------------------------------------------------------

    async def transcribe_file(
        self, audio_data: bytes, mime_type: str
    ) -> TranscriptResult:
        """Transcribe a complete audio file using Deepgram batch API.

        Uses nova-2, en-US, smart_format, punctuation, utterances for segments.
        """
        if not audio_data:
            return TranscriptResult(
                full_text="",
                segments=[],
                language="en",
                duration_seconds=0.0,
            )

        encoding = _MIME_TO_ENCODING.get(mime_type)

        kwargs: dict[str, Any] = {
            "request": audio_data,
            "model": "nova-2",
            "language": "en-US",
            "smart_format": True,
            "punctuate": True,
            "diarize": False,
            "utterances": True,
        }
        if encoding:
            kwargs["encoding"] = encoding
            if encoding == "mulaw":
                kwargs["sample_rate"] = 8000

        max_retries = 3
        last_error: Exception | None = None

        for attempt in range(max_retries):
            try:
                response = await self._client.listen.v1.media.transcribe_file(**kwargs)
                return self._parse_batch_response(response)
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Deepgram batch transcription attempt %d/%d failed: %s",
                    attempt + 1,
                    max_retries,
                    exc,
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5 * (2**attempt))

        raise RuntimeError(
            f"Deepgram batch transcription failed after {max_retries} attempts"
        ) from last_error

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_batch_response(response: Any) -> TranscriptResult:
        """Convert Deepgram batch API response to our TranscriptResult model."""
        duration = float(response.metadata.duration) if response.metadata else 0.0
        language = "en"

        segments: list[TranscriptSegment] = []
        full_texts: list[str] = []

        channels = response.results.channels if response.results else []
        for channel in channels:
            if channel.detected_language:
                language = channel.detected_language

            alternatives = channel.alternatives or []
            if not alternatives:
                continue
            alt = alternatives[0]
            transcript = alt.transcript or ""
            if transcript:
                full_texts.append(transcript)

            words = alt.words or []
            if words:
                confidence = alt.confidence if alt.confidence is not None else 0.0
                start_time = float(words[0].start) if hasattr(words[0], "start") else 0.0
                end_time = float(words[-1].end) if hasattr(words[-1], "end") else 0.0
                segments.append(
                    TranscriptSegment(
                        text=transcript,
                        confidence=confidence,
                        is_final=True,
                        start_time=start_time,
                        end_time=end_time,
                    )
                )

        return TranscriptResult(
            full_text=" ".join(full_texts),
            segments=segments,
            language=language,
            duration_seconds=duration,
        )
