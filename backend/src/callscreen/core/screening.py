"""AI voice screening orchestrator.

Coordinates STT transcripts, LLM-based conversation, and TTS responses
to screen incoming calls on behalf of elderly landline users.
"""

import logging
import time
from typing import Any

from pydantic import BaseModel, Field

from callscreen.ai.llm import classify_intent, complete
from callscreen.ai.prompts.screening import (
    FAREWELL_SCRIPTS,
    GREETING_SCRIPT,
    SCREENING_SYSTEM_PROMPT,
)
from callscreen.voice.stt.base import TranscriptSegment

logger = logging.getLogger("callscreen.screening")

# After this many caller exchanges, trigger intent classification
MIN_EXCHANGES_FOR_CLASSIFICATION = 3
MAX_EXCHANGES_BEFORE_FORCE = 5


class ScreeningResult(BaseModel):
    """Outcome of a completed screening session."""

    call_sid: str = Field(description="Twilio Call SID")
    transcript: str = Field(default="", description="Full conversation transcript")
    intent_classification: dict[str, Any] = Field(
        default_factory=dict, description="LLM intent classification result"
    )
    recommendation: str = Field(
        default="message",
        description="Screening recommendation: forward, message, or block",
    )
    trust_adjustment: float = Field(
        default=0.0,
        description="Suggested trust score adjustment (-1.0 to 1.0)",
    )
    duration_seconds: float = Field(
        default=0.0, description="Total screening duration in seconds"
    )


class _ConversationState:
    """Internal mutable state for an active screening conversation."""

    def __init__(self, call_sid: str) -> None:
        self.call_sid = call_sid
        self.started_at = time.time()
        self.messages: list[dict[str, str]] = [
            {"role": "system", "content": SCREENING_SYSTEM_PROMPT},
        ]
        self.caller_exchanges: int = 0
        self.full_transcript_parts: list[str] = []
        self.intent_classified: bool = False
        self.recommendation: str = "message"
        self.classification: dict[str, Any] = {}


