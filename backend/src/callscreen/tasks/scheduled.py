"""Scheduled (Celery beat) tasks."""

import logging

from callscreen.tasks.celery_app import app

logger = logging.getLogger("callscreen.tasks")


@app.task(name="callscreen.tasks.scheduled.sync_blocklists")
def sync_blocklists() -> dict:
    """Fetch and update community blocklists."""
    logger.info("Starting blocklist sync")
    # TODO: Implement in Sprint 1.3
    return {"status": "ok", "updated": 0}
