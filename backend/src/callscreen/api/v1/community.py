"""Community intelligence API endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from callscreen.db.session import get_db
from callscreen.intelligence.community import (
    BLOCKLIST_THRESHOLD,
    NEGATIVE_REPORT_TYPES,
    get_community_score,
    get_reports,
    submit_report,
)
from callscreen.models.community_report import CommunityReport, ReportType
from callscreen.models.user import User, UserRole
from callscreen.schemas.community import (
    CommunityReportCreate,
    CommunityReportResponse,
    CommunityStatsResponse,
)
from callscreen.security.auth import get_current_user
from callscreen.utils.phone import normalize_e164

logger = logging.getLogger("callscreen.api.community")

router = APIRouter()


@router.post("/report", response_model=CommunityReportResponse, status_code=201)
async def create_report(
    payload: CommunityReportCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit a community report about a phone number.

    Any authenticated user can submit a report. The reporter identity
    is SHA256-hashed for anonymity.
    """
    # Validate report type
    try:
        ReportType(payload.report_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid report type: {payload.report_type}. "
            f"Must be one of: {', '.join(rt.value for rt in ReportType)}",
        )

    # Normalize phone number
    try:
        normalized = normalize_e164(payload.phone_number)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid phone number format",
        )

    try:
        report = await submit_report(
            phone_number=normalized,
            report_type=payload.report_type,
            category=payload.category,
            description=payload.description,
            reporter_id=str(current_user.id),
            db=db,
        )
        await db.commit()
        return CommunityReportResponse.model_validate(report)
    except Exception:
        await db.rollback()
        logger.exception("Failed to submit community report")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit report",
        )


@router.get("/reports/{phone_number}", response_model=list[CommunityReportResponse])
async def get_phone_reports(
    phone_number: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all community reports for a phone number.

    Requires admin or caretaker role.
    """
    if current_user.role not in (UserRole.ADMIN, UserRole.CARETAKER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and caretakers can view community reports",
        )

    # Normalize phone number
    try:
        normalized = normalize_e164(phone_number)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid phone number format",
        )

    try:
        reports = await get_reports(normalized, db)
        return [CommunityReportResponse.model_validate(r) for r in reports]
    except Exception:
        logger.exception("Failed to get community reports for %s", phone_number)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve reports",
        )


@router.get("/stats", response_model=CommunityStatsResponse)
async def get_community_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get aggregate community report statistics.

    Requires admin role.
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view community stats",
        )

    try:
        # Total reports
        total_result = await db.execute(select(func.count(CommunityReport.id)))
        total_reports = total_result.scalar() or 0

        # Unique numbers
        unique_result = await db.execute(
            select(func.count(func.distinct(CommunityReport.phone_number)))
        )
        unique_numbers = unique_result.scalar() or 0

        # Reports by type
        type_result = await db.execute(
            select(
                CommunityReport.report_type,
                func.count(CommunityReport.id).label("count"),
            ).group_by(CommunityReport.report_type)
        )
        reports_by_type = {row.report_type.value if hasattr(row.report_type, 'value') else str(row.report_type): row.count for row in type_result.all()}

        # Top reported numbers (top 10 by report count)
        top_result = await db.execute(
            select(
                CommunityReport.phone_number,
                func.count(CommunityReport.id).label("report_count"),
            )
            .group_by(CommunityReport.phone_number)
            .order_by(func.count(CommunityReport.id).desc())
            .limit(10)
        )
        top_reported = [
            {"phone_number": row.phone_number, "report_count": row.report_count}
            for row in top_result.all()
        ]

        # Numbers meeting blocklist threshold
        negative_types = [rt.value for rt in NEGATIVE_REPORT_TYPES]
        blocklist_result = await db.execute(
            select(func.count()).select_from(
                select(CommunityReport.phone_number)
                .where(CommunityReport.report_type.in_(negative_types))
                .group_by(CommunityReport.phone_number)
                .having(func.count(CommunityReport.id) >= BLOCKLIST_THRESHOLD)
                .subquery()
            )
        )
        blocklist_count = blocklist_result.scalar() or 0

        return CommunityStatsResponse(
            total_reports=total_reports,
            unique_numbers=unique_numbers,
            reports_by_type=reports_by_type,
            top_reported_numbers=top_reported,
            blocklist_count=blocklist_count,
        )
    except Exception:
        logger.exception("Failed to compute community stats")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve stats",
        )
