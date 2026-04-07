"""Tests for community intelligence service."""

import hashlib
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from callscreen.intelligence.community import (
    BLOCKLIST_THRESHOLD,
    MIN_REPORTS_FOR_SCORE,
    _hash_reporter,
    aggregate_blocklist,
    get_community_score,
    get_reports,
    submit_report,
)
from callscreen.models.community_report import CommunityReport, ReportType
from callscreen.models.number_intel import NumberIntel


class TestHashReporter:
    """Test reporter identity hashing."""

    def test_hash_produces_sha256(self):
        """Reporter hash should be a SHA256 hex digest."""
        result = _hash_reporter("user123")
        expected = hashlib.sha256("user123".encode("utf-8")).hexdigest()
        assert result == expected
        assert len(result) == 64

    def test_hash_is_deterministic(self):
        """Same input should always produce the same hash."""
        assert _hash_reporter("abc") == _hash_reporter("abc")

    def test_different_inputs_different_hashes(self):
        """Different inputs should produce different hashes."""
        assert _hash_reporter("user1") != _hash_reporter("user2")


@pytest.mark.asyncio
class TestSubmitReport:
    """Test community report submission."""

    async def test_submit_creates_report(self, db_session: AsyncSession):
        """Submitting a report should create a CommunityReport record."""
        report = await submit_report(
            phone_number="+15551234567",
            report_type="scam",
            category="IRS scam",
            description="Claimed I owed taxes",
            reporter_id="user-abc-123",
            db=db_session,
        )
        await db_session.commit()

        assert report.phone_number == "+15551234567"
        assert report.report_type == ReportType.SCAM
        assert report.category == "IRS scam"
        assert report.description == "Claimed I owed taxes"
        assert report.reporter_hash == _hash_reporter("user-abc-123")
        assert report.is_verified is False
        assert report.id is not None

    async def test_submit_hashes_reporter_identity(self, db_session: AsyncSession):
        """Reporter ID should be hashed, not stored in plain text."""
        reporter_id = "secret-identity-456"
        report = await submit_report(
            phone_number="+15559876543",
            report_type="spam",
            category=None,
            description=None,
            reporter_id=reporter_id,
            db=db_session,
        )
        await db_session.commit()

        assert report.reporter_hash != reporter_id
        assert report.reporter_hash == hashlib.sha256(reporter_id.encode()).hexdigest()

    async def test_submit_with_nullable_fields(self, db_session: AsyncSession):
        """Category and description should be optional."""
        report = await submit_report(
            phone_number="+15551112222",
            report_type="robocall",
            category=None,
            description=None,
            reporter_id="user-xyz",
            db=db_session,
        )
        await db_session.commit()

        assert report.category is None
        assert report.description is None

    async def test_submit_invalid_report_type_raises(self, db_session: AsyncSession):
        """Invalid report type should raise ValueError."""
        with pytest.raises(ValueError):
            await submit_report(
                phone_number="+15551234567",
                report_type="invalid_type",
                category=None,
                description=None,
                reporter_id="user-1",
                db=db_session,
            )


@pytest.mark.asyncio
class TestGetCommunityScore:
    """Test community score calculation."""

    async def test_no_reports_returns_none(self, db_session: AsyncSession):
        """No reports should return None."""
        score = await get_community_score("+15550000000", db_session)
        assert score is None

    async def test_fewer_than_minimum_returns_none(self, db_session: AsyncSession):
        """Fewer than MIN_REPORTS_FOR_SCORE reports should return None."""
        # Submit fewer reports than the threshold
        for i in range(MIN_REPORTS_FOR_SCORE - 1):
            await submit_report(
                phone_number="+15551111111",
                report_type="scam",
                category=None,
                description=None,
                reporter_id=f"user-{i}",
                db=db_session,
            )
        await db_session.commit()

        score = await get_community_score("+15551111111", db_session)
        assert score is None

    async def test_all_scam_reports_score_zero(self, db_session: AsyncSession):
        """All scam reports should produce a score of 0.0."""
        for i in range(5):
            await submit_report(
                phone_number="+15552222222",
                report_type="scam",
                category="IRS",
                description=None,
                reporter_id=f"user-{i}",
                db=db_session,
            )
        await db_session.commit()

        score = await get_community_score("+15552222222", db_session)
        assert score == 0.0

    async def test_all_legitimate_reports_score_one(self, db_session: AsyncSession):
        """All legitimate reports should produce a score of 1.0."""
        for i in range(4):
            await submit_report(
                phone_number="+15553333333",
                report_type="legitimate",
                category=None,
                description=None,
                reporter_id=f"user-{i}",
                db=db_session,
            )
        await db_session.commit()

        score = await get_community_score("+15553333333", db_session)
        assert score == 1.0

    async def test_mixed_reports_score(self, db_session: AsyncSession):
        """Mixed reports should produce a proportional score."""
        # 2 legitimate + 2 scam + 1 spam = 2/5 = 0.4
        for i in range(2):
            await submit_report(
                phone_number="+15554444444",
                report_type="legitimate",
                category=None,
                description=None,
                reporter_id=f"legit-{i}",
                db=db_session,
            )
        for i in range(2):
            await submit_report(
                phone_number="+15554444444",
                report_type="scam",
                category=None,
                description=None,
                reporter_id=f"scam-{i}",
                db=db_session,
            )
        await submit_report(
            phone_number="+15554444444",
            report_type="spam",
            category=None,
            description=None,
            reporter_id="spam-0",
            db=db_session,
        )
        await db_session.commit()

        score = await get_community_score("+15554444444", db_session)
        assert score == 0.4


