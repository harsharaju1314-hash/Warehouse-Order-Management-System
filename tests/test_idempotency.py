"""Tests for request idempotency and duplicate submission prevention."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_idempotency_prevents_duplicate_reservations(client: AsyncClient):
    # Setup product and warehouse with 50 units
    p = (await client.post("/api/v1/products", json={
        "sku": "PROD-IDEMP-01", "name": "Tablet", "price": 299.0, "weight_kg": 0.6
    })).json()

    w = (await client.post("/api/v1/warehouses", json={
        "code": "WH-IDEMP-01", "name": "Idempotency WH", "latitude": 37.77, "longitude": -122.41
    })).json()

    await client.post("/api/v1/inventory/adjustments", json={
        "warehouse_id": w["id"], "product_id": p["id"], "quantity_delta": 50
    })

    idempotency_key = "idemp_test_key_unique_12345"

    order_payload = {
        "customer_id": "CUST-IDEMP",
        "destination_lat": 37.78,
        "destination_lon": -122.42,
        "items": [{"product_id": p["id"], "requested_quantity": 5}]
    }

    # First submission
    res1 = await client.post(
        "/api/v1/orders",
        json=order_payload,
        headers={"X-Idempotency-Key": idempotency_key}
    )
    assert res1.status_code == 201
    order1 = res1.json()
    order1_id = order1["id"]

    # Second submission with IDENTICAL idempotency key
    res2 = await client.post(
        "/api/v1/orders",
        json=order_payload,
        headers={"X-Idempotency-Key": idempotency_key}
    )
    assert res2.status_code in (200, 201)
    order2 = res2.json()
    assert order2["id"] == order1_id  # Returns the exact same order

    # Verify inventory reserved count is EXACTLY 5 (NOT 10!)
    inv_res = await client.get("/api/v1/inventory")
    match = [i for i in inv_res.json() if i["product_id"] == p["id"] and i["warehouse_id"] == w["id"]][0]
    assert match["quantity_reserved"] == 5
    assert match["quantity_available"] == 45