class ScreeningOrchestrator:
    """Main call screening engine.

    Maintains per-call conversation history, feeds caller utterances
    to the LLM, and decides when to classify intent.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, _ConversationState] = {}

    async def start_screening(self, call_sid: str, voice_session: Any = None) -> None:
        """Begin an AI voice screening session.

        Args:
            call_sid: Twilio Call SID.
            voice_session: Optional VoiceSession (for future TTS integration).
        """
        state = _ConversationState(call_sid)
        self._sessions[call_sid] = state

        # Record the greeting as our first assistant message
        state.messages.append({"role": "assistant", "content": GREETING_SCRIPT})
        state.full_transcript_parts.append(f"[Assistant] {GREETING_SCRIPT}")

        logger.info("Screening started for call_sid=%s", call_sid)

    async def handle_transcript(
        self, call_sid: str, segment: TranscriptSegment
    ) -> str | None:
        """Process a new transcript segment, return TTS response if needed.

        Only processes final (non-interim) segments. Sends the caller's
        utterance to the LLM and returns the assistant's response.

        Args:
            call_sid: Twilio Call SID.
            segment: The transcribed speech segment.

        Returns:
            The assistant's text response to speak via TTS, or None if
            the segment is interim (not yet finalized).
        """
        state = self._sessions.get(call_sid)
        if state is None:
            logger.warning("No screening session for call_sid=%s", call_sid)
            return None

        # Only act on final transcripts
        if not segment.is_final:
            return None

        caller_text = segment.text.strip()
        if not caller_text:
            return None

        state.caller_exchanges += 1
        state.messages.append({"role": "user", "content": caller_text})
        state.full_transcript_parts.append(f"[Caller] {caller_text}")

        logger.info(
            "Screening exchange %d for call_sid=%s: %s",
            state.caller_exchanges,
            call_sid,
            caller_text[:80],
        )

        # Check if we should classify intent now
        if state.caller_exchanges >= MAX_EXCHANGES_BEFORE_FORCE:
            return await self._classify_and_farewell(state)

        # Generate conversational response via LLM
        try:
            response = await complete(
                messages=state.messages,
                temperature=0.3,
                max_tokens=256,
            )
        except Exception:
            logger.exception("LLM completion failed for call_sid=%s", call_sid)
            response = (
                "I'm sorry, could you repeat that? "
                "I want to make sure I understand correctly."
            )

        # Check if the LLM included an ASSESSMENT in its response
        if "ASSESSMENT:" in response:
            assessment_line = response.split("ASSESSMENT:")[-1].strip()
            # Strip the assessment from the spoken response
            spoken_response = response.split("ASSESSMENT:")[0].strip()
            state.messages.append({"role": "assistant", "content": spoken_response})
            state.full_transcript_parts.append(f"[Assistant] {spoken_response}")
            # Parse inline assessment and trigger classification
            return await self._classify_and_farewell(state)

        state.messages.append({"role": "assistant", "content": response})
        state.full_transcript_parts.append(f"[Assistant] {response}")

        # After minimum exchanges, try intent classification
        if (
            state.caller_exchanges >= MIN_EXCHANGES_FOR_CLASSIFICATION
            and not state.intent_classified
        ):
            return await self._classify_and_farewell(state)

        return response

    async def end_screening(self, call_sid: str) -> ScreeningResult:
        """End screening and return the assessment.

        If intent has not been classified yet, runs classification now.

        Args:
            call_sid: Twilio Call SID.

        Returns:
            ScreeningResult with transcript, classification, and recommendation.
        """
        state = self._sessions.pop(call_sid, None)
        if state is None:
            logger.warning(
                "No screening session to end for call_sid=%s", call_sid
            )
            return ScreeningResult(
                call_sid=call_sid,
                transcript="",
                recommendation="message",
            )

        # Classify if not already done
        if not state.intent_classified:
            await self._run_classification(state)

        duration = time.time() - state.started_at

        result = ScreeningResult(
            call_sid=call_sid,
            transcript="\n".join(state.full_transcript_parts),
            intent_classification=state.classification,
            recommendation=state.recommendation,
            trust_adjustment=self._compute_trust_adjustment(state.classification),
            duration_seconds=round(duration, 2),
        )

        logger.info(
            "Screening ended for call_sid=%s: recommendation=%s duration=%.1fs",
            call_sid,
            result.recommendation,
            result.duration_seconds,
        )
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _classify_and_farewell(self, state: _ConversationState) -> str:
        """Run intent classification, then return farewell script."""
        await self._run_classification(state)
        farewell = FAREWELL_SCRIPTS.get(state.recommendation, FAREWELL_SCRIPTS["message"])
        state.full_transcript_parts.append(f"[Assistant] {farewell}")
        return farewell

    async def _run_classification(self, state: _ConversationState) -> None:
        """Call the LLM to classify caller intent."""
        if state.intent_classified:
            return

        transcript_text = "\n".join(state.full_transcript_parts)
        try:
            classification = await classify_intent(transcript_text)
            state.classification = classification
            state.recommendation = self._map_recommendation(classification)
            state.intent_classified = True
            logger.info(
                "Intent classified for call_sid=%s: category=%s recommendation=%s",
                state.call_sid,
                classification.get("category", "unknown"),
                state.recommendation,
            )
        except Exception:
            logger.exception(
                "Intent classification failed for call_sid=%s", state.call_sid
            )
            state.classification = {
                "intent": "unknown",
                "confidence": 0.0,
                "category": "unknown",
                "is_legitimate": None,
                "summary": "Classification failed",
                "urgency": "medium",
            }
            state.recommendation = "message"
            state.intent_classified = True

    @staticmethod
    def _map_recommendation(classification: dict[str, Any]) -> str:
        """Map an intent classification to a screening recommendation."""
        category = classification.get("category", "unknown")
        is_legitimate = classification.get("is_legitimate")
        confidence = classification.get("confidence", 0.0)

        if category == "scam" or category == "robocall":
            return "block"

        if is_legitimate is True and confidence >= 0.7:
            return "forward"

        if is_legitimate is False and confidence >= 0.7:
            return "block"

        # Default: take a message
        return "message"

    @staticmethod
    def _compute_trust_adjustment(classification: dict[str, Any]) -> float:
        """Compute a trust score adjustment from -1.0 to 1.0."""
        if not classification:
            return 0.0

        category = classification.get("category", "unknown")
        is_legitimate = classification.get("is_legitimate")
        confidence = classification.get("confidence", 0.0)

        if category in ("scam", "robocall"):
            return -1.0 * confidence

        if is_legitimate is True:
            return 0.5 * confidence

        if is_legitimate is False:
            return -0.5 * confidence

        return 0.0
