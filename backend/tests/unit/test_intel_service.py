"""Tests for the NumberIntelService orchestration layer."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from callscreen.intelligence.base import NumberIntelProvider, NumberIntelResult
from callscreen.intelligence.service import NumberIntelService
from callscreen.models.number_intel import LineType, NumberIntel


class FakeProvider(NumberIntelProvider):
    """Fake provider for testing that returns configurable data."""

    provider_name = "fake"

    def __init__(self, result: NumberIntelResult | None = None, available: bool = True):
        self._result = result or NumberIntelResult()
        self._available = available

    async def lookup(self, phone_number: str) -> NumberIntelResult:
        return self._result

    async def is_available(self) -> bool:
        return self._available


class FailingProvider(NumberIntelProvider):
    """Provider that always raises an exception."""

    provider_name = "failing"

    async def lookup(self, phone_number: str) -> NumberIntelResult:
        raise RuntimeError("Provider failure")

    async def is_available(self) -> bool:
        return True


@pytest.mark.asyncio
class TestNumberIntelService:

    async def test_fresh_lookup_creates_record(self, db_session: AsyncSession):
        """A lookup for a new number should create a NumberIntel record."""
        provider = FakeProvider(
            NumberIntelResult(
                carrier_name="Test Carrier",
                line_type="landline",
                cnam="Test Caller",
            )
        )
        service = NumberIntelService(providers=[provider])

        intel = await service.get_intel("+15551234567", db_session)

        assert intel.phone_number == "+15551234567"
        assert intel.carrier_name == "Test Carrier"
        assert intel.line_type == LineType.LANDLINE
        assert intel.cnam == "Test Caller"
        assert intel.composite_trust_score is not None
        assert intel.last_updated is not None

    async def test_cache_hit_skips_providers(self, db_session: AsyncSession):
        """If a fresh cached record exists, providers should not be called."""
        # Pre-populate cache
        record = NumberIntel(
            phone_number="+15559999999",
            carrier_name="Cached Carrier",
            line_type=LineType.MOBILE,
            composite_trust_score=0.75,
            last_updated=datetime.now(UTC),
        )
        db_session.add(record)
        await db_session.flush()

        # Provider that would overwrite carrier_name
        provider = FakeProvider(
            NumberIntelResult(carrier_name="New Carrier"),
        )
        service = NumberIntelService(providers=[provider])

        intel = await service.get_intel("+15559999999", db_session)

        # Should return cached value, not the provider value
        assert intel.carrier_name == "Cached Carrier"

    async def test_stale_cache_refreshes(self, db_session: AsyncSession):
        """A stale cached record (>24h old) should trigger provider refresh."""
        stale_time = datetime.now(UTC) - timedelta(hours=25)
        record = NumberIntel(
            phone_number="+15558888888",
            carrier_name="Old Carrier",
            line_type=LineType.UNKNOWN,
            composite_trust_score=0.5,
            last_updated=stale_time,
        )
        db_session.add(record)
        await db_session.flush()

        provider = FakeProvider(
            NumberIntelResult(carrier_name="Updated Carrier", line_type="landline"),
        )
        service = NumberIntelService(providers=[provider])

        intel = await service.get_intel("+15558888888", db_session)

        assert intel.carrier_name == "Updated Carrier"
        assert intel.line_type == LineType.LANDLINE
        # Compare timezone-aware timestamps (SQLite may strip tz info)
        updated = intel.last_updated.replace(tzinfo=UTC) if intel.last_updated.tzinfo is None else intel.last_updated
        assert updated > stale_time

    async def test_failing_provider_does_not_crash(self, db_session: AsyncSession):
        """A provider that raises should not crash the service."""
        service = NumberIntelService(providers=[FailingProvider()])

        # Should not raise
        intel = await service.get_intel("+15557777777", db_session)

        assert intel.phone_number == "+15557777777"
        assert intel.composite_trust_score is not None

    async def test_multiple_providers_aggregated(self, db_session: AsyncSession):
        """Results from multiple providers should be merged."""
        provider_a = FakeProvider(
            NumberIntelResult(carrier_name="CarrierA", line_type="landline"),
        )
        provider_b = FakeProvider(
            NumberIntelResult(cnam="CallerB", ftc_complaint_count=0),
        )
        service = NumberIntelService(providers=[provider_a, provider_b])

        intel = await service.get_intel("+15556666666", db_session)

        assert intel.carrier_name == "CarrierA"
        assert intel.cnam == "CallerB"
        assert intel.ftc_complaint_count == 0
        assert intel.line_type == LineType.LANDLINE

    async def test_unavailable_provider_skipped(self, db_session: AsyncSession):
        """Providers that report unavailable should be skipped gracefully."""
        unavailable = FakeProvider(
            NumberIntelResult(carrier_name="ShouldNotAppear"),
            available=False,
        )
        available = FakeProvider(
            NumberIntelResult(carrier_name="AvailableCarrier"),
            available=True,
        )
        service = NumberIntelService(providers=[unavailable, available])

        intel = await service.get_intel("+15555555555", db_session)

        assert intel.carrier_name == "AvailableCarrier"

    async def test_stir_verstat_merged(self, db_session: AsyncSession):
        """STIR/SHAKEN verstat should be merged into the result."""
        provider = FakeProvider(
            NumberIntelResult(carrier_name="TestCarrier"),
        )
        service = NumberIntelService(providers=[provider])

        intel = await service.get_intel(
            "+15554444444", db_session, stir_verstat="TN-Validation-Passed-A"
        )

        assert intel.stir_attestation == "A"
