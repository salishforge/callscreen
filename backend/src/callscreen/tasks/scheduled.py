"""Scheduled (Celery beat) tasks."""

import asyncio
import logging

import httpx

from callscreen.tasks.celery_app import app

logger = logging.getLogger("callscreen.tasks")

# Configurable blocklist URL; override via environment or settings
DEFAULT_BLOCKLIST_URL = "https://callscreen.example.com/blocklists/community.json"


@app.task(name="callscreen.tasks.scheduled.sync_blocklists")
def sync_blocklists(blocklist_url: str | None = None) -> dict:
    """Fetch external blocklists and aggregate community reports.

    Two-phase sync:
    1. Downloads a JSON blocklist from a configurable URL and updates
       NumberIntel records with community_blocklist_hit.
    2. Aggregates community reports to auto-flag numbers with >= N
       scam/spam reports.

    Expected JSON format for external blocklist:
        {"numbers": ["+15551234567", "+15559876543", ...]}

    Args:
        blocklist_url: URL to fetch the blocklist from. Falls back to
            DEFAULT_BLOCKLIST_URL if not provided.

    Returns:
        Dict with status and count of updated entries.
    """
    # Phase 1: External blocklist
    url = blocklist_url or DEFAULT_BLOCKLIST_URL
    logger.info("Starting blocklist sync from %s", url)

    external_updated = 0
    try:
        response = httpx.get(url, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        numbers = data.get("numbers", [])
        if numbers:
            external_updated = _update_blocklist_entries(numbers)
            logger.info("External blocklist sync: %d entries updated", external_updated)
        else:
            logger.info("External blocklist is empty, nothing to update")
    except httpx.HTTPError as exc:
        logger.error("Failed to fetch blocklist from %s: %s", url, exc)
    except (ValueError, AttributeError) as exc:
        logger.error("Failed to parse blocklist JSON: %s", exc)

    # Phase 2: Community report aggregation
    community_result = _run_community_aggregation()
    community_flagged = community_result.get("flagged", 0)
    logger.info("Community aggregation: %d numbers flagged", community_flagged)

    total_updated = external_updated + community_flagged
    logger.info("Blocklist sync complete: %d total entries updated", total_updated)
    return {
        "status": "ok",
        "updated": total_updated,
        "external_updated": external_updated,
        "community_flagged": community_flagged,
    }


def _run_community_aggregation() -> dict:
    """Run async community aggregation from sync Celery context."""
    try:
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

        from callscreen.config import get_settings
        from callscreen.intelligence.community import aggregate_blocklist

        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async def _aggregate():
            async with session_factory() as session:
                result = await aggregate_blocklist(session)
                await session.commit()
                return result

        # Run async code in sync Celery context
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(_aggregate())
        finally:
            loop.close()

        return result
    except Exception:
        logger.exception("Failed to run community aggregation")
        return {"status": "error", "flagged": 0}


@app.task(name="callscreen.tasks.scheduled.send_daily_digests")
def send_daily_digests() -> dict:
    """Send daily digest emails to all users.

    Iterates over every active user and delegates to
    :func:`callscreen.messaging.notifications.send_daily_digest`.
    Runs inside a fresh async event-loop so that the async DB session
    and adapter calls work correctly from the synchronous Celery worker.
    """
    logger.info("Starting daily digest task")
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_send_all_digests())
    finally:
        loop.close()


async def _send_all_digests() -> dict:
    from sqlalchemy import select as sa_select

    from callscreen.db.session import async_session_factory
    from callscreen.messaging.notifications import send_daily_digest
    from callscreen.models.user import User

    sent = 0
    failed = 0

    async with async_session_factory() as db:
        result = await db.execute(sa_select(User).where(User.is_active.is_(True)))
        users = result.scalars().all()

        for user in users:
            try:
                delivery = await send_daily_digest(user_id=str(user.id), db=db)
                if delivery is not None and delivery.success:
                    sent += 1
                elif delivery is not None:
                    failed += 1
            except Exception:
                logger.exception("Digest failed for user %s", user.id)
                failed += 1

        await db.commit()

    logger.info("Daily digests complete: sent=%d failed=%d", sent, failed)
    return {"status": "ok", "sent": sent, "failed": failed}


def _update_blocklist_entries(numbers: list[str]) -> int:
    """Update the number_intel table with community blocklist hits.

    Uses a synchronous DB session since this runs inside a Celery task.
    """
    updated = 0
    try:
        from sqlalchemy import create_engine, update
        from sqlalchemy.orm import Session

        from callscreen.config import get_settings
        from callscreen.models.number_intel import NumberIntel

        settings = get_settings()
        # Convert async URL to sync for Celery context
        sync_url = settings.database_url.replace("+asyncpg", "").replace("+aiosqlite", "")
        engine = create_engine(sync_url)

        with Session(engine) as session:
            for phone in numbers:
                phone = phone.strip()
                if not phone:
                    continue
                result = session.execute(
                    update(NumberIntel)
                    .where(NumberIntel.phone_number == phone)
                    .values(community_blocklist_hit=True)
                )
                if result.rowcount > 0:
                    updated += result.rowcount
                else:
                    # Create new entry if it doesn't exist
                    record = NumberIntel(
                        phone_number=phone,
                        community_blocklist_hit=True,
                    )
                    session.add(record)
                    updated += 1
            session.commit()
        engine.dispose()
    except Exception:
        logger.exception("Failed to update blocklist entries in DB")

    return updated
