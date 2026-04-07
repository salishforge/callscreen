"""Persona selection engine for scam deterrent engagement.

Selects the appropriate persona based on trust score and call context,
rotating between available personas for variety.
"""

import logging
import random
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from callscreen.models.persona import Persona

logger = logging.getLogger(__name__)

# Trust score thresholds
ENGAGE_THRESHOLD = 0.2  # Activate persona when trust_score < this
LEGITIMATE_THRESHOLD = 0.3  # Definitely do NOT engage when trust_score >= this


class PersonaEngine:
    """Selects and manages scam deterrent personas."""

    def __init__(self) -> None:
        self._last_persona_id: UUID | None = None

    async def should_engage(self, trust_score: float) -> bool:
        """Determine if a scam deterrent persona should be activated.

        Only activates when trust_score < 0.2 (highly likely scam).
        Returns False for trust_score >= 0.3 (legitimate calls).
        For scores between 0.2 and 0.3, returns False (uncertain zone).
        """
        return trust_score < ENGAGE_THRESHOLD

    async def select_persona(
        self,
        trust_score: float,
        call_metadata: dict,
        db: AsyncSession,
    ) -> Persona | None:
        """Select an appropriate persona based on trust score and call context.

        Args:
            trust_score: The calculated trust score for the call (0.0 - 1.0).
            call_metadata: Additional call context (e.g., caller_number, call_type).
            db: Database session.

        Returns:
            A Persona instance if engagement is warranted, None otherwise.
        """
        if trust_score >= LEGITIMATE_THRESHOLD:
            logger.debug(
                "Trust score %.2f >= %.2f, no persona needed",
                trust_score,
                LEGITIMATE_THRESHOLD,
            )
            return None

        if not await self.should_engage(trust_score):
            logger.debug(
                "Trust score %.2f in uncertain zone, not engaging",
                trust_score,
            )
            return None

        # Fetch active personas whose engagement rules cover this trust score
        result = await db.execute(
            select(Persona).where(Persona.is_active.is_(True))
        )
        all_personas = result.scalars().all()

        # Filter to those matching the trust score range
        matching = []
        for persona in all_personas:
            rules = persona.engagement_rules or {}
            min_score = rules.get("min_trust_score", 0.0)
            max_score = rules.get("max_trust_score", 0.2)
            if min_score <= trust_score <= max_score:
                matching.append(persona)

        if not matching:
            logger.warning("No matching personas for trust_score=%.2f", trust_score)
            return None

        # Rotate: avoid picking the same persona twice in a row
        if len(matching) > 1 and self._last_persona_id is not None:
            non_repeat = [p for p in matching if p.id != self._last_persona_id]
            if non_repeat:
                matching = non_repeat

        selected = random.choice(matching)
        self._last_persona_id = selected.id
        logger.info(
            "Selected persona '%s' for trust_score=%.2f",
            selected.name,
            trust_score,
        )
        return selected
