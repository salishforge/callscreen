"""Integration tests for the Community API endpoints."""

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from callscreen.config import get_settings
from callscreen.db.session import get_db
from callscreen.intelligence.community import submit_report
from callscreen.main import create_app
from callscreen.models.user import User, UserRole
from callscreen.security.auth import create_access_token, hash_password


@pytest_asyncio.fixture
async def community_client(db_session: AsyncSession) -> AsyncClient:
    """Create a test client for community endpoints."""
    app = create_app()

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
async def admin_for_community(db_session: AsyncSession) -> tuple[User, str]:
    """Create an admin user and return (user, token)."""
    user = User(
        id=uuid.uuid4(),
        email="community-admin@test.com",
        hashed_password=hash_password("testpassword123"),
        role=UserRole.ADMIN,
        phone_number="+15550010001",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    token = create_access_token(user_id=str(user.id), role=user.role.value)
    return user, token


@pytest_asyncio.fixture
async def caretaker_for_community(db_session: AsyncSession) -> tuple[User, str]:
    """Create a caretaker user and return (user, token)."""
    user = User(
        id=uuid.uuid4(),
        email="community-caretaker@test.com",
        hashed_password=hash_password("testpassword123"),
        role=UserRole.CARETAKER,
        phone_number="+15550020002",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    token = create_access_token(user_id=str(user.id), role=user.role.value)
    return user, token


@pytest_asyncio.fixture
async def regular_for_community(db_session: AsyncSession) -> tuple[User, str]:
    """Create a regular user and return (user, token)."""
    user = User(
        id=uuid.uuid4(),
        email="community-user@test.com",
        hashed_password=hash_password("testpassword123"),
        role=UserRole.USER,
        phone_number="+15550030003",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    token = create_access_token(user_id=str(user.id), role=user.role.value)
    return user, token


@pytest.mark.asyncio
class TestCommunityReportAPI:

    async def test_submit_report_authenticated(
        self, community_client: AsyncClient, regular_for_community
    ):
        """Any authenticated user can submit a report."""
        _, token = regular_for_community

        response = await community_client.post(
            "/api/v1/community/report",
            json={
                "phone_number": "+15551234567",
                "report_type": "scam",
                "category": "IRS scam",
                "description": "Claimed I owed taxes",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["phone_number"] == "+15551234567"
        assert data["report_type"] == "scam"
        assert data["category"] == "IRS scam"
        assert data["is_verified"] is False
        assert "reporter_hash" in data

    async def test_submit_report_unauthenticated_rejected(
        self, community_client: AsyncClient
    ):
        """Unauthenticated requests should be rejected."""
        response = await community_client.post(
            "/api/v1/community/report",
            json={
                "phone_number": "+15551234567",
                "report_type": "scam",
            },
        )
        assert response.status_code in (401, 403)

    async def test_submit_report_invalid_type(
        self, community_client: AsyncClient, regular_for_community
    ):
        """Invalid report type should return 400."""
        _, token = regular_for_community

        response = await community_client.post(
            "/api/v1/community/report",
            json={
                "phone_number": "+15551234567",
                "report_type": "invalid_type",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400

    async def test_get_reports_admin(
        self,
        community_client: AsyncClient,
        admin_for_community,
        db_session: AsyncSession,
    ):
        """Admin should be able to retrieve reports for a number."""
        user, token = admin_for_community

        # Pre-populate reports
        for i in range(3):
            await submit_report(
                phone_number="+15559876543",
                report_type="spam",
                category="car warranty",
                description=None,
                reporter_id=f"reporter-{i}",
                db=db_session,
            )
        await db_session.commit()

        response = await community_client.get(
            "/api/v1/community/reports/+15559876543",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert all(r["phone_number"] == "+15559876543" for r in data)

    async def test_get_reports_regular_user_forbidden(
        self, community_client: AsyncClient, regular_for_community
    ):
        """Regular users should not be able to view reports."""
        _, token = regular_for_community

        response = await community_client.get(
            "/api/v1/community/reports/+15551234567",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403

    async def test_get_reports_caretaker_allowed(
        self,
        community_client: AsyncClient,
        caretaker_for_community,
    ):
        """Caretakers should be allowed to view reports."""
        _, token = caretaker_for_community

        response = await community_client.get(
            "/api/v1/community/reports/+15551234567",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200

    async def test_stats_admin_only(
        self,
        community_client: AsyncClient,
        admin_for_community,
        regular_for_community,
    ):
        """Only admin should be able to view stats."""
        _, admin_token = admin_for_community
        _, user_token = regular_for_community

        # Admin should succeed
        admin_response = await community_client.get(
            "/api/v1/community/stats",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert admin_response.status_code == 200
        data = admin_response.json()
        assert "total_reports" in data
        assert "unique_numbers" in data
        assert "reports_by_type" in data
        assert "top_reported_numbers" in data
        assert "blocklist_count" in data

        # Regular user should be forbidden
        user_response = await community_client.get(
            "/api/v1/community/stats",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert user_response.status_code == 403
