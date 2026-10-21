"""Concurrency and race condition tests to verify non-overselling under concurrent orders."""
import asyncio
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_concurrent_orders_prevent_overselling():
    """
    Launch 10 concurrent orders competing for 10 units of stock.
    Each order demands 3 units.
    Total demand = 30 units, available = 10 units.
    Exactly 3 orders can succeed (9 units), remaining 7 MUST fail with 422.
    Available stock must never become negative.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Setup product and warehouse with 10 units stock
        p = (await client.post("/api/v1/products", json={
            "sku": "PROD-RACE-001", "name": "Limited Edition GPU", "price": 999.0, "weight_kg": 2.5
        })).json()

        w = (await client.post("/api/v1/warehouses", json={
            "code": "WH-RACE-01", "name": "Race Test WH", "latitude": 37.77, "longitude": -122.41
        })).json()

        await client.post("/api/v1/inventory/adjustments", json={
            "warehouse_id": w["id"], "product_id": p["id"], "quantity_delta": 10
        })

        # 2. Prepare 10 concurrent client calls
        async def submit_order(idx: int):
            async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
                return await ac.post("/api/v1/orders", json={
                    "customer_id": f"CUST-RACE-{idx}",
                    "destination_lat": 37.78,
                    "destination_lon": -122.42,
                    "items": [{"product_id": p["id"], "requested_quantity": 3}]
                })

        tasks = [submit_order(i) for i in range(10)]
        responses = await asyncio.gather(*tasks)

        success_count = sum(1 for r in responses if r.status_code == 201)
        insufficient_count = sum(1 for r in responses if r.status_code == 422)

        # Assert exactly 3 succeeded and 7 rejected
        assert success_count == 3
        assert insufficient_count == 7

        # Verify final database inventory state
        inv_res = await client.get("/api/v1/inventory")
        match = [i for i in inv_res.json() if i["product_id"] == p["id"] and i["warehouse_id"] == w["id"]][0]

        assert match["quantity_on_hand"] == 10
        assert match["quantity_reserved"] == 9
        assert match["quantity_available"] == 1
        assert match["quantity_reserved"] <= match["quantity_on_hand"]
