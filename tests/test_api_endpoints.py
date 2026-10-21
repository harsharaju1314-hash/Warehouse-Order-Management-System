"""Tests for API status codes, error models, and OpenAPI documentation."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_openapi_schema_endpoint(client: AsyncClient):
    res = await client.get("/openapi.json")
    assert res.status_code == 200
    schema = res.json()
    assert "paths" in schema
    assert "/api/v1/orders" in schema["paths"]
    assert "/api/v1/inventory" in schema["paths"]


@pytest.mark.asyncio
async def test_not_found_structured_error(client: AsyncClient):
    res = await client.get("/api/v1/products/non-existent-uuid-999")
    assert res.status_code == 404
    data = res.json()
    assert "error" in data
    assert data["code"] == "RESOURCE_NOT_FOUND"
    assert "details" in data


@pytest.mark.asyncio
async def test_invalid_request_body_validation(client: AsyncClient):
    # Missing required 'sku' and negative price
    res = await client.post("/api/v1/products", json={"name": "Bad Product", "price": -5.0})
    assert res.status_code == 422  # Pydantic validation error


@pytest.mark.asyncio
async def test_system_health_endpoint(client: AsyncClient):
    res = await client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "database_connected" in data
    assert "redis_connected" in data
