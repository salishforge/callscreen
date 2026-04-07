"""Tests for the AI voice screening orchestrator."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from callscreen.core.screening import (
    MAX_EXCHANGES_BEFORE_FORCE,
    MIN_EXCHANGES_FOR_CLASSIFICATION,
    ScreeningOrchestrator,
    ScreeningResult,
)
from callscreen.voice.stt.base import TranscriptSegment


def _make_segment(text: str, is_final: bool = True) -> TranscriptSegment:
    """Helper to create a TranscriptSegment."""
    return TranscriptSegment(
        text=text,
        confidence=0.95,
        is_final=is_final,
        start_time=0.0,
        end_time=1.0,
    )


def _mock_classification(
    category: str = "personal",
    is_legitimate: bool = True,
    confidence: float = 0.9,
) -> dict:
    return {
        "intent": "personal call",
        "confidence": confidence,
        "category": category,
        "is_legitimate": is_legitimate,
        "summary": "A friend calling to chat",
        "urgency": "low",
    }


class TestScreeningOrchestrator:
    """Tests for the ScreeningOrchestrator class."""

    @pytest.mark.asyncio
    async def test_start_screening_creates_session(self):
        """start_screening should register a session with a greeting."""
        orch = ScreeningOrchestrator()
        await orch.start_screening("CA_test_001")

        # Session is tracked internally
        assert "CA_test_001" in orch._sessions
        state = orch._sessions["CA_test_001"]
        assert state.caller_exchanges == 0
        # The greeting should be recorded in transcript parts
        assert len(state.full_transcript_parts) == 1
        assert "[Assistant]" in state.full_transcript_parts[0]

    @pytest.mark.asyncio
    async def test_handle_transcript_ignores_interim_segments(self):
        """Interim (non-final) segments should return None."""
        orch = ScreeningOrchestrator()
        await orch.start_screening("CA_test_002")

        segment = _make_segment("hello", is_final=False)
        result = await orch.handle_transcript("CA_test_002", segment)
        assert result is None
        assert orch._sessions["CA_test_002"].caller_exchanges == 0

    @pytest.mark.asyncio
    async def test_handle_transcript_returns_llm_response(self):
        """A final transcript should produce an LLM response."""
        orch = ScreeningOrchestrator()
        await orch.start_screening("CA_test_003")

        with patch(
            "callscreen.core.screening.complete",
            new_callable=AsyncMock,
            return_value="Thank you for calling. May I ask your name?",
        ):
            segment = _make_segment("Hi, I'm calling about an appointment.")
            response = await orch.handle_transcript("CA_test_003", segment)

        assert response is not None
        assert "name" in response.lower() or "calling" in response.lower()
        assert orch._sessions["CA_test_003"].caller_exchanges == 1

    @pytest.mark.asyncio
    async def test_handle_transcript_no_session_returns_none(self):
        """Handling a transcript for an unknown session returns None."""
        orch = ScreeningOrchestrator()
        segment = _make_segment("Hello")
        result = await orch.handle_transcript("CA_nonexistent", segment)
        assert result is None

    @pytest.mark.asyncio
    async def test_classification_triggered_after_min_exchanges(self):
        """After MIN_EXCHANGES_FOR_CLASSIFICATION, intent classification fires."""
        orch = ScreeningOrchestrator()
        await orch.start_screening("CA_test_004")

        classification = _mock_classification()

        with (
            patch(
                "callscreen.core.screening.complete",
                new_callable=AsyncMock,
                return_value="Thank you, can you tell me more?",
            ),
            patch(
                "callscreen.core.screening.classify_intent",
                new_callable=AsyncMock,
                return_value=classification,
            ) as mock_classify,
        ):
            # Send exchanges below the threshold -- no classification yet
            for i in range(MIN_EXCHANGES_FOR_CLASSIFICATION - 1):
                seg = _make_segment(f"Utterance {i}")
                await orch.handle_transcript("CA_test_004", seg)

            assert mock_classify.call_count == 0

            # This exchange hits the threshold -- classification fires
            seg = _make_segment("One more utterance")
            response = await orch.handle_transcript("CA_test_004", seg)

            assert mock_classify.call_count == 1
            # Should return farewell script
            assert response is not None

    @pytest.mark.asyncio
    async def test_forced_classification_at_max_exchanges(self):
        """After MAX_EXCHANGES_BEFORE_FORCE, classification is forced."""
        orch = ScreeningOrchestrator()
        await orch.start_screening("CA_test_005")

        classification = _mock_classification(
            category="unknown", is_legitimate=None, confidence=0.3
        )

        with (
            patch(
                "callscreen.core.screening.complete",
                new_callable=AsyncMock,
                return_value="I see, please go on.",
            ),
            patch(
                "callscreen.core.screening.classify_intent",
                new_callable=AsyncMock,
                return_value=classification,
            ) as mock_classify,
        ):
            # Send exactly MAX exchanges -- each one should NOT classify
            # until the final one (the max'th) hits the force threshold
            for i in range(MAX_EXCHANGES_BEFORE_FORCE):
                seg = _make_segment(f"Exchange {i}")
                await orch.handle_transcript("CA_test_005", seg)

            assert mock_classify.call_count >= 1

    @pytest.mark.asyncio
    async def test_end_screening_returns_result(self):
        """end_screening should return a ScreeningResult with transcript."""
        orch = ScreeningOrchestrator()
        await orch.start_screening("CA_test_006")

        classification = _mock_classification()

        with (
            patch(
                "callscreen.core.screening.complete",
                new_callable=AsyncMock,
                return_value="Thank you.",
            ),
            patch(
                "callscreen.core.screening.classify_intent",
                new_callable=AsyncMock,
                return_value=classification,
            ),
        ):
            seg = _make_segment("Hi, this is John.")
            await orch.handle_transcript("CA_test_006", seg)

            result = await orch.end_screening("CA_test_006")

        assert isinstance(result, ScreeningResult)
        assert result.call_sid == "CA_test_006"
        assert "John" in result.transcript
        assert result.recommendation in ("forward", "message", "block")
        assert result.duration_seconds >= 0.0

    @pytest.mark.asyncio
    async def test_end_screening_no_session_returns_default(self):
        """Ending a nonexistent session returns a default result."""
        orch = ScreeningOrchestrator()
        result = await orch.end_screening("CA_ghost")

        assert result.call_sid == "CA_ghost"
        assert result.transcript == ""
        assert result.recommendation == "message"

    @pytest.mark.asyncio
    async def test_recommendation_maps_scam_to_block(self):
        """Scam classification should map to block recommendation."""
        orch = ScreeningOrchestrator()
        await orch.start_screening("CA_test_007")

        classification = _mock_classification(
            category="scam", is_legitimate=False, confidence=0.95
        )

        with (
            patch(
                "callscreen.core.screening.complete",
                new_callable=AsyncMock,
                return_value="Tell me more.",
            ),
            patch(
                "callscreen.core.screening.classify_intent",
                new_callable=AsyncMock,
                return_value=classification,
            ),
        ):
            for i in range(MIN_EXCHANGES_FOR_CLASSIFICATION):
                seg = _make_segment(f"Give me your SSN {i}")
                await orch.handle_transcript("CA_test_007", seg)

            result = await orch.end_screening("CA_test_007")

        assert result.recommendation == "block"
        assert result.trust_adjustment < 0

    @pytest.mark.asyncio
    async def test_llm_failure_returns_fallback_response(self):
        """If LLM fails, a fallback response should be returned."""
        orch = ScreeningOrchestrator()
        await orch.start_screening("CA_test_008")

        with patch(
            "callscreen.core.screening.complete",
            new_callable=AsyncMock,
            side_effect=Exception("LLM down"),
        ):
            seg = _make_segment("Hello there")
            response = await orch.handle_transcript("CA_test_008", seg)

        assert response is not None
        assert "repeat" in response.lower()

    @pytest.mark.asyncio
    async def test_empty_text_segment_ignored(self):
        """A final segment with empty text should be ignored."""
        orch = ScreeningOrchestrator()
        await orch.start_screening("CA_test_009")

        seg = _make_segment("   ", is_final=True)
        result = await orch.handle_transcript("CA_test_009", seg)
        assert result is None
        assert orch._sessions["CA_test_009"].caller_exchanges == 0


class TestScreeningResult:
    """Tests for the ScreeningResult model."""

    def test_screening_result_defaults(self):
        result = ScreeningResult(call_sid="CA_test")
        assert result.transcript == ""
        assert result.recommendation == "message"
        assert result.trust_adjustment == 0.0
        assert result.duration_seconds == 0.0

    def test_screening_result_serializes(self):
        result = ScreeningResult(
            call_sid="CA_serial",
            transcript="Hello",
            intent_classification={"category": "personal"},
            recommendation="forward",
            trust_adjustment=0.5,
            duration_seconds=12.3,
        )
        data = result.model_dump()
        assert data["call_sid"] == "CA_serial"
        assert data["recommendation"] == "forward"


class TestRecommendationMapping:
    """Tests for the static recommendation mapping logic."""

    def test_scam_maps_to_block(self):
        result = ScreeningOrchestrator._map_recommendation(
            {"category": "scam", "is_legitimate": False, "confidence": 0.9}
        )
        assert result == "block"

    def test_robocall_maps_to_block(self):
        result = ScreeningOrchestrator._map_recommendation(
            {"category": "robocall", "is_legitimate": False, "confidence": 0.8}
        )
        assert result == "block"

    def test_legitimate_high_confidence_maps_to_forward(self):
        result = ScreeningOrchestrator._map_recommendation(
            {"category": "medical", "is_legitimate": True, "confidence": 0.9}
        )
        assert result == "forward"

    def test_low_confidence_maps_to_message(self):
        result = ScreeningOrchestrator._map_recommendation(
            {"category": "unknown", "is_legitimate": None, "confidence": 0.3}
        )
        assert result == "message"

    def test_illegitimate_high_confidence_maps_to_block(self):
        result = ScreeningOrchestrator._map_recommendation(
            {"category": "business", "is_legitimate": False, "confidence": 0.8}
        )
        assert result == "block"


class TestTrustAdjustment:
    """Tests for the trust score adjustment computation."""

    def test_scam_gives_negative_adjustment(self):
        adj = ScreeningOrchestrator._compute_trust_adjustment(
            {"category": "scam", "confidence": 0.9}
        )
        assert adj < 0

    def test_legitimate_gives_positive_adjustment(self):
        adj = ScreeningOrchestrator._compute_trust_adjustment(
            {"category": "personal", "is_legitimate": True, "confidence": 0.8}
        )
        assert adj > 0

    def test_empty_classification_gives_zero(self):
        adj = ScreeningOrchestrator._compute_trust_adjustment({})
        assert adj == 0.0
