"""Community intelligence service -- anonymous report aggregation and scoring."""

import hashlib
import logging

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from callscreen.models.community_report import CommunityReport, ReportType
from callscreen.models.number_intel import NumberIntel

logger = logging.getLogger("callscreen.intelligence.community")

# Minimum reports before a community score is calculated
MIN_REPORTS_FOR_SCORE = 3

# Threshold: numbers with this many scam/spam reports auto-flag the blocklist
BLOCKLIST_THRESHOLD = 5

# Report types considered negative
NEGATIVE_REPORT_TYPES = {ReportType.SCAM, ReportType.SPAM, ReportType.ROBOCALL, ReportType.SPOOFED}


def _hash_reporter(reporter_id: str) -> str:
    """SHA256 hash a reporter identity for anonymity."""
    return hashlib.sha256(reporter_id.encode("utf-8")).hexdigest()


async def submit_report(
    phone_number: str,
    report_type: str,
    category: str | None,
    description: str | None,
    reporter_id: str,
    db: AsyncSession,
) -> CommunityReport:
    """Submit an anonymous community report about a phone number.

    Args:
        phone_number: E.164 formatted phone number.
        report_type: One of the ReportType enum values.
        category: Optional category (e.g. "IRS scam", "car warranty").
        description: Optional free-text description.
        reporter_id: Raw reporter identity (will be hashed before storage).
        db: Async database session.

    Returns:
        The created CommunityReport record.
    """
    reporter_hash = _hash_reporter(reporter_id)
    report_enum = ReportType(report_type)

    report = CommunityReport(
        phone_number=phone_number,
        report_type=report_enum,
        category=category,
        description=description,
        reporter_hash=reporter_hash,
        is_verified=False,
    )
    db.add(report)
    await db.flush()
    await db.refresh(report)

    logger.info(
        "Community report submitted for %s (type=%s, category=%s)",
        phone_number,
        report_type,
        category,
    )
    return report


async def get_community_score(phone_number: str, db: AsyncSession) -> float | None:
    """Calculate a community trust score based on reports.

    Formula: (positive_reports / total_reports) if total >= MIN_REPORTS_FOR_SCORE.
    Returns 0.0 (all negative) to 1.0 (all positive), or None if insufficient data.

    Args:
        phone_number: E.164 formatted phone number.
        db: Async database session.

    Returns:
        Float between 0.0 and 1.0, or None if fewer than MIN_REPORTS_FOR_SCORE reports.
    """
    result = await db.execute(
        select(CommunityReport).where(CommunityReport.phone_number == phone_number)
    )
    reports = result.scalars().all()

    total = len(reports)
    if total < MIN_REPORTS_FOR_SCORE:
        return None

    positive_count = sum(1 for r in reports if r.report_type == ReportType.LEGITIMATE)
    return round(positive_count / total, 4)


async def get_reports(phone_number: str, db: AsyncSession) -> list[CommunityReport]:
    """Get all community reports for a phone number.

    Args:
        phone_number: E.164 formatted phone number.
        db: Async database session.

    Returns:
        List of CommunityReport records ordered by creation time.
    """
    result = await db.execute(
        select(CommunityReport)
        .where(CommunityReport.phone_number == phone_number)
        .order_by(CommunityReport.created_at.desc())
    )
    return list(result.scalars().all())


async def aggregate_blocklist(db: AsyncSession) -> dict:
    """Aggregate community reports into a blocklist of flagged numbers.

    Numbers with >= BLOCKLIST_THRESHOLD scam/spam/robocall/spoofed reports
    are flagged with community_blocklist_hit on their NumberIntel record.

    Args:
        db: Async database session.

    Returns:
        Dict with status and count of flagged numbers.
    """
    # Find numbers with enough negative reports
    negative_types = [rt.value for rt in NEGATIVE_REPORT_TYPES]
    stmt = (
        select(
            CommunityReport.phone_number,
            func.count(CommunityReport.id).label("report_count"),
        )
        .where(CommunityReport.report_type.in_(negative_types))
        .group_by(CommunityReport.phone_number)
        .having(func.count(CommunityReport.id) >= BLOCKLIST_THRESHOLD)
    )
    result = await db.execute(stmt)
    flagged_numbers = [row.phone_number for row in result.all()]

    if not flagged_numbers:
        logger.info("No numbers meet blocklist threshold")
        return {"status": "ok", "flagged": 0, "numbers": []}

    # Update existing NumberIntel records
    updated = 0
    for phone in flagged_numbers:
        # Check if record exists
        existing = await db.execute(
            select(NumberIntel).where(NumberIntel.phone_number == phone)
        )
        record = existing.scalar_one_or_none()

        if record:
            if not record.community_blocklist_hit:
                record.community_blocklist_hit = True
                updated += 1
        else:
            # Create new NumberIntel entry for this number
            new_record = NumberIntel(
                phone_number=phone,
                community_blocklist_hit=True,
            )
            db.add(new_record)
            updated += 1

    await db.flush()

    logger.info(
        "Community blocklist aggregation complete: %d numbers flagged (%d updated)",
        len(flagged_numbers),
        updated,
    )
    return {"status": "ok", "flagged": len(flagged_numbers), "numbers": flagged_numbers}
