"""Number intelligence service -- orchestrates providers, caches in DB."""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from callscreen.intelligence.base import NumberIntelProvider, NumberIntelResult
from callscreen.intelligence.community import get_community_score
from callscreen.intelligence.providers.stir_shaken import parse_stir_verstat
from callscreen.intelligence.providers.twilio_lookup import TwilioLookupProvider
from callscreen.intelligence.trust_score import calculate_trust_score
from callscreen.models.number_intel import LineType, NumberIntel

logger = logging.getLogger("callscreen.intelligence.service")

# Cache staleness threshold
CACHE_TTL = timedelta(hours=24)


def _map_line_type(raw: str | None) -> LineType:
    """Map a raw line type string to the LineType enum."""
    if raw is None:
        return LineType.UNKNOWN
    try:
        return LineType(raw)
    except ValueError:
        return LineType.UNKNOWN


class NumberIntelService:
    """Orchestrates number intelligence providers, caches results in DB."""

    def __init__(self, providers: list[NumberIntelProvider] | None = None) -> None:
        self._providers = providers or [TwilioLookupProvider()]

    async def get_intel(
        self,
        phone_number: str,
        db: AsyncSession,
        stir_verstat: str | None = None,
    ) -> NumberIntel:
        """Get intelligence for a phone number.

        Checks DB cache first; refreshes if stale (>24h). Runs all available
        providers, aggregates results, computes trust score, and upserts to DB.

        Args:
            phone_number: E.164 formatted phone number.
            db: Async database session.
            stir_verstat: Optional STIR/SHAKEN StirVerstat header value.

        Returns:
            NumberIntel ORM model with all available data.
        """
        # Check cache
        cached = await self._get_cached(phone_number, db)
        if cached and not self._is_stale(cached):
            logger.debug("Cache hit for %s (last_updated=%s)", phone_number, cached.last_updated)
            # Always update STIR attestation if a fresh value is provided
            if stir_verstat:
                stir_result = parse_stir_verstat(stir_verstat)
                if stir_result.stir_attestation and stir_result.stir_attestation != cached.stir_attestation:
                    cached.stir_attestation = stir_result.stir_attestation
                    await db.flush()
            return cached

        logger.info("Cache miss or stale for %s, running providers", phone_number)

        # Run all available providers
        aggregated = await self._run_providers(phone_number)

        # Merge STIR/SHAKEN data
        if stir_verstat:
            stir_result = parse_stir_verstat(stir_verstat)
            aggregated = self._merge_results(aggregated, stir_result)

        # Fetch community score if available
        community_score = await get_community_score(phone_number, db)

        # Compute trust score
        call_count = cached.call_count if cached else 0
        has_history = bool(cached and cached.disposition_history)
        trust_score = calculate_trust_score(
            aggregated, call_count, has_history, community_score=community_score
        )

        # Upsert to DB
        intel = await self._upsert(phone_number, aggregated, trust_score, cached, db)
        return intel

    async def _get_cached(
        self, phone_number: str, db: AsyncSession
    ) -> NumberIntel | None:
        """Fetch cached intel from the database."""
        result = await db.execute(
            select(NumberIntel).where(NumberIntel.phone_number == phone_number)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _is_stale(record: NumberIntel) -> bool:
        """Check if a cached record is older than the TTL."""
        if record.last_updated is None:
            return True
        return datetime.now(UTC) - record.last_updated.replace(tzinfo=UTC) > CACHE_TTL

    async def _run_providers(self, phone_number: str) -> NumberIntelResult:
        """Run all available providers and aggregate results."""
        aggregated = NumberIntelResult()

        for provider in self._providers:
            try:
                available = await provider.is_available()
                if not available:
                    logger.debug("Provider %s not available, skipping", provider.provider_name)
                    continue

                result = await provider.lookup(phone_number)
                aggregated = self._merge_results(aggregated, result)
                logger.info(
                    "Provider %s returned data for %s",
                    provider.provider_name,
                    phone_number,
                )
            except Exception:
                logger.exception(
                    "Provider %s failed for %s",
                    provider.provider_name,
                    phone_number,
                )
                # Continue with other providers

        return aggregated

    @staticmethod
    def _merge_results(
        base: NumberIntelResult, incoming: NumberIntelResult
    ) -> NumberIntelResult:
        """Merge incoming results into base, preferring non-None values from incoming."""
        merged = base.model_copy()
        for field_name in NumberIntelResult.model_fields:
            incoming_val = getattr(incoming, field_name)
            if incoming_val is not None:
                setattr(merged, field_name, incoming_val)
        return merged

    async def _upsert(
        self,
        phone_number: str,
        intel_data: NumberIntelResult,
        trust_score: float,
        existing: NumberIntel | None,
        db: AsyncSession,
    ) -> NumberIntel:
        """Create or update a NumberIntel record in the database."""
        now = datetime.now(UTC)

        if existing:
            record = existing
        else:
            record = NumberIntel(phone_number=phone_number)
            db.add(record)

        # Apply aggregated data
        if intel_data.carrier_name is not None:
            record.carrier_name = intel_data.carrier_name
        record.line_type = _map_line_type(intel_data.line_type)
        if intel_data.cnam is not None:
            record.cnam = intel_data.cnam
        if intel_data.nomorobo_score is not None:
            record.nomorobo_score = intel_data.nomorobo_score
        if intel_data.ftc_complaint_count is not None:
            record.ftc_complaint_count = intel_data.ftc_complaint_count
        if intel_data.stir_attestation is not None:
            record.stir_attestation = intel_data.stir_attestation
        if intel_data.is_medical_provider is not None:
            record.is_medical_provider = intel_data.is_medical_provider
        if intel_data.medical_provider_name is not None:
            record.medical_provider_name = intel_data.medical_provider_name
        if intel_data.community_blocklist_hit is not None:
            record.community_blocklist_hit = intel_data.community_blocklist_hit

        record.composite_trust_score = trust_score
        record.last_updated = now
        record.last_seen = now

        await db.flush()
        await db.refresh(record)
        return record
