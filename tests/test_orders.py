"""Tests for order creation, reservation, fulfillment, and cancellation."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_order_creation_and_reservation(client: AsyncClient):
    # Create product and warehouse with inventory
    p_res = await client.post("/api/v1/products", json={
        "sku": "PROD-ORD-001", "name": "Monitor Stand", "price": 45.00, "weight_kg": 2.0
    })
    prod_id = p_res.json()["id"]

    w_res = await client.post("/api/v1/warehouses", json={
        "code": "WH-ORD-01", "name": "Order Test WH", "latitude": 37.7749, "longitude": -122.4194
    })
    wh_id = w_res.json()["id"]

    await client.post("/api/v1/inventory/adjustments", json={
        "warehouse_id": wh_id, "product_id": prod_id, "quantity_delta": 50
    })

    # Create Order for 10 units
    order_res = await client.post("/api/v1/orders", json={
        "customer_id": "CUST-1001",
        "destination_lat": 37.7833,
        "destination_lon": -122.4167,
        "items": [{"product_id": prod_id, "requested_quantity": 10}]
    })
    assert order_res.status_code == 201
    order = order_res.json()
    assert order["status"] == "RESERVED"
    assert order["total_item_price"] == 450.00
    assert order["total_fulfillment_cost"] > 0
    assert len(order["allocations"]) == 1
    assert order["allocations"][0]["allocated_quantity"] == 10


@pytest.mark.asyncio
async def test_order_fulfillment_deducts_stock(client: AsyncClient):
    # Create product, warehouse, stock 20
    p = (await client.post("/api/v1/products", json={
        "sku": "PROD-FULFILL-01", "name": "Webcam", "price": 60.00, "weight_kg": 0.3
    })).json()
    w = (await client.post("/api/v1/warehouses", json={
        "code": "WH-FULFILL-01", "name": "Fulfillment Hub", "latitude": 30.0, "longitude": -95.0
    })).json()

    await client.post("/api/v1/inventory/adjustments", json={
        "warehouse_id": w["id"], "product_id": p["id"], "quantity_delta": 20
    })

    # Order 5 units
    ord = (await client.post("/api/v1/orders", json={
        "customer_id": "CUST-SHIP",
        "destination_lat": 30.1, "destination_lon": -95.1,
        "items": [{"product_id": p["id"], "requested_quantity": 5}]
    })).json()
    assert ord["status"] == "RESERVED"

    # Fulfill order
    ship_res = await client.post(f"/api/v1/orders/{ord['id']}/fulfill")
    assert ship_res.status_code == 200
    assert ship_res.json()["status"] == "FULFILLED"

    # Verify inventory is now 15 on-hand and 0 reserved
    inv_res = await client.get("/api/v1/inventory")
    match = [i for i in inv_res.json() if i["product_id"] == p["id"] and i["warehouse_id"] == w["id"]][0]
    assert match["quantity_on_hand"] == 15
    assert match["quantity_reserved"] == 0


@pytest.mark.asyncio
async def test_order_cancellation_releases_reservation(client: AsyncClient):
    # Create product, warehouse, stock 30
    p = (await client.post("/api/v1/products", json={
        "sku": "PROD-CANCEL-01", "name": "Desk Lamp", "price": 25.00, "weight_kg": 1.5
    })).json()
    w = (await client.post("/api/v1/warehouses", json={
        "code": "WH-CANCEL-01", "name": "Cancel Hub", "latitude": 41.8781, "longitude": -87.6298
    })).json()

    await client.post("/api/v1/inventory/adjustments", json={
        "warehouse_id": w["id"], "product_id": p["id"], "quantity_delta": 30
    })

    # Order 10 units
    ord = (await client.post("/api/v1/orders", json={
        "customer_id": "CUST-CANCEL",
        "destination_lat": 41.9, "destination_lon": -87.7,
        "items": [{"product_id": p["id"], "requested_quantity": 10}]
    })).json()
    assert ord["status"] == "RESERVED"

    # Check inventory reservation is 10
    inv_res1 = await client.get("/api/v1/inventory")
    match1 = [i for i in inv_res1.json() if i["product_id"] == p["id"] and i["warehouse_id"] == w["id"]][0]
    assert match1["quantity_reserved"] == 10
    assert match1["quantity_available"] == 20

    # Cancel order
    cancel_res = await client.post(f"/api/v1/orders/{ord['id']}/cancel")
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "CANCELLED"

    # Check inventory reservation returned to 0, available back to 30
    inv_res2 = await client.get("/api/v1/inventory")
    match2 = [i for i in inv_res2.json() if i["product_id"] == p["id"] and i["warehouse_id"] == w["id"]][0]
    assert match2["quantity_reserved"] == 0
    assert match2["quantity_available"] == 30


@pytest.mark.asyncio
async def test_cannot_fulfill_cancelled_order(client: AsyncClient):
    # Create order and immediately cancel
    p = (await client.get("/api/v1/products")).json()["items"][0]
    w = (await client.get("/api/v1/warehouses")).json()[0]
    await client.post("/api/v1/inventory/adjustments", json={
        "warehouse_id": w["id"], "product_id": p["id"], "quantity_delta": 10
    })

    ord = (await client.post("/api/v1/orders", json={
        "customer_id": "CUST-INV-STATE",
        "destination_lat": 35.0, "destination_lon": -100.0,
        "items": [{"product_id": p["id"], "requested_quantity": 2}]
    })).json()

    await client.post(f"/api/v1/orders/{ord['id']}/cancel")

    # Attempt to fulfill cancelled order
    res = await client.post(f"/api/v1/orders/{ord['id']}/fulfill")
    assert res.status_code == 409
    assert "cannot perform 'FULFILL'" in res.json()["error"]


@pytest.mark.asyncio
async def test_insufficient_stock_fails_order(client: AsyncClient):
    p = (await client.post("/api/v1/products", json={
        "sku": "PROD-OUT-STOCK", "name": "Rare Gem", "price": 500.0, "weight_kg": 0.5
    })).json()

    # Request order for 10 units when 0 stock exists
    res = await client.post("/api/v1/orders", json={
        "customer_id": "CUST-OVERSELL",
        "destination_lat": 35.0, "destination_lon": -100.0,
        "items": [{"product_id": p["id"], "requested_quantity": 10}]
    })
    assert res.status_code == 422
    assert "Insufficient inventory" in res.json()["error"]


@pytest.mark.asyncio
async def test_order_list_pagination_and_status_filter(client: AsyncClient):
    res = await client.get("/api/v1/orders?page=1&size=5")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert "pages" in data
    assert data["page"] == 1
    assert data["size"] == 5


@pytest.mark.asyncio
async def test_zero_quantity_order_rejected(client: AsyncClient):
    p = (await client.get("/api/v1/products")).json()["items"][0]
    res = await client.post("/api/v1/orders", json={
        "customer_id": "CUST-ZERO",
        "destination_lat": 35.0, "destination_lon": -100.0,
        "items": [{"product_id": p["id"], "requested_quantity": 0}]  # Invalid: gt=0
    })
    assert res.status_code == 422

