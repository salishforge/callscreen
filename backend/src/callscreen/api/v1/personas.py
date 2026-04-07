"""Persona management API endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from callscreen.ai.prompts.personas.builtin import get_builtin_personas
from callscreen.db.session import get_db
from callscreen.models.persona import Persona
from callscreen.schemas.persona import PersonaCreate, PersonaResponse, PersonaUpdate
from callscreen.security.auth import get_current_user

router = APIRouter()


def _require_admin(current_user) -> None:  # type: ignore[no-untyped-def]
    """Raise 403 if the user is not an admin."""
    from callscreen.models.user import UserRole

    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )


@router.get("", response_model=list[PersonaResponse])
async def list_personas(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List all personas (admin only)."""
    _require_admin(current_user)
    result = await db.execute(select(Persona).order_by(Persona.name))
    personas = result.scalars().all()
    return [PersonaResponse.model_validate(p) for p in personas]


@router.get("/{persona_id}", response_model=PersonaResponse)
async def get_persona(
    persona_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get persona detail."""
    result = await db.execute(select(Persona).where(Persona.id == persona_id))
    persona = result.scalar_one_or_none()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    return PersonaResponse.model_validate(persona)


@router.post("", response_model=PersonaResponse, status_code=status.HTTP_201_CREATED)
async def create_persona(
    data: PersonaCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create a custom persona (admin only)."""
    _require_admin(current_user)

    persona = Persona(
        name=data.name,
        description=data.description,
        system_prompt=data.system_prompt,
        voice_id=data.voice_id,
        speech_rate=data.speech_rate,
        engagement_rules=data.engagement_rules.model_dump() if data.engagement_rules else None,
        is_builtin=False,
        is_active=True,
        created_by=current_user.id,
    )
    db.add(persona)
    await db.flush()
    await db.refresh(persona)
    return PersonaResponse.model_validate(persona)


@router.put("/{persona_id}", response_model=PersonaResponse)
async def update_persona(
    persona_id: uuid.UUID,
    data: PersonaUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Update a persona (admin only, not builtin)."""
    _require_admin(current_user)

    result = await db.execute(select(Persona).where(Persona.id == persona_id))
    persona = result.scalar_one_or_none()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    if persona.is_builtin:
        raise HTTPException(status_code=400, detail="Cannot modify built-in personas")

    update_data = data.model_dump(exclude_unset=True)
    if "engagement_rules" in update_data and update_data["engagement_rules"] is not None:
        update_data["engagement_rules"] = data.engagement_rules.model_dump()  # type: ignore[union-attr]

    for field, value in update_data.items():
        setattr(persona, field, value)

    await db.flush()
    await db.refresh(persona)
    return PersonaResponse.model_validate(persona)


@router.delete("/{persona_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_persona(
    persona_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Deactivate a persona (admin only, not builtin)."""
    _require_admin(current_user)

    result = await db.execute(select(Persona).where(Persona.id == persona_id))
    persona = result.scalar_one_or_none()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    if persona.is_builtin:
        raise HTTPException(status_code=400, detail="Cannot deactivate built-in personas")

    persona.is_active = False
    await db.flush()


@router.post("/seed-builtins", response_model=list[PersonaResponse])
async def seed_builtins(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Seed the built-in personas into the database.

    Skips any that already exist (matched by name + is_builtin).
    """
    _require_admin(current_user)

    builtin_defs = get_builtin_personas()
    seeded: list[Persona] = []

    for defn in builtin_defs:
        existing = await db.execute(
            select(Persona).where(
                Persona.name == defn["name"],
                Persona.is_builtin.is_(True),
            )
        )
        if existing.scalar_one_or_none():
            continue

        persona = Persona(**defn)
        db.add(persona)
        await db.flush()
        await db.refresh(persona)
        seeded.append(persona)

    return [PersonaResponse.model_validate(p) for p in seeded]
