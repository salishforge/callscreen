"""Shared test fixtures."""

import asyncio
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from callscreen.config import Settings, get_settings
from callscreen.db.session import get_db
from callscreen.main import create_app
from callscreen.models.base import Base


def get_test_settings() -> Settings:
    return Settings(
        callscreen_env="development",
        callscreen_secret_key="test-secret-key-for-testing-only",
        callscreen_encryption_key="dGVzdC1lbmNyeXB0aW9uLWtleS0zMmJ5",
        database_url="sqlite+aiosqlite:///",
        redis_url="redis://localhost:6379/0",
        twilio_account_sid="ACtest",
        twilio_auth_token="",
    )


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    # Override dependencies
    app.dependency_overrides[get_settings] = get_test_settings
    app.dependency_overrides[get_db] = lambda: db_session

    async def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession):
    """Create an admin user for testing."""
    from callscreen.models.user import User, UserRole
    from callscreen.security.auth import hash_password

    user = User(
        id=uuid.uuid4(),
        email="admin@test.com",
        hashed_password=hash_password("testpassword123"),
        role=UserRole.ADMIN,
        phone_number="+15551234567",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def regular_user(db_session: AsyncSession):
    """Create a regular user for testing."""
    from callscreen.models.user import User, UserRole
    from callscreen.security.auth import hash_password

    user = User(
        id=uuid.uuid4(),
        email="user@test.com",
        hashed_password=hash_password("testpassword123"),
        role=UserRole.USER,
        phone_number="+15559876543",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_token(admin_user):
    """Get a JWT token for the admin user."""
    from callscreen.security.auth import create_access_token

    return create_access_token(user_id=str(admin_user.id), role=admin_user.role.value)


@pytest_asyncio.fixture
async def user_token(regular_user):
    """Get a JWT token for the regular user."""
    from callscreen.security.auth import create_access_token

    return create_access_token(user_id=str(regular_user.id), role=regular_user.role.value)
