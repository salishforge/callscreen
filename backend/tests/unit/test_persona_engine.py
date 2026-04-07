"""Tests for the persona selection engine."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from callscreen.ai.persona_engine import (
    ENGAGE_THRESHOLD,
    LEGITIMATE_THRESHOLD,
    PersonaEngine,
)


def _make_persona(
    name: str = "Test Persona",
    is_active: bool = True,
    min_trust: float = 0.0,
    max_trust: float = 0.2,
    persona_id: uuid.UUID | None = None,
):
    """Create a mock Persona object."""
    p = MagicMock()
    p.id = persona_id or uuid.uuid4()
    p.name = name
    p.is_active = is_active
    p.engagement_rules = {
        "min_trust_score": min_trust,
        "max_trust_score": max_trust,
        "target_duration_seconds": 300,
        "max_duration_seconds": 600,
    }
    return p


def _mock_db_with_personas(personas):
    """Create a mock AsyncSession that returns the given personas."""
    db = AsyncMock()
    result = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = personas
    result.scalars.return_value = scalars
    db.execute = AsyncMock(return_value=result)
    return db


@pytest.mark.asyncio
async def test_should_engage_scam_call():
    """Personas should engage when trust score indicates a scam."""
    engine = PersonaEngine()
    assert await engine.should_engage(0.0) is True
    assert await engine.should_engage(0.1) is True
    assert await engine.should_engage(0.19) is True


@pytest.mark.asyncio
async def test_should_not_engage_legitimate_call():
    """Personas should NOT engage for legitimate or uncertain calls."""
    engine = PersonaEngine()
    assert await engine.should_engage(0.2) is False
    assert await engine.should_engage(0.3) is False
    assert await engine.should_engage(0.5) is False
    assert await engine.should_engage(1.0) is False


@pytest.mark.asyncio
async def test_select_persona_returns_none_for_legitimate():
    """Select persona returns None when trust score is above the legitimate threshold."""
    engine = PersonaEngine()
    db = _mock_db_with_personas([])

    result = await engine.select_persona(0.5, {}, db)
    assert result is None

    result = await engine.select_persona(LEGITIMATE_THRESHOLD, {}, db)
    assert result is None


@pytest.mark.asyncio
async def test_select_persona_returns_none_uncertain_zone():
    """Trust scores between ENGAGE and LEGITIMATE thresholds should return None."""
    engine = PersonaEngine()
    db = _mock_db_with_personas([_make_persona()])

    result = await engine.select_persona(0.25, {}, db)
    assert result is None


@pytest.mark.asyncio
async def test_select_persona_returns_matching_persona():
    """A matching active persona is returned for low trust scores."""
    persona = _make_persona(name="Confused Grandparent")
    engine = PersonaEngine()
    db = _mock_db_with_personas([persona])

    result = await engine.select_persona(0.1, {}, db)
    assert result is not None
    assert result.name == "Confused Grandparent"


@pytest.mark.asyncio
async def test_select_persona_respects_trust_range():
    """Only personas whose engagement rules cover the trust score are eligible."""
    narrow = _make_persona(name="Narrow", min_trust=0.0, max_trust=0.05)
    wide = _make_persona(name="Wide", min_trust=0.0, max_trust=0.2)
    engine = PersonaEngine()
    db = _mock_db_with_personas([narrow, wide])

    # Trust score 0.1 should only match "Wide"
    result = await engine.select_persona(0.1, {}, db)
    assert result is not None
    assert result.name == "Wide"


@pytest.mark.asyncio
async def test_select_persona_rotates():
    """The engine avoids selecting the same persona twice in a row."""
    id_a = uuid.uuid4()
    id_b = uuid.uuid4()
    persona_a = _make_persona(name="A", persona_id=id_a)
    persona_b = _make_persona(name="B", persona_id=id_b)
    engine = PersonaEngine()

    # Force the "last used" to persona A
    engine._last_persona_id = id_a
    db = _mock_db_with_personas([persona_a, persona_b])

    result = await engine.select_persona(0.1, {}, db)
    assert result is not None
    assert result.id == id_b


@pytest.mark.asyncio
async def test_select_persona_returns_none_when_no_active():
    """Returns None when there are no active personas at all."""
    engine = PersonaEngine()
    db = _mock_db_with_personas([])

    result = await engine.select_persona(0.05, {}, db)
    assert result is None
