"""Number intelligence cache model."""

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, Integer, String
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from callscreen.models.base import Base, UUIDPrimaryKeyMixin


class LineType(str, enum.Enum):
    LANDLINE = "landline"
    MOBILE = "mobile"
    VOIP = "voip"
    UNKNOWN = "unknown"


class NumberIntel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "number_intel"

    phone_number: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    carrier_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    line_type: Mapped[LineType] = mapped_column(Enum(LineType), default=LineType.UNKNOWN)
    cnam: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nomorobo_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ftc_complaint_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stir_attestation: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_medical_provider: Mapped[bool] = mapped_column(Boolean, default=False)
    medical_provider_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    community_blocklist_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    composite_trust_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    call_count: Mapped[int] = mapped_column(Integer, default=0)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    disposition_history: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
