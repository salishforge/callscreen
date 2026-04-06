"""RBAC permission checks."""

from fastapi import Depends, HTTPException, status

from callscreen.models.user import UserRole
from callscreen.security.auth import get_current_user


async def require_role(*roles: UserRole):
    """Create a dependency that requires the user to have one of the specified roles."""

    async def _check(current_user=Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return _check


async def require_admin(current_user=Depends(get_current_user)):
    """Require admin role."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


async def require_caretaker_or_admin(current_user=Depends(get_current_user)):
    """Require caretaker or admin role."""
    if current_user.role not in (UserRole.ADMIN, UserRole.CARETAKER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Caretaker or admin access required",
        )
    return current_user
