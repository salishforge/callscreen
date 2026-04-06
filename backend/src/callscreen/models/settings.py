"""User settings model."""

import uuid
from datetime import time

from sqlalchemy import Boolean, Enum, ForeignKey, JSON, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from callscreen.models.base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin


class UserSettings(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id"), unique=True
    )
    preferred_channel: Mapped[str] = mapped_column(String(50), default="email")
    greeting_message: Mapped[str] = mapped_column(
        Text,
        default="Hello. You have reached an automated call screening service.",
    )
    quiet_hours_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    quiet_hours_end: Mapped[time | None] = mapped_column(Time, nullable=True)
    quiet_hours_timezone: Mapped[str] = mapped_column(String(50), default="America/New_York")
    caretaker_fork_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    caretaker_user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id"), nullable=True
    )
    caretaker_fork_priority: Mapped[str] = mapped_column(String(20), default="urgent")
    persona_preferences: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    screening_strictness: Mapped[str] = mapped_column(String(20), default="moderate")

    user = relationship("User", back_populates="settings", foreign_keys=[user_id])
