"""Abstract base class for Text-to-Speech providers."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from pydantic import BaseModel, Field


class AudioResult(BaseModel):
    """Result of a TTS synthesis operation."""

    audio_data: bytes = Field(description="Raw audio bytes")
    mime_type: str = Field(description="MIME type of the audio (e.g. audio/basic)")
    sample_rate: int = Field(gt=0, description="Sample rate in Hz")
    duration_seconds: float = Field(ge=0.0, description="Audio duration in seconds")


class TTSProvider(ABC):
    """Abstract base class for TTS providers."""

    @abstractmethod
    async def synthesize(
        self, text: str, voice_id: str, **kwargs: object
    ) -> AudioResult:
        """Synthesize text to a complete audio buffer.

        Args:
            text: The text to speak.
            voice_id: Provider-specific voice identifier.
            **kwargs: Additional provider-specific options.

        Returns:
            AudioResult with the full audio data.
        """
        ...  # pragma: no cover

    @abstractmethod
    async def stream_synthesize(
        self, text: str, voice_id: str, **kwargs: object
    ) -> AsyncIterator[bytes]:
        """Stream synthesized audio in chunks.

        Args:
            text: The text to speak.
            voice_id: Provider-specific voice identifier.
            **kwargs: Additional provider-specific options.

        Yields:
            Raw audio bytes as they become available.
        """
        ...  # pragma: no cover
