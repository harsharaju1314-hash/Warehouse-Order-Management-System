"""Unit and integration tests for routing algorithms and OR-Tools LP optimization."""
import pytest
from app.routing.base import WarehouseCandidate, OrderDemand
from app.routing.greedy_nearest import GreedyNearestRoutingStrategy
from app.routing.or_tools_lp import ORToolsLPRoutingStrategy
from httpx import AsyncClient


def test_or_tools_lp_single_warehouse_optimal():
    """Verify OR-Tools chooses the lowest cost warehouse."""
    router = ORToolsLPRoutingStrategy()

    candidates = [
        WarehouseCandidate(
            warehouse_id="WH-CHEAP",
            warehouse_code="WH-CHEAP",
            latitude=37.77, longitude=-122.41,
            distance_km=10.0,
            shipping_base_cost=3.0, shipping_cost_per_km=0.01, processing_cost_per_unit=1.0,
            capacity_remaining=500,
            stock_by_product={"PROD-1": 100}
        ),
        WarehouseCandidate(
            warehouse_id="WH-EXPENSIVE",
            warehouse_code="WH-EXPENSIVE",
            latitude=40.71, longitude=-74.00,
            distance_km=4000.0,
            shipping_base_cost=15.0, shipping_cost_per_km=0.08, processing_cost_per_unit=3.0,
            capacity_remaining=500,
            stock_by_product={"PROD-1": 100}
        ),
    ]

    demands = [OrderDemand(product_id="PROD-1", requested_quantity=10, unit_price=20.0, weight_kg=1.0)]

    result = router.route_order(
        dest_lat=37.78, dest_lon=-122.42, demands=demands, candidates=candidates, max_splits=2
    )

    assert result.is_feasible is True
    assert len(result.allocations) == 1
    assert result.allocations[0].warehouse_id == "WH-CHEAP"
    assert result.allocations[0].quantity == 10


def test_split_fulfillment_across_multiple_warehouses():
    """Verify order splits when a single warehouse has insufficient inventory."""
    router = ORToolsLPRoutingStrategy()

    candidates = [
        WarehouseCandidate(
            warehouse_id="WH-1", warehouse_code="WH-1",
            latitude=37.77, longitude=-122.41, distance_km=20.0,
            shipping_base_cost=5.0, shipping_cost_per_km=0.02, processing_cost_per_unit=1.0,
            capacity_remaining=100, stock_by_product={"PROD-1": 6}
        ),
        WarehouseCandidate(
            warehouse_id="WH-2", warehouse_code="WH-2",
            latitude=37.78, longitude=-122.40, distance_km=25.0,
            shipping_base_cost=5.0, shipping_cost_per_km=0.02, processing_cost_per_unit=1.0,
            capacity_remaining=100, stock_by_product={"PROD-1": 8}
        ),
    ]

    # Demand is 10 units (WH-1 has only 6, so must split to WH-2)
    demands = [OrderDemand(product_id="PROD-1", requested_quantity=10, unit_price=10.0, weight_kg=1.0)]

    result = router.route_order(
        dest_lat=37.77, dest_lon=-122.41, demands=demands, candidates=candidates, max_splits=2
    )

    assert result.is_feasible is True
    assert len(result.allocations) == 2
    total_qty = sum(a.quantity for a in result.allocations)
    assert total_qty == 10
    assert result.split_count == 2


def test_capacity_limit_constraint_enforcement():
    """Verify routing respects warehouse daily capacity limit even if stock exists."""
    router = ORToolsLPRoutingStrategy()

    candidates = [
        WarehouseCandidate(
            warehouse_id="WH-LOW-CAP", warehouse_code="WH-LOW-CAP",
            latitude=37.77, longitude=-122.41, distance_km=5.0,
            shipping_base_cost=2.0, shipping_cost_per_km=0.01, processing_cost_per_unit=1.0,
            capacity_remaining=3,  # Only 3 units capacity left!
            stock_by_product={"PROD-1": 100}
        ),
        WarehouseCandidate(
            warehouse_id="WH-BACKUP", warehouse_code="WH-BACKUP",
            latitude=37.78, longitude=-122.40, distance_km=20.0,
            shipping_base_cost=5.0, shipping_cost_per_km=0.02, processing_cost_per_unit=1.5,
            capacity_remaining=100,
            stock_by_product={"PROD-1": 100}
        ),
    ]

    demands = [OrderDemand(product_id="PROD-1", requested_quantity=10, unit_price=15.0, weight_kg=1.0)]

    result = router.route_order(
        dest_lat=37.77, dest_lon=-122.41, demands=demands, candidates=candidates, max_splits=2
    )

    assert result.is_feasible is True
    wh_low_cap_alloc = [a for a in result.allocations if a.warehouse_id == "WH-LOW-CAP"]
    assert len(wh_low_cap_alloc) == 1
    assert wh_low_cap_alloc[0].quantity == 3  # Capped at remaining capacity 3


