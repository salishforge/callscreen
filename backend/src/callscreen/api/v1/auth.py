"""Authentication endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from callscreen.db.session import get_db
from callscreen.schemas.auth import LoginRequest, LoginResponse, RegisterRequest, UserResponse
from callscreen.security.auth import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    hash_password,
    verify_password,
)
from callscreen.security.permissions import require_admin
from callscreen.security.rate_limiter import rate_limit

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    """Register a new user (admin only)."""
    from callscreen.models.user import User

    existing = await db.execute(select(User).where(User.email == request.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=request.email,
        hashed_password=hash_password(request.password),
        role=request.role,
        phone_number=request.phone_number or "",
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    return UserResponse(
        id=str(user.id),
        email=user.email,
        role=user.role.value,
        phone_number=user.phone_number,
        is_active=user.is_active,
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _rl=Depends(rate_limit("login")),
):
    """Authenticate and receive tokens."""
    from callscreen.models.user import User

    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    access_token = create_access_token(user_id=str(user.id), role=user.role.value)
    refresh_token = create_refresh_token(user_id=str(user.id))

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,  # 7 days
    )

    return LoginResponse(access_token=access_token, token_type="bearer")


@router.post("/refresh", response_model=LoginResponse)
async def refresh(
    request_obj: object = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Refresh access token using refresh cookie."""
    from fastapi import Request

    from callscreen.models.user import User
    from callscreen.security.auth import decode_token

    req: Request = request_obj  # type: ignore[assignment]
    refresh_token = req.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")

    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid user")

    access_token = create_access_token(user_id=str(user.id), role=user.role.value)
    return LoginResponse(access_token=access_token, token_type="bearer")


@router.post("/logout")
async def logout(response: Response):
    """Invalidate refresh token."""
    response.delete_cookie("refresh_token")
    return {"status": "ok"}


@router.get("/me", response_model=UserResponse)
async def me(current_user=Depends(get_current_user)):
    """Get current user profile."""
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        role=current_user.role.value,
        phone_number=current_user.phone_number,
        is_active=current_user.is_active,
    )
