"""Number intelligence API endpoint."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from callscreen.db.session import get_db
from callscreen.intelligence.service import NumberIntelService
from callscreen.models.user import UserRole
from callscreen.schemas.number_intel import NumberIntelResponse
from callscreen.security.auth import get_current_user
from callscreen.utils.phone import normalize_e164

logger = logging.getLogger("callscreen.api.intel")

router = APIRouter()

# Module-level service instance (providers can be swapped in tests)
_service = NumberIntelService()


def get_intel_service() -> NumberIntelService:
    """Dependency for the intel service (allows test overrides)."""
    return _service


@router.get("/{phone_number}", response_model=NumberIntelResponse)
async def get_number_intel(
    phone_number: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    service: NumberIntelService = Depends(get_intel_service),
):
    """Look up intelligence data for a phone number.

    Returns cached data if fresh, otherwise triggers a new lookup.
    Requires admin or caretaker role.
    """
    # Role check
    if current_user.role not in (UserRole.ADMIN, UserRole.CARETAKER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and caretakers can access number intelligence",
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
        intel = await service.get_intel(normalized, db)
        return NumberIntelResponse.model_validate(intel)
    except Exception:
        logger.exception("Failed to get intel for %s", phone_number)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve number intelligence",
        )
