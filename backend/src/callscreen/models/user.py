"""User model."""

import enum

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from callscreen.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    CARETAKER = "caretaker"
    USER = "user"


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.USER)
    phone_number: Mapped[str] = mapped_column(String(20), default="")
    mfa_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    contacts = relationship("Contact", back_populates="user", lazy="selectin")
    settings = relationship(
        "UserSettings",
        back_populates="user",
        uselist=False,
        lazy="selectin",
        foreign_keys="UserSettings.user_id",
    )
    calls = relationship(
        "CallRecord",
        back_populates="user",
        lazy="selectin",
        foreign_keys="CallRecord.user_id",
    )
    messages = relationship(
        "Message",
        back_populates="user",
        lazy="selectin",
        foreign_keys="Message.user_id",
    )
