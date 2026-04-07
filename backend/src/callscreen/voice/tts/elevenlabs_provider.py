"""ElevenLabs Flash v2.5 TTS provider implementation."""

import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from callscreen.voice.tts.base import AudioResult, TTSProvider

logger = logging.getLogger("callscreen.voice.tts.elevenlabs")

_ELEVENLABS_BASE_URL = "https://api.elevenlabs.io/v1"

# Default voice settings tuned for natural phone speech
_DEFAULT_STABILITY = 0.5
_DEFAULT_SIMILARITY_BOOST = 0.75
_DEFAULT_STYLE = 0.0

# mulaw 8kHz for Twilio compatibility
_OUTPUT_FORMAT = "ulaw_8000"
_SAMPLE_RATE = 8000
_MIME_TYPE = "audio/basic"


class ElevenLabsTTSProvider(TTSProvider):
    """Text-to-speech using ElevenLabs Flash v2.5 via their REST API.

    Outputs mulaw 8kHz audio suitable for direct Twilio media stream injection.
    Uses httpx.AsyncClient for all HTTP requests.
    """

    def __init__(
        self,
        api_key: str,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(timeout=30.0)

    async def close(self) -> None:
        """Close the underlying HTTP client if we own it."""
        if self._owns_client and not self._http.is_closed:
            await self._http.aclose()

    # ------------------------------------------------------------------
    # Full synthesis
    # ------------------------------------------------------------------

    async def synthesize(
        self, text: str, voice_id: str, **kwargs: object
    ) -> AudioResult:
        """Synthesize text to a complete mulaw 8kHz audio buffer."""
        if not text.strip():
            return AudioResult(
                audio_data=b"",
                mime_type=_MIME_TYPE,
                sample_rate=_SAMPLE_RATE,
                duration_seconds=0.0,
            )

        body = self._build_request_body(text, **kwargs)
        url = f"{_ELEVENLABS_BASE_URL}/text-to-speech/{voice_id}"

        try:
            response = await self._http.post(
                url,
                json=body,
                headers=self._headers(),
                params={"output_format": _OUTPUT_FORMAT},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "ElevenLabs synthesis HTTP %s: %s",
                exc.response.status_code,
                exc.response.text[:500],
            )
            raise RuntimeError(
                f"ElevenLabs synthesis failed with status {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            logger.error("ElevenLabs synthesis request error: %s", exc)
            raise RuntimeError("ElevenLabs synthesis request failed") from exc

        audio_data = response.content
        # mulaw 8kHz: 8000 samples/sec, 1 byte per sample
        duration = len(audio_data) / _SAMPLE_RATE if audio_data else 0.0

        return AudioResult(
            audio_data=audio_data,
            mime_type=_MIME_TYPE,
            sample_rate=_SAMPLE_RATE,
            duration_seconds=duration,
        )

    # ------------------------------------------------------------------
    # Streaming synthesis
    # ------------------------------------------------------------------

    async def stream_synthesize(
        self, text: str, voice_id: str, **kwargs: object
    ) -> AsyncIterator[bytes]:
        """Stream synthesized audio chunks from ElevenLabs."""
        if not text.strip():
            return

        body = self._build_request_body(text, **kwargs)
        url = f"{_ELEVENLABS_BASE_URL}/text-to-speech/{voice_id}/stream"

        try:
            async with self._http.stream(
                "POST",
                url,
                json=body,
                headers=self._headers(),
                params={"output_format": _OUTPUT_FORMAT},
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes(chunk_size=1024):
                    if chunk:
                        yield chunk
        except httpx.HTTPStatusError as exc:
            logger.error(
                "ElevenLabs streaming HTTP %s: %s",
                exc.response.status_code,
                exc.response.text[:500],
            )
            raise RuntimeError(
                f"ElevenLabs streaming failed with status {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            logger.error("ElevenLabs streaming request error: %s", exc)
            raise RuntimeError("ElevenLabs streaming request failed") from exc

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "xi-api-key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }

    @staticmethod
    def _build_request_body(text: str, **kwargs: Any) -> dict[str, Any]:
        """Build the JSON body for the ElevenLabs TTS endpoint."""
        stability = kwargs.get("stability", _DEFAULT_STABILITY)
        similarity_boost = kwargs.get("similarity_boost", _DEFAULT_SIMILARITY_BOOST)
        style = kwargs.get("style", _DEFAULT_STYLE)

        return {
            "text": text,
            "model_id": "eleven_flash_v2_5",
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity_boost,
                "style": style,
            },
        }
