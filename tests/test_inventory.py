"""Tests for inventory adjustments, balance constraints, and audit movements."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_inventory_adjustment_increases_stock(client: AsyncClient):
    # Setup product and warehouse
    p_res = await client.post("/api/v1/products", json={
        "sku": "PROD-INV-001", "name": "USB-C Cable", "price": 12.50, "weight_kg": 0.1
    })
    prod_id = p_res.json()["id"]

    w_res = await client.post("/api/v1/warehouses", json={
        "code": "WH-INV-01", "name": "Inventory Test Hub", "latitude": 34.0522, "longitude": -118.2437
    })
    wh_id = w_res.json()["id"]

    # Adjust stock +100
    adj_res = await client.post("/api/v1/inventory/adjustments", json={
        "warehouse_id": wh_id,
        "product_id": prod_id,
        "quantity_delta": 100,
        "reason": "Initial stock shipment"
    })
    assert adj_res.status_code == 200
    data = adj_res.json()
    assert data["quantity_on_hand"] == 100
    assert data["quantity_reserved"] == 0
    assert data["quantity_available"] == 100


@pytest.mark.asyncio
async def test_inventory_audit_movement_recorded(client: AsyncClient):
    # Fetch movements
    res = await client.get("/api/v1/inventory/movements")
    assert res.status_code == 200
    movements = res.json()
    assert len(movements) >= 1
    latest = movements[0]
    assert latest["change_type"] == "ADJUSTMENT"
    assert latest["quantity_delta"] == 100
    assert latest["balance_on_hand_after"] == 100


@pytest.mark.asyncio
async def test_inventory_overview_matrix(client: AsyncClient):
    res = await client.get("/api/v1/inventory")
    assert res.status_code == 200
    items = res.json()
    assert len(items) >= 1
    assert "warehouse_code" in items[0]
    assert "product_sku" in items[0]
    assert "quantity_available" in items[0]


@pytest.mark.asyncio
async def test_negative_stock_prevention(client: AsyncClient):
    # Get an existing product and warehouse
    wh = (await client.get("/api/v1/warehouses")).json()[0]
    prod = (await client.get("/api/v1/products")).json()["items"][0]

    # Attempt to reduce by an absurd amount (-99999)
    res = await client.post("/api/v1/inventory/adjustments", json={
        "warehouse_id": wh["id"],
        "product_id": prod["id"],
        "quantity_delta": -99999,
        "reason": "Illegal deduction"
    })
    assert res.status_code == 422
    assert "Insufficient inventory" in res.json()["error"]
