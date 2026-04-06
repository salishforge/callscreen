"""Message model."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from callscreen.models.base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin


class MessagePriority(str, enum.Enum):
    URGENT = "urgent"
    NORMAL = "normal"
    LOW = "low"


class MessageCategory(str, enum.Enum):
    MEDICAL = "medical"
    PERSONAL = "personal"
    BUSINESS = "business"
    OTHER = "other"


class DeliveryStatus(str, enum.Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"


class Message(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "messages"

    call_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("call_records.id"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id"), index=True
    )
    content: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[MessagePriority] = mapped_column(
        Enum(MessagePriority), default=MessagePriority.NORMAL
    )
    category: Mapped[MessageCategory] = mapped_column(
        Enum(MessageCategory), default=MessageCategory.OTHER
    )
    audio_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    delivery_status: Mapped[DeliveryStatus] = mapped_column(
        Enum(DeliveryStatus), default=DeliveryStatus.PENDING
    )
    delivered_via: Mapped[str | None] = mapped_column(String(50), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    call = relationship("CallRecord", back_populates="messages")
    user = relationship("User", back_populates="messages")
    deliveries = relationship("MessageDelivery", back_populates="message", lazy="selectin")


class MessageDelivery(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "message_deliveries"

    message_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("messages.id"), index=True
    )
    channel: Mapped[str] = mapped_column(String(50))
    recipient: Mapped[str] = mapped_column(String(255))
    status: Mapped[DeliveryStatus] = mapped_column(
        Enum(DeliveryStatus, name="delivery_channel_status"), default=DeliveryStatus.PENDING
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    message = relationship("Message", back_populates="deliveries")
