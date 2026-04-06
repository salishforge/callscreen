"""Call record model."""

import enum
import uuid

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from callscreen.models.base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin


class CallStatus(str, enum.Enum):
    INCOMING = "incoming"
    TRIAGE = "triage"
    NUMBER_LOOKUP = "number_lookup"
    SCREENING = "screening"
    INTERVIEWING = "interviewing"
    DECIDING = "deciding"
    FORWARDING = "forwarding"
    MESSAGING = "messaging"
    BLOCKING = "blocking"
    ENGAGING = "engaging"
    COMPLETED = "completed"
    FAILED = "failed"


class CallDisposition(str, enum.Enum):
    FORWARDED = "forwarded"
    MESSAGED = "messaged"
    BLOCKED = "blocked"
    ENGAGED = "engaged"
    EMERGENCY = "emergency"
    ABANDONED = "abandoned"


class StirAttestation(str, enum.Enum):
    A = "A"
    B = "B"
    C = "C"
    UNKNOWN = "unknown"


class CallRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "call_records"

    call_sid: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), index=True)
    from_number: Mapped[str] = mapped_column(String(20), index=True)
    to_number: Mapped[str] = mapped_column(String(20))
    direction: Mapped[str] = mapped_column(String(10), default="inbound")
    status: Mapped[CallStatus] = mapped_column(Enum(CallStatus), default=CallStatus.INCOMING)
    disposition: Mapped[CallDisposition | None] = mapped_column(
        Enum(CallDisposition), nullable=True
    )
    started_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trust_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    stir_attestation: Mapped[StirAttestation] = mapped_column(
        Enum(StirAttestation), default=StirAttestation.UNKNOWN
    )
    recording_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    caller_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    caller_intent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    screening_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    user = relationship("User", back_populates="calls", foreign_keys=[user_id])
    messages = relationship("Message", back_populates="call", lazy="selectin")
