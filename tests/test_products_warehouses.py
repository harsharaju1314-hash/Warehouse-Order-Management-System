"""Tests for Products and Warehouses management."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_product_success(client: AsyncClient):
    payload = {
        "sku": "PROD-TEST-001",
        "name": "Mechanical Keyboard",
        "description": "RGB Backlit Gaming Keyboard",
        "price": 89.99,
        "weight_kg": 1.2
    }
    res = await client.post("/api/v1/products", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["sku"] == "PROD-TEST-001"
    assert data["price"] == 89.99
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_duplicate_sku_fails(client: AsyncClient):
    payload = {
        "sku": "PROD-TEST-001",
        "name": "Duplicate Keyboard",
        "price": 99.99,
        "weight_kg": 1.0
    }
    res = await client.post("/api/v1/products", json=payload)
    assert res.status_code == 400
    assert "already exists" in res.json()["error"]


@pytest.mark.asyncio
async def test_update_product_and_cache_invalidation(client: AsyncClient):
    # Create product
    create_res = await client.post("/api/v1/products", json={
        "sku": "PROD-TEST-002",
        "name": "Wireless Mouse",
        "price": 29.99,
        "weight_kg": 0.25
    })
    prod_id = create_res.json()["id"]

    # First get (caches product)
    get_res1 = await client.get(f"/api/v1/products/{prod_id}")
    assert get_res1.status_code == 200

    # Update product
    update_res = await client.patch(f"/api/v1/products/{prod_id}", json={
        "price": 34.99,
        "name": "Ergonomic Wireless Mouse"
    })
    assert update_res.status_code == 200
    assert update_res.json()["price"] == 34.99

    # Second get should reflect updated data
    get_res2 = await client.get(f"/api/v1/products/{prod_id}")
    assert get_res2.status_code == 200
    assert get_res2.json()["price"] == 34.99


@pytest.mark.asyncio
async def test_create_warehouse_success(client: AsyncClient):
    payload = {
        "code": "WH-TEST-EAST",
        "name": "East Regional Warehouse",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "capacity_limit": 500,
        "shipping_base_cost": 6.00,
        "shipping_cost_per_km": 0.04,
        "processing_cost_per_unit": 1.25
    }
    res = await client.post("/api/v1/warehouses", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["code"] == "WH-TEST-EAST"
    assert data["status"] == "ACTIVE"
    assert data["capacity_limit"] == 500


@pytest.mark.asyncio
async def test_warehouse_health_evaluation(client: AsyncClient):
    res = await client.get("/api/v1/health/warehouses")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1
    wh = data[0]
    assert "is_healthy" in wh
    assert "available_capacity" in wh
    assert wh["is_healthy"] is True


@pytest.mark.asyncio
async def test_toggle_warehouse_offline(client: AsyncClient):
    # Fetch list
    res = await client.get("/api/v1/warehouses")
    wh_id = res.json()[0]["id"]

    # Set OFFLINE
    patch_res = await client.patch(f"/api/v1/warehouses/{wh_id}", json={"status": "OFFLINE"})
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "OFFLINE"

    # Reset back to ACTIVE
    reset_res = await client.patch(f"/api/v1/warehouses/{wh_id}", json={"status": "ACTIVE"})
    assert reset_res.status_code == 200
    assert reset_res.json()["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_invalid_warehouse_coordinates(client: AsyncClient):
    # Latitude > 90 must fail validation
    payload = {
        "code": "WH-BAD-COORDS",
        "name": "Invalid WH",
        "latitude": 195.0,  # Invalid
        "longitude": 45.0,
    }
    res = await client.post("/api/v1/warehouses", json=payload)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_exact_cache_hit_on_product_retrieval(client: AsyncClient):
    from app.core.redis import redis_client
    p = (await client.post("/api/v1/products", json={
        "sku": "PROD-CACHE-TEST", "name": "Cache Test Item", "price": 19.99, "weight_kg": 0.5
    })).json()

    # Read product to seed cache
    await client.get(f"/api/v1/products/{p['id']}")
    cached = await redis_client.get_json(f"product:{p['id']}")
    assert cached is not None
    assert cached["sku"] == "PROD-CACHE-TEST"