@pytest.mark.asyncio
class TestGetReports:
    """Test report retrieval."""

    async def test_get_reports_for_number(self, db_session: AsyncSession):
        """Should return all reports for a given phone number."""
        for i in range(3):
            await submit_report(
                phone_number="+15555555555",
                report_type="scam",
                category=None,
                description=None,
                reporter_id=f"user-{i}",
                db=db_session,
            )
        await db_session.commit()

        reports = await get_reports("+15555555555", db_session)
        assert len(reports) == 3
        assert all(r.phone_number == "+15555555555" for r in reports)

    async def test_get_reports_empty(self, db_session: AsyncSession):
        """Should return empty list for a number with no reports."""
        reports = await get_reports("+15550000000", db_session)
        assert reports == []


@pytest.mark.asyncio
class TestAggregateBlocklist:
    """Test blocklist aggregation from community reports."""

    async def test_no_reports_flags_nothing(self, db_session: AsyncSession):
        """With no reports, no numbers should be flagged."""
        result = await aggregate_blocklist(db_session)
        assert result["flagged"] == 0

    async def test_below_threshold_not_flagged(self, db_session: AsyncSession):
        """Numbers with fewer than BLOCKLIST_THRESHOLD reports should not be flagged."""
        for i in range(BLOCKLIST_THRESHOLD - 1):
            await submit_report(
                phone_number="+15556666666",
                report_type="scam",
                category=None,
                description=None,
                reporter_id=f"user-{i}",
                db=db_session,
            )
        await db_session.commit()

        result = await aggregate_blocklist(db_session)
        assert "+15556666666" not in result.get("numbers", [])

    async def test_at_threshold_flagged(self, db_session: AsyncSession):
        """Numbers with exactly BLOCKLIST_THRESHOLD scam reports should be flagged."""
        for i in range(BLOCKLIST_THRESHOLD):
            await submit_report(
                phone_number="+15557777777",
                report_type="scam",
                category=None,
                description=None,
                reporter_id=f"user-{i}",
                db=db_session,
            )
        await db_session.commit()

        result = await aggregate_blocklist(db_session)
        assert result["flagged"] >= 1
        assert "+15557777777" in result["numbers"]

    async def test_flagged_creates_number_intel_record(self, db_session: AsyncSession):
        """Flagged numbers should get a NumberIntel record with community_blocklist_hit."""
        for i in range(BLOCKLIST_THRESHOLD + 2):
            await submit_report(
                phone_number="+15558888888",
                report_type="spam",
                category=None,
                description=None,
                reporter_id=f"user-{i}",
                db=db_session,
            )
        await db_session.commit()

        await aggregate_blocklist(db_session)
        await db_session.commit()

        from sqlalchemy import select
        result = await db_session.execute(
            select(NumberIntel).where(NumberIntel.phone_number == "+15558888888")
        )
        record = result.scalar_one_or_none()
        assert record is not None
        assert record.community_blocklist_hit is True

    async def test_legitimate_reports_not_flagged(self, db_session: AsyncSession):
        """Numbers with only legitimate reports should not be flagged."""
        for i in range(BLOCKLIST_THRESHOLD + 5):
            await submit_report(
                phone_number="+15559999999",
                report_type="legitimate",
                category=None,
                description=None,
                reporter_id=f"user-{i}",
                db=db_session,
            )
        await db_session.commit()

        result = await aggregate_blocklist(db_session)
        assert "+15559999999" not in result.get("numbers", [])
