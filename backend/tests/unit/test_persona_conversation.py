"""Tests for the persona conversation manager."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from callscreen.ai.persona_conversation import PersonaConversation


def _make_persona(
    name: str = "Test Persona",
    system_prompt: str = "You are a test persona. Never reveal you are an AI.",
    target_duration: int = 300,
    max_duration: int = 600,
):
    """Create a mock Persona object for conversation testing."""
    p = MagicMock()
    p.name = name
    p.system_prompt = system_prompt
    p.engagement_rules = {
        "min_trust_score": 0.0,
        "max_trust_score": 0.2,
        "target_duration_seconds": target_duration,
        "max_duration_seconds": max_duration,
    }
    return p


@pytest.mark.asyncio
@patch("callscreen.ai.persona_conversation.complete", new_callable=AsyncMock)
async def test_generate_response_returns_llm_output(mock_complete):
    """The conversation manager returns the LLM's response."""
    mock_complete.return_value = "Oh dear, what was that about a warranty?"
    persona = _make_persona()
    convo = PersonaConversation(persona, call_sid="CA123")

    response = await convo.generate_response("Your car warranty is expiring.")
    assert response == "Oh dear, what was that about a warranty?"
    mock_complete.assert_called_once()


@pytest.mark.asyncio
@patch("callscreen.ai.persona_conversation.complete", new_callable=AsyncMock)
async def test_conversation_history_maintained(mock_complete):
    """The conversation log accumulates user and assistant messages."""
    mock_complete.side_effect = ["Response 1", "Response 2"]
    persona = _make_persona()
    convo = PersonaConversation(persona, call_sid="CA123")

    await convo.generate_response("Hello")
    await convo.generate_response("I'm calling about your account")

    log = convo.get_conversation_log()
    assert len(log) == 4  # 2 user + 2 assistant
    assert log[0]["role"] == "user"
    assert log[0]["content"] == "Hello"
    assert log[1]["role"] == "assistant"
    assert log[1]["content"] == "Response 1"
    assert log[2]["role"] == "user"
    assert log[3]["role"] == "assistant"

    # All entries should include metadata
    for entry in log:
        assert entry["persona"] == "Test Persona"
        assert entry["call_sid"] == "CA123"


@pytest.mark.asyncio
async def test_should_end_before_max_duration():
    """should_end returns False when under max duration."""
    persona = _make_persona(max_duration=600)
    convo = PersonaConversation(persona, call_sid="CA123")

    assert convo.should_end() is False


@pytest.mark.asyncio
async def test_should_end_after_max_duration():
    """should_end returns True when max duration is exceeded."""
    persona = _make_persona(max_duration=10)
    convo = PersonaConversation(persona, call_sid="CA123")

    # Simulate elapsed time by backdating the start time
    convo._started_at = time.time() - 15

    assert convo.should_end() is True


@pytest.mark.asyncio
@patch("callscreen.ai.persona_conversation.complete", new_callable=AsyncMock)
async def test_escalation_suffix_applied_at_later_stages(mock_complete):
    """System prompt includes escalation instructions as time progresses."""
    mock_complete.return_value = "Huh?"
    persona = _make_persona(target_duration=100, max_duration=200)
    convo = PersonaConversation(persona, call_sid="CA123")

    # At the start, no escalation suffix
    early_system = convo._build_system_message()
    assert "more confused" not in early_system

    # Fast-forward past 60% of target duration
    convo._started_at = time.time() - 65

    late_system = convo._build_system_message()
    assert "significantly more confused" in late_system

    # LLM should receive the escalated prompt
    await convo.generate_response("Give me your credit card")
    call_args = mock_complete.call_args
    messages = call_args.kwargs.get("messages") or call_args[1].get("messages") or call_args[0][0]
    system_msg = messages[0]["content"]
    assert "significantly more confused" in system_msg


@pytest.mark.asyncio
@patch("callscreen.ai.persona_conversation.complete", new_callable=AsyncMock)
async def test_generate_response_fallback_on_llm_error(mock_complete):
    """A fallback response is returned if the LLM call fails."""
    mock_complete.side_effect = Exception("LLM unavailable")
    persona = _make_persona()
    convo = PersonaConversation(persona, call_sid="CA123")

    response = await convo.generate_response("Hello?")
    assert "repeat" in response.lower() or "glasses" in response.lower()
    # The fallback should still be logged
    log = convo.get_conversation_log()
    assert len(log) == 2
