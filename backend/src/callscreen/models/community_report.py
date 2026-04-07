"""Community report model for anonymous call reports."""

import enum

from sqlalchemy import Boolean, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from callscreen.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ReportType(str, enum.Enum):
    SCAM = "scam"
    SPAM = "spam"
    ROBOCALL = "robocall"
    SPOOFED = "spoofed"
    LEGITIMATE = "legitimate"


class CommunityReport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Anonymous community report about a phone number."""

    __tablename__ = "community_reports"

    phone_number: Mapped[str] = mapped_column(String(20), index=True)
    report_type: Mapped[ReportType] = mapped_column(Enum(ReportType))
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    reporter_hash: Mapped[str] = mapped_column(String(64))  # SHA256 hex digest
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
