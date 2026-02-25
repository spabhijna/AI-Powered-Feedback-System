"""
Integration tests for FastAPI routes.
Uses an in-memory SQLite database and mocks ML inference.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch


# ---------------------------------------------------------------------------
# App fixture – patch heavy ML calls before the app module is imported
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def mock_ml_models():
    """Prevent actual model loading during tests."""
    with patch("app.services.processing.process_feedback", return_value=("negative", "technical", "high", "Test summary")):
        yield


@pytest_asyncio.fixture
async def client():
    """Async test client with isolated in-memory DB."""
    from tortoise import Tortoise

    await Tortoise.init(
        db_url="sqlite://:memory:",
        modules={"models": ["app.models"]},
    )
    await Tortoise.generate_schemas()

    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    await Tortoise.close_connections()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_create_feedback_default_source(client):
    with patch("app.api.routes.process_feedback", return_value=("negative", "technical", "high", "Summary")):
        resp = await client.post("/feedback", json={"text": "App crashes on login"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["sentiment"] == "negative"
    assert data["category"] == "technical"
    assert data["priority"] == "high"
    assert data["source"] == "web"


@pytest.mark.asyncio
async def test_create_feedback_custom_source(client):
    with patch("app.api.routes.process_feedback", return_value=("positive", "general", "low", None)):
        resp = await client.post("/feedback", json={"text": "Great app!", "source": "api"})
    assert resp.status_code == 200
    assert resp.json()["source"] == "api"


@pytest.mark.asyncio
async def test_get_feedback_empty(client):
    resp = await client.get("/feedback")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_analytics_empty(client):
    resp = await client.get("/analytics")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_feedback" in data
    assert "sentiment_distribution" in data
    assert "category_distribution" in data
    assert "priority_distribution" in data


@pytest.mark.asyncio
async def test_trends(client):
    resp = await client.get("/trends")
    assert resp.status_code == 200
    data = resp.json()
    assert "period" in data
    assert "alerts" in data


@pytest.mark.asyncio
async def test_feedback_filter_by_sentiment(client):
    with patch("app.api.routes.process_feedback", return_value=("positive", "general", "low", None)):
        await client.post("/feedback", json={"text": "Excellent service"})

    resp = await client.get("/feedback?sentiment=positive")
    assert resp.status_code == 200
    items = resp.json()
    assert all(i["sentiment"] == "positive" for i in items)
