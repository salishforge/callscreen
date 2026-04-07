"""Community report schemas for request/response validation."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CommunityReportCreate(BaseModel):
    """Schema for submitting a community report."""

    phone_number: str = Field(..., description="E.164 formatted phone number")
    report_type: str = Field(
        ...,
        description="Report type: scam, spam, robocall, spoofed, or legitimate",
    )
    category: str | None = Field(
        None, description="Category (e.g. 'IRS scam', 'car warranty')"
    )
    description: str | None = Field(None, description="Optional description")


class CommunityReportResponse(BaseModel):
    """Schema for community report API responses."""

    id: uuid.UUID
    phone_number: str
    report_type: str
    category: str | None = None
    description: str | None = None
    reporter_hash: str
    is_verified: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CommunityStatsResponse(BaseModel):
    """Schema for aggregate community stats."""

    total_reports: int
    unique_numbers: int
    reports_by_type: dict[str, int]
    top_reported_numbers: list[dict]
    blocklist_count: int
