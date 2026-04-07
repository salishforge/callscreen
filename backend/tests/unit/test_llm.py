"""Tests for LiteLLM integration."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from callscreen.ai.llm import complete, classify_intent, summarize_voicemail


@pytest.fixture
def mock_litellm_response():
    """Create a mock LiteLLM response."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = "Test response"
    response.usage = MagicMock()
    response.usage.prompt_tokens = 10
    response.usage.completion_tokens = 5
    return response


class TestComplete:
    @pytest.mark.asyncio
    async def test_complete_returns_content(self, mock_litellm_response):
        with patch("callscreen.ai.llm.litellm.acompletion", new_callable=AsyncMock, return_value=mock_litellm_response):
            result = await complete([{"role": "user", "content": "Hello"}])
            assert result == "Test response"

    @pytest.mark.asyncio
    async def test_complete_uses_config_default_model(self, mock_litellm_response):
        with patch("callscreen.ai.llm.litellm.acompletion", new_callable=AsyncMock, return_value=mock_litellm_response) as mock_call:
            await complete([{"role": "user", "content": "Hello"}])
            call_kwargs = mock_call.call_args[1]
            assert "anthropic" in call_kwargs["model"] or "claude" in call_kwargs["model"]

    @pytest.mark.asyncio
    async def test_complete_with_custom_model(self, mock_litellm_response):
        with patch("callscreen.ai.llm.litellm.acompletion", new_callable=AsyncMock, return_value=mock_litellm_response) as mock_call:
            await complete(
                [{"role": "user", "content": "Hello"}],
                model="openai/gpt-4o-mini",
            )
            call_kwargs = mock_call.call_args[1]
            assert call_kwargs["model"] == "openai/gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_complete_handles_empty_response(self):
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = None
        response.usage = None
        with patch("callscreen.ai.llm.litellm.acompletion", new_callable=AsyncMock, return_value=response):
            result = await complete([{"role": "user", "content": "Hello"}])
            assert result == ""


class TestClassifyIntent:
    @pytest.mark.asyncio
    async def test_classify_parses_json_response(self):
        intent_json = json.dumps({
            "intent": "medical appointment confirmation",
            "confidence": 0.9,
            "category": "medical",
            "is_legitimate": True,
            "summary": "Dr. Smith's office confirming appointment",
            "urgency": "medium",
        })
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = intent_json
        response.usage = MagicMock(prompt_tokens=50, completion_tokens=30)

        with patch("callscreen.ai.llm.litellm.acompletion", new_callable=AsyncMock, return_value=response):
            result = await classify_intent("Hi, this is Dr. Smith's office calling about your appointment tomorrow")
            assert result["category"] == "medical"
            assert result["is_legitimate"] is True
            assert result["confidence"] == 0.9

    @pytest.mark.asyncio
    async def test_classify_handles_markdown_fenced_json(self):
        intent_json = '```json\n{"intent": "test", "confidence": 0.5, "category": "unknown", "is_legitimate": null, "summary": "Test", "urgency": "low"}\n```'
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = intent_json
        response.usage = MagicMock(prompt_tokens=50, completion_tokens=30)

        with patch("callscreen.ai.llm.litellm.acompletion", new_callable=AsyncMock, return_value=response):
            result = await classify_intent("Some transcript")
            assert result["intent"] == "test"

    @pytest.mark.asyncio
    async def test_classify_handles_invalid_json(self):
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = "This is not JSON at all"
        response.usage = MagicMock(prompt_tokens=50, completion_tokens=10)

        with patch("callscreen.ai.llm.litellm.acompletion", new_callable=AsyncMock, return_value=response):
            result = await classify_intent("Some transcript")
            assert result["intent"] == "unknown"
            assert result["confidence"] == 0.0


class TestSummarizeVoicemail:
    @pytest.mark.asyncio
    async def test_summarize_returns_text(self):
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = "Dr. Smith called about your appointment tomorrow at 2pm."
        response.usage = MagicMock(prompt_tokens=40, completion_tokens=15)

        with patch("callscreen.ai.llm.litellm.acompletion", new_callable=AsyncMock, return_value=response):
            result = await summarize_voicemail("Hi this is Dr Smith calling about your appointment")
            assert "Dr. Smith" in result

    @pytest.mark.asyncio
    async def test_summarize_strips_whitespace(self):
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = "  Summary with extra spaces  \n"
        response.usage = MagicMock(prompt_tokens=40, completion_tokens=10)

        with patch("callscreen.ai.llm.litellm.acompletion", new_callable=AsyncMock, return_value=response):
            result = await summarize_voicemail("test")
            assert result == "Summary with extra spaces"
