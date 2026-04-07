"""Tests for STT base models (TranscriptSegment, TranscriptResult)."""

import pytest
from pydantic import ValidationError

from callscreen.voice.stt.base import TranscriptResult, TranscriptSegment


class TestTranscriptSegment:
    @pytest.mark.unit
    def test_valid_segment(self):
        seg = TranscriptSegment(
            text="hello world",
            confidence=0.95,
            is_final=True,
            start_time=0.0,
            end_time=1.5,
        )
        assert seg.text == "hello world"
        assert seg.confidence == 0.95
        assert seg.is_final is True
        assert seg.start_time == 0.0
        assert seg.end_time == 1.5

    @pytest.mark.unit
    def test_confidence_bounds(self):
        """Confidence must be between 0.0 and 1.0."""
        with pytest.raises(ValidationError):
            TranscriptSegment(
                text="test",
                confidence=1.5,
                is_final=True,
                start_time=0.0,
                end_time=1.0,
            )
        with pytest.raises(ValidationError):
            TranscriptSegment(
                text="test",
                confidence=-0.1,
                is_final=True,
                start_time=0.0,
                end_time=1.0,
            )

    @pytest.mark.unit
    def test_negative_start_time_rejected(self):
        with pytest.raises(ValidationError):
            TranscriptSegment(
                text="test",
                confidence=0.5,
                is_final=False,
                start_time=-1.0,
                end_time=1.0,
            )

    @pytest.mark.unit
    def test_interim_result(self):
        """Interim (non-final) segments are valid."""
        seg = TranscriptSegment(
            text="partial",
            confidence=0.3,
            is_final=False,
            start_time=2.0,
            end_time=3.0,
        )
        assert seg.is_final is False


class TestTranscriptResult:
    @pytest.mark.unit
    def test_valid_result(self):
        seg = TranscriptSegment(
            text="hello",
            confidence=0.9,
            is_final=True,
            start_time=0.0,
            end_time=1.0,
        )
        result = TranscriptResult(
            full_text="hello",
            segments=[seg],
            language="en",
            duration_seconds=1.0,
        )
        assert result.full_text == "hello"
        assert len(result.segments) == 1
        assert result.language == "en"
        assert result.duration_seconds == 1.0

    @pytest.mark.unit
    def test_empty_segments(self):
        result = TranscriptResult(
            full_text="",
            segments=[],
            language="en",
            duration_seconds=0.0,
        )
        assert result.segments == []

    @pytest.mark.unit
    def test_default_language(self):
        result = TranscriptResult(
            full_text="test",
            duration_seconds=1.0,
        )
        assert result.language == "en"

    @pytest.mark.unit
    def test_negative_duration_rejected(self):
        with pytest.raises(ValidationError):
            TranscriptResult(
                full_text="test",
                segments=[],
                language="en",
                duration_seconds=-1.0,
            )
