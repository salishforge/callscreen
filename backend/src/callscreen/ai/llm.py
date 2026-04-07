"""LiteLLM multi-provider gateway for AI completions.

Routes to Claude (primary), OpenAI (fallback), or Ollama (self-hosted)
via the LiteLLM unified API.
"""

import logging
from typing import Any

import litellm

from callscreen.config import get_settings

logger = logging.getLogger(__name__)

# Suppress LiteLLM's verbose logging
litellm.set_verbose = False


async def complete(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 1024,
    **kwargs: Any,
) -> str:
    """Run a chat completion through LiteLLM.

    Args:
        messages: OpenAI-format message list [{"role": ..., "content": ...}]
        model: LiteLLM model string (e.g., "anthropic/claude-sonnet-4-20250514").
               Falls back to config default.
        temperature: Sampling temperature (lower = more deterministic)
        max_tokens: Max response tokens

    Returns:
        The assistant's response text.
    """
    settings = get_settings()
    model = model or settings.litellm_default_model

    try:
        response = await litellm.acompletion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        content = response.choices[0].message.content or ""
        logger.debug("LLM completion: model=%s tokens_in=%d tokens_out=%d",
                     model,
                     response.usage.prompt_tokens if response.usage else 0,
                     response.usage.completion_tokens if response.usage else 0)
        return content
    except Exception as e:
        logger.error("LLM completion failed (model=%s): %s", model, e)
        # Try fallback to OpenAI if primary fails
        if "anthropic" in (model or "") and settings.openai_api_key:
            logger.info("Falling back to OpenAI")
            try:
                response = await litellm.acompletion(
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content or ""
            except Exception as fallback_err:
                logger.error("Fallback also failed: %s", fallback_err)
        raise


async def classify_intent(transcript: str) -> dict[str, Any]:
    """Classify a caller's intent from their transcript.

    Returns:
        Dict with keys: intent, confidence, category, is_legitimate, summary
    """
    system_prompt = """You are a call screening AI. Analyze the caller's transcript and classify their intent.
Respond in JSON with these exact keys:
- intent: Brief description of what the caller wants (string)
- confidence: Your confidence in the classification, 0.0-1.0 (float)
- category: One of "medical", "personal", "business", "government", "scam", "robocall", "unknown" (string)
- is_legitimate: Whether this appears to be a legitimate call (boolean)
- summary: One-sentence summary suitable for the recipient (string)
- urgency: One of "high", "medium", "low" (string)

Be conservative — when in doubt, mark as "unknown" with lower confidence."""

    import json
    response = await complete(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Caller transcript:\n{transcript}"},
        ],
        temperature=0.1,
        max_tokens=512,
    )

    try:
        # Strip markdown code fences if present
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            cleaned = cleaned.rsplit("```", 1)[0]
        return json.loads(cleaned)
    except (json.JSONDecodeError, IndexError):
        logger.warning("Failed to parse intent classification, returning raw")
        return {
            "intent": "unknown",
            "confidence": 0.0,
            "category": "unknown",
            "is_legitimate": None,
            "summary": response[:200],
            "urgency": "medium",
        }


async def summarize_voicemail(transcript: str, caller_info: str = "") -> str:
    """Generate a concise voicemail summary for the recipient.

    Designed for elderly users — uses clear, simple language.
    """
    system_prompt = """You are summarizing a voicemail for an elderly person.
Write a clear, simple 1-3 sentence summary. Use plain language.
Include: who called, why, and any action needed.
If it appears to be a scam, say so clearly."""

    context = f"Caller info: {caller_info}\n" if caller_info else ""
    response = await complete(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{context}Voicemail transcript:\n{transcript}"},
        ],
        temperature=0.2,
        max_tokens=256,
    )
    return response.strip()
