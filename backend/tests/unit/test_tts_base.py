"""Tests for TTS base models (AudioResult)."""

import pytest
from pydantic import ValidationError

from callscreen.voice.tts.base import AudioResult


class TestAudioResult:
    @pytest.mark.unit
    def test_valid_result(self):
        result = AudioResult(
            audio_data=b"\x00\x01\x02",
            mime_type="audio/basic",
            sample_rate=8000,
            duration_seconds=0.5,
        )
        assert result.audio_data == b"\x00\x01\x02"
        assert result.mime_type == "audio/basic"
        assert result.sample_rate == 8000
        assert result.duration_seconds == 0.5

    @pytest.mark.unit
    def test_empty_audio(self):
        result = AudioResult(
            audio_data=b"",
            mime_type="audio/basic",
            sample_rate=8000,
            duration_seconds=0.0,
        )
        assert result.audio_data == b""

    @pytest.mark.unit
    def test_invalid_sample_rate(self):
        """Sample rate must be positive."""
        with pytest.raises(ValidationError):
            AudioResult(
                audio_data=b"\x00",
                mime_type="audio/basic",
                sample_rate=0,
                duration_seconds=0.1,
            )

    @pytest.mark.unit
    def test_negative_duration_rejected(self):
        with pytest.raises(ValidationError):
            AudioResult(
                audio_data=b"\x00",
                mime_type="audio/basic",
                sample_rate=8000,
                duration_seconds=-1.0,
            )
