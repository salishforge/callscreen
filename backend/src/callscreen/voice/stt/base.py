"""Abstract base class for Speech-to-Text providers."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from pydantic import BaseModel, Field


class TranscriptSegment(BaseModel):
    """A single segment of transcribed speech."""

    text: str = Field(description="Transcribed text for this segment")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0-1")
    is_final: bool = Field(description="Whether this is a final (non-interim) result")
    start_time: float = Field(ge=0.0, description="Start time in seconds")
    end_time: float = Field(ge=0.0, description="End time in seconds")


class TranscriptResult(BaseModel):
    """Complete transcription result for a file or recording."""

    full_text: str = Field(description="Full concatenated transcript text")
    segments: list[TranscriptSegment] = Field(default_factory=list, description="Individual segments")
    language: str = Field(default="en", description="Detected or specified language code")
    duration_seconds: float = Field(ge=0.0, description="Total audio duration in seconds")


class STTProvider(ABC):
    """Abstract base class for STT providers."""

    @abstractmethod
    async def transcribe_stream(
        self, audio_stream: AsyncIterator[bytes]
    ) -> AsyncIterator[TranscriptSegment]:
        """Transcribe a stream of audio chunks in real time.

        Args:
            audio_stream: Async iterator yielding raw audio bytes.

        Yields:
            TranscriptSegment for each recognized utterance (interim and final).
        """
        ...  # pragma: no cover

    @abstractmethod
    async def transcribe_file(
        self, audio_data: bytes, mime_type: str
    ) -> TranscriptResult:
        """Transcribe a complete audio file (batch mode).

        Args:
            audio_data: Raw audio file bytes.
            mime_type: MIME type of the audio (e.g. "audio/wav").

        Returns:
            TranscriptResult with full text and segments.
        """
        ...  # pragma: no cover
