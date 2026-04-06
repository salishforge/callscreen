"""Audit logging service."""

import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from callscreen.models.audit import AuditLog

logger = logging.getLogger("callscreen.audit")


async def write_audit_log(
    db: AsyncSession,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    user_id: str | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Write an entry to the audit log."""
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
        timestamp=datetime.now(UTC),
    )
    db.add(entry)
    logger.info(
        "AUDIT: action=%s resource=%s/%s user=%s",
        action,
        resource_type,
        resource_id,
        user_id,
    )
