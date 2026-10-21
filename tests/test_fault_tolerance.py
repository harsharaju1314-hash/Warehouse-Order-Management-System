"""Fault tolerance, retry mechanics, and warehouse outage failover tests."""
import pytest
from app.core.retry import with_retry, is_retryable_exception
from app.core.exceptions import (
    TransientServiceError,
    InsufficientInventoryError,
    WarehouseUnavailableError
)
from httpx import AsyncClient


def test_transient_error_classification():
    transient = TransientServiceError("Temporary network glitch")
    wh_unavail = WarehouseUnavailableError("WH-01")
    business_err = InsufficientInventoryError("P1", 10, 0)
    val_err = ValueError("Invalid input")

    assert is_retryable_exception(transient) is True
    assert is_retryable_exception(wh_unavail) is True
    assert is_retryable_exception(business_err) is False
    assert is_retryable_exception(val_err) is False


@pytest.mark.asyncio
async def test_retry_mechanism_recovers_after_transient_failure():
    attempts = 0

    @with_retry(max_retries=3, base_delay=0.01)
    async def flaky_operation():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise TransientServiceError("Transient timeout")
        return "SUCCESS"

    result = await flaky_operation()
    assert result == "SUCCESS"
    assert attempts == 3


@pytest.mark.asyncio
async def test_retry_exhaustion_raises_exception():
    attempts = 0

    @with_retry(max_retries=2, base_delay=0.01)
    async def permanently_broken():
        nonlocal attempts
        attempts += 1
        raise TransientServiceError("Never recovers")

    with pytest.raises(TransientServiceError):
        await permanently_broken()
    assert attempts == 3  # Initial + 2 retries


@pytest.mark.asyncio
async def test_warehouse_outage_failover_routing(client: AsyncClient):
    """
    Simulate a warehouse going OFFLINE.
    Verify that subsequent orders automatically route to the remaining active warehouse.
    """
    # Create product
    p = (await client.post("/api/v1/products", json={
        "sku": "PROD-FAILOVER-01", "name": "Failover Item", "price": 50.0, "weight_kg": 1.0
    })).json()

    # Create Primary and Secondary Warehouses
    wh_primary = (await client.post("/api/v1/warehouses", json={
        "code": "WH-PRIMARY", "name": "Primary Hub", "latitude": 37.77, "longitude": -122.41
    })).json()

    wh_backup = (await client.post("/api/v1/warehouses", json={
        "code": "WH-BACKUP-01", "name": "Backup Hub", "latitude": 37.80, "longitude": -122.40
    })).json()

    # Stock both warehouses with 20 units
    await client.post("/api/v1/inventory/adjustments", json={
        "warehouse_id": wh_primary["id"], "product_id": p["id"], "quantity_delta": 20
    })
    await client.post("/api/v1/inventory/adjustments", json={
        "warehouse_id": wh_backup["id"], "product_id": p["id"], "quantity_delta": 20
    })

    # Take primary warehouse OFFLINE (outage simulation)
    await client.patch(f"/api/v1/warehouses/{wh_primary['id']}", json={"status": "OFFLINE"})

    # Submit order
    res = await client.post("/api/v1/orders", json={
        "customer_id": "CUST-FAILOVER",
        "destination_lat": 37.77, "destination_lon": -122.41,
        "items": [{"product_id": p["id"], "requested_quantity": 5}]
    })

    assert res.status_code == 201
    order = res.json()
    assert order["status"] == "RESERVED"
    # Order must have routed to WH-BACKUP because primary is OFFLINE
    assert len(order["allocations"]) == 1
    assert order["allocations"][0]["warehouse_id"] == wh_backup["id"]

    # Restore primary warehouse to ACTIVE
    await client.patch(f"/api/v1/warehouses/{wh_primary['id']}", json={"status": "ACTIVE"})
