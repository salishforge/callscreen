"""Persona conversation manager for scam deterrent engagement.

Manages an in-character conversation between a scam deterrent persona
and a scam caller, tracking duration and maintaining conversation history.
"""

import logging
import time

from callscreen.ai.llm import complete
from callscreen.models.persona import Persona

logger = logging.getLogger(__name__)

# Escalation stages based on elapsed time fraction
ESCALATION_PROMPTS = {
    0.0: "",
    0.3: "\n\n[You are becoming slightly more confused and tangential in your responses.]",
    0.6: "\n\n[You are now significantly more confused. You frequently lose your train of thought, repeat yourself, and go on longer tangents. Make it harder for the caller to get any useful information.]",
    0.8: "\n\n[You are extremely confused now. You are barely coherent, mixing up topics wildly, and it is nearly impossible for the caller to accomplish anything. Consider putting them on hold or asking them to repeat everything from the beginning.]",
}


class PersonaConversation:
    """Manages a single scam deterrent conversation."""

    def __init__(self, persona: Persona, call_sid: str) -> None:
        self._persona = persona
        self._call_sid = call_sid
        self._history: list[dict[str, str]] = []
        self._started_at: float = time.time()
        self._turn_count: int = 0

    @property
    def persona(self) -> Persona:
        return self._persona

    @property
    def call_sid(self) -> str:
        return self._call_sid

    @property
    def elapsed_seconds(self) -> float:
        return time.time() - self._started_at

    @property
    def max_duration_seconds(self) -> int:
        rules = self._persona.engagement_rules or {}
        return rules.get("max_duration_seconds", 600)

    @property
    def target_duration_seconds(self) -> int:
        rules = self._persona.engagement_rules or {}
        return rules.get("target_duration_seconds", 300)

    def _get_escalation_suffix(self) -> str:
        """Get the appropriate escalation prompt based on elapsed time."""
        if self.target_duration_seconds <= 0:
            return ""
        fraction = self.elapsed_seconds / self.target_duration_seconds
        suffix = ""
        for threshold, prompt in sorted(ESCALATION_PROMPTS.items()):
            if fraction >= threshold:
                suffix = prompt
        return suffix

    def _build_system_message(self) -> str:
        """Build the system prompt with escalation instructions."""
        base = self._persona.system_prompt
        escalation = self._get_escalation_suffix()
        return base + escalation

    async def generate_response(self, caller_utterance: str) -> str:
        """Generate an in-character response to the scam caller.

        Args:
            caller_utterance: What the scam caller just said.

        Returns:
            The persona's in-character response.
        """
        self._turn_count += 1
        self._history.append({"role": "user", "content": caller_utterance})

        messages = [
            {"role": "system", "content": self._build_system_message()},
            *self._history,
        ]

        try:
            response = await complete(
                messages=messages,
                temperature=0.7,
                max_tokens=256,
            )
        except Exception:
            logger.exception(
                "LLM generation failed for persona '%s' on call %s",
                self._persona.name,
                self._call_sid,
            )
            # Fallback: a generic stalling response
            response = "Oh my, could you repeat that? I was just looking for my glasses..."

        self._history.append({"role": "assistant", "content": response})

        logger.debug(
            "Persona '%s' turn %d on call %s (%.0fs elapsed)",
            self._persona.name,
            self._turn_count,
            self._call_sid,
            self.elapsed_seconds,
        )
        return response

    def should_end(self) -> bool:
        """Check if the maximum engagement duration has been reached."""
        return self.elapsed_seconds >= self.max_duration_seconds

    def get_conversation_log(self) -> list[dict]:
        """Return the full conversation history for audit logging.

        Returns:
            List of message dicts with role, content, and metadata.
        """
        return [
            {
                "role": msg["role"],
                "content": msg["content"],
                "persona": self._persona.name,
                "call_sid": self._call_sid,
            }
            for msg in self._history
        ]
