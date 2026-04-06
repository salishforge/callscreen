"""Contact model (whitelist/blocklist)."""

import enum
import uuid

from sqlalchemy import Enum, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from callscreen.models.base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin


class ContactType(str, enum.Enum):
    WHITELIST = "whitelist"
    BLOCKLIST = "blocklist"
    KNOWN = "known"


class ContactCategory(str, enum.Enum):
    PERSONAL = "personal"
    MEDICAL = "medical"
    BUSINESS = "business"
    GOVERNMENT = "government"
    OTHER = "other"


class Contact(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "contacts"
    __table_args__ = (UniqueConstraint("user_id", "phone_number", name="uq_user_phone"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id"), index=True
    )
    phone_number: Mapped[str] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(255))
    contact_type: Mapped[ContactType] = mapped_column(Enum(ContactType))
    category: Mapped[ContactCategory] = mapped_column(
        Enum(ContactCategory), default=ContactCategory.OTHER
    )
    trust_override: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")

    user = relationship("User", back_populates="contacts")