def test_infeasible_when_total_capacity_exceeded():
    router = ORToolsLPRoutingStrategy()

    candidates = [
        WarehouseCandidate(
            warehouse_id="WH-TINY", warehouse_code="WH-TINY",
            latitude=37.77, longitude=-122.41, distance_km=10.0,
            shipping_base_cost=5.0, shipping_cost_per_km=0.02, processing_cost_per_unit=1.0,
            capacity_remaining=2, stock_by_product={"PROD-1": 50}
        )
    ]
    demands = [OrderDemand(product_id="PROD-1", requested_quantity=10, unit_price=10.0, weight_kg=1.0)]

    result = router.route_order(
        dest_lat=37.77, dest_lon=-122.41, demands=demands, candidates=candidates, max_splits=2
    )
    assert result.is_feasible is False
    assert "infeasible" in result.failure_reason.lower()


@pytest.mark.asyncio
async def test_end_to_end_split_fulfillment_via_api(client: AsyncClient):
    # Setup 1 product and 2 warehouses
    p = (await client.post("/api/v1/products", json={
        "sku": "PROD-SPLIT-API", "name": "4K TV", "price": 400.0, "weight_kg": 15.0
    })).json()

    w1 = (await client.post("/api/v1/warehouses", json={
        "code": "WH-SPLIT-A", "name": "Wh A", "latitude": 32.0, "longitude": -96.0
    })).json()

    w2 = (await client.post("/api/v1/warehouses", json={
        "code": "WH-SPLIT-B", "name": "Wh B", "latitude": 33.0, "longitude": -97.0
    })).json()

    # WH-A has 4 units, WH-B has 6 units
    await client.post("/api/v1/inventory/adjustments", json={
        "warehouse_id": w1["id"], "product_id": p["id"], "quantity_delta": 4
    })
    await client.post("/api/v1/inventory/adjustments", json={
        "warehouse_id": w2["id"], "product_id": p["id"], "quantity_delta": 6
    })

    # Order 7 units (requires split)
    res = await client.post("/api/v1/orders", json={
        "customer_id": "CUST-SPLIT-API",
        "destination_lat": 32.5, "destination_lon": -96.5,
        "items": [{"product_id": p["id"], "requested_quantity": 7}]
    })
    assert res.status_code == 201
    ord_data = res.json()
    assert ord_data["status"] == "RESERVED"
    assert len(ord_data["allocations"]) == 2
    allocated_sum = sum(a["allocated_quantity"] for a in ord_data["allocations"])
    assert allocated_sum == 7


def test_or_tools_vs_greedy_cost_comparison():
    """Verify OR-Tools achieves equal or lower cost than naive greedy."""
    greedy = GreedyNearestRoutingStrategy()
    ortools = ORToolsLPRoutingStrategy()

    # Setup scenario where nearest warehouse has higher shipping cost slope or unit handling
    candidates = [
        WarehouseCandidate(
            warehouse_id="WH-CLOSE-EXPENSIVE", warehouse_code="WH-CLOSE-EXPENSIVE",
            latitude=37.77, longitude=-122.41, distance_km=10.0,
            shipping_base_cost=10.0, shipping_cost_per_km=0.10, processing_cost_per_unit=5.0,
            capacity_remaining=100, stock_by_product={"P1": 10}
        ),
        WarehouseCandidate(
            warehouse_id="WH-FAR-CHEAP", warehouse_code="WH-FAR-CHEAP",
            latitude=37.78, longitude=-122.40, distance_km=15.0,
            shipping_base_cost=2.0, shipping_cost_per_km=0.01, processing_cost_per_unit=1.0,
            capacity_remaining=100, stock_by_product={"P1": 10}
        ),
    ]

    demands = [OrderDemand(product_id="P1", requested_quantity=10, unit_price=20.0, weight_kg=1.0)]

    res_greedy = greedy.route_order(37.77, -122.41, demands, candidates)
    res_opt = ortools.route_order(37.77, -122.41, demands, candidates)

    assert res_greedy.is_feasible is True
    assert res_opt.is_feasible is True
    # OR-Tools should achieve lower or equal cost than greedy
    assert res_opt.total_cost <= res_greedy.total_cost
