"""Tests for health check endpoints."""

import pytest


@pytest.mark.integration
async def test_liveness(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.integration
async def test_readiness(client):
    response = await client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "version" in data
    assert data["version"] == "0.1.0"
