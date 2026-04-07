"""User settings endpoints."""

from datetime import time

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from callscreen.db.session import get_db
from callscreen.models.settings import UserSettings
from callscreen.schemas.settings import SettingsResponse, SettingsUpdate
from callscreen.security.auth import get_current_user

router = APIRouter()


@router.get("", response_model=SettingsResponse)
async def get_settings(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get current user settings."""
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    )
    settings = result.scalar_one_or_none()

    if not settings:
        settings = UserSettings(user_id=current_user.id)
        db.add(settings)
        await db.flush()
        await db.refresh(settings)

    return SettingsResponse.model_validate(settings)


@router.put("", response_model=SettingsResponse)
async def update_settings(
    data: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Update user settings."""
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    )
    settings = result.scalar_one_or_none()

    if not settings:
        settings = UserSettings(user_id=current_user.id)
        db.add(settings)

    for field, value in data.model_dump(exclude_unset=True).items():
        # Convert HH:MM strings to time objects for DB Time columns
        if field in ("quiet_hours_start", "quiet_hours_end") and isinstance(value, str):
            h, m = value.split(":")
            value = time(int(h), int(m))
        setattr(settings, field, value)

    await db.flush()
    await db.refresh(settings)
    return SettingsResponse.model_validate(settings)
