"""Tests for contact management endpoints."""

import pytest


@pytest.mark.integration
async def test_create_whitelist_contact(client, admin_user, admin_token):
    response = await client.post(
        "/api/v1/contacts",
        json={
            "phone_number": "+15551234567",
            "name": "Dr. Smith",
            "contact_type": "whitelist",
            "category": "medical",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Dr. Smith"
    assert data["contact_type"] == "whitelist"


@pytest.mark.integration
async def test_list_contacts(client, admin_user, admin_token):
    # Create a contact first
    await client.post(
        "/api/v1/contacts",
        json={
            "phone_number": "+15559998888",
            "name": "Test Contact",
            "contact_type": "blocklist",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    response = await client.get(
        "/api/v1/contacts",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


@pytest.mark.integration
async def test_duplicate_contact_rejected(client, admin_user, admin_token):
    contact_data = {
        "phone_number": "+15557776666",
        "name": "Duplicate Test",
        "contact_type": "whitelist",
    }
    await client.post(
        "/api/v1/contacts",
        json=contact_data,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    response = await client.post(
        "/api/v1/contacts",
        json=contact_data,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 400
