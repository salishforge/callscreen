"""Integration tests for the Number Intel API endpoint."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from callscreen.api.v1.intel import get_intel_service
from callscreen.config import get_settings
from callscreen.db.session import get_db
from callscreen.intelligence.base import NumberIntelResult
from callscreen.intelligence.service import NumberIntelService
from callscreen.main import create_app
from callscreen.models.number_intel import LineType, NumberIntel
from callscreen.models.user import User, UserRole
from callscreen.security.auth import create_access_token, hash_password


@pytest_asyncio.fixture
async def intel_client(db_session: AsyncSession) -> AsyncClient:
    """Create a test client with a mocked intel service."""
    app = create_app()

    # Create a mock service that returns a pre-populated NumberIntel
    async def _override_db():
        yield db_session

    def _test_settings():
        from callscreen.config import Settings
        return Settings(
            callscreen_env="development",
            callscreen_secret_key="test-secret-key-for-testing-only",
            callscreen_encryption_key="dGVzdC1lbmNyeXB0aW9uLWtleS0zMmJ5",
            database_url="sqlite+aiosqlite:///",
            redis_url="redis://localhost:6379/0",
            twilio_account_sid="ACtest",
            twilio_auth_token="",
        )

    app.dependency_overrides[get_settings] = _test_settings
    app.dependency_overrides[get_db] = _override_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_for_intel(db_session: AsyncSession) -> tuple[User, str]:
    """Create an admin user and return (user, token)."""
    user = User(
        id=uuid.uuid4(),
        email="intel-admin@test.com",
        hashed_password=hash_password("testpassword123"),
        role=UserRole.ADMIN,
        phone_number="+15550001111",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    token = create_access_token(user_id=str(user.id), role=user.role.value)
    return user, token


@pytest_asyncio.fixture
async def caretaker_for_intel(db_session: AsyncSession) -> tuple[User, str]:
    """Create a caretaker user and return (user, token)."""
    user = User(
        id=uuid.uuid4(),
        email="intel-caretaker@test.com",
        hashed_password=hash_password("testpassword123"),
        role=UserRole.CARETAKER,
        phone_number="+15550002222",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    token = create_access_token(user_id=str(user.id), role=user.role.value)
    return user, token


@pytest_asyncio.fixture
async def regular_for_intel(db_session: AsyncSession) -> tuple[User, str]:
    """Create a regular user and return (user, token)."""
    user = User(
        id=uuid.uuid4(),
        email="intel-user@test.com",
        hashed_password=hash_password("testpassword123"),
        role=UserRole.USER,
        phone_number="+15550003333",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    token = create_access_token(user_id=str(user.id), role=user.role.value)
    return user, token


@pytest.mark.asyncio
class TestIntelAPI:

    async def test_admin_can_get_intel(
        self, intel_client: AsyncClient, admin_for_intel, db_session: AsyncSession
    ):
        """Admin users should be able to access the intel endpoint."""
        _, token = admin_for_intel

        # Pre-populate a record so the service returns it
        record = NumberIntel(
            phone_number="+15551234567",
            carrier_name="Verizon",
            line_type=LineType.LANDLINE,
            cnam="Test Caller",
            composite_trust_score=0.85,
            last_updated=datetime.now(UTC),
        )
        db_session.add(record)
        await db_session.flush()

        response = await intel_client.get(
            "/api/v1/intel/+15551234567",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["phone_number"] == "+15551234567"
        assert data["carrier_name"] == "Verizon"
        assert data["composite_trust_score"] is not None

    async def test_regular_user_forbidden(
        self, intel_client: AsyncClient, regular_for_intel
    ):
        """Regular users should be denied access (403)."""
        _, token = regular_for_intel

        response = await intel_client.get(
            "/api/v1/intel/+15551234567",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403

    async def test_unauthenticated_rejected(self, intel_client: AsyncClient):
        """Requests without a token should be rejected."""
        response = await intel_client.get("/api/v1/intel/+15551234567")
        # HTTPBearer returns 403 when no credentials are provided
        assert response.status_code in (401, 403)

    async def test_caretaker_can_get_intel(
        self, intel_client: AsyncClient, caretaker_for_intel, db_session: AsyncSession
    ):
        """Caretaker users should also be allowed access."""
        _, token = caretaker_for_intel

        record = NumberIntel(
            phone_number="+15559876543",
            carrier_name="AT&T",
            line_type=LineType.MOBILE,
            composite_trust_score=0.6,
            last_updated=datetime.now(UTC),
        )
        db_session.add(record)
        await db_session.flush()

        response = await intel_client.get(
            "/api/v1/intel/+15559876543",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["phone_number"] == "+15559876543"
