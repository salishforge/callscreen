"""Integration tests for persona API endpoints."""

import pytest


PERSONA_DATA = {
    "name": "Test Scam Waster",
    "description": "A test persona for wasting scam callers' time",
    "system_prompt": "You are a confused person. Never reveal you are an AI.",
    "voice_id": "test_voice",
    "speech_rate": 0.9,
    "engagement_rules": {
        "min_trust_score": 0.0,
        "max_trust_score": 0.2,
        "target_duration_seconds": 300,
        "max_duration_seconds": 600,
    },
}


@pytest.mark.integration
async def test_create_persona_admin(client, admin_user, admin_token):
    """Admins can create a custom persona."""
    response = await client.post(
        "/api/v1/personas",
        json=PERSONA_DATA,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Scam Waster"
    assert data["is_builtin"] is False
    assert data["is_active"] is True
    assert data["engagement_rules"]["max_duration_seconds"] == 600


@pytest.mark.integration
async def test_create_persona_forbidden_for_regular_user(client, regular_user, user_token):
    """Non-admin users cannot create personas."""
    response = await client.post(
        "/api/v1/personas",
        json=PERSONA_DATA,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403


@pytest.mark.integration
async def test_list_personas(client, admin_user, admin_token):
    """Admins can list all personas."""
    # Create one first
    await client.post(
        "/api/v1/personas",
        json=PERSONA_DATA,
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    response = await client.get(
        "/api/v1/personas",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


@pytest.mark.integration
async def test_get_persona_by_id(client, admin_user, admin_token):
    """Can fetch a persona by its ID."""
    create_resp = await client.post(
        "/api/v1/personas",
        json=PERSONA_DATA,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    persona_id = create_resp.json()["id"]

    response = await client.get(
        f"/api/v1/personas/{persona_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    assert response.json()["id"] == persona_id


@pytest.mark.integration
async def test_update_custom_persona(client, admin_user, admin_token):
    """Admins can update a custom (non-builtin) persona."""
    create_resp = await client.post(
        "/api/v1/personas",
        json=PERSONA_DATA,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    persona_id = create_resp.json()["id"]

    response = await client.put(
        f"/api/v1/personas/{persona_id}",
        json={"name": "Updated Name", "speech_rate": 1.1},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Name"
    assert response.json()["speech_rate"] == 1.1


@pytest.mark.integration
async def test_deactivate_custom_persona(client, admin_user, admin_token):
    """Admins can deactivate a custom persona."""
    create_resp = await client.post(
        "/api/v1/personas",
        json=PERSONA_DATA,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    persona_id = create_resp.json()["id"]

    response = await client.delete(
        f"/api/v1/personas/{persona_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 204

    # Verify it's now inactive
    get_resp = await client.get(
        f"/api/v1/personas/{persona_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert get_resp.json()["is_active"] is False


@pytest.mark.integration
async def test_seed_builtins(client, admin_user, admin_token):
    """Seeding built-ins creates all 4 persona records."""
    response = await client.post(
        "/api/v1/personas/seed-builtins",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 4
    names = {p["name"] for p in data}
    assert "Confused Grandparent" in names
    assert "The Philosopher" in names

    # Second seed should be idempotent (no duplicates)
    response2 = await client.post(
        "/api/v1/personas/seed-builtins",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response2.status_code == 200
    assert len(response2.json()) == 0  # all already exist
