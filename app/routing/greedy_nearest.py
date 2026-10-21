"""Baseline Greedy (Nearest-Eligible-Warehouse) Routing Strategy."""
from typing import List, Dict
from app.routing.base import (
    BaseRoutingStrategy,
    WarehouseCandidate,
    OrderDemand,
    RoutingResult,
    AllocationUnit
)


class GreedyNearestRoutingStrategy(BaseRoutingStrategy):
    """
    Greedy heuristic:
    1. Sorts warehouses by distance / base cost to destination.
    2. Sequentially allocates from the nearest warehouse with available stock and capacity.
    3. Splits across subsequent warehouses if stock is insufficient.
    """
    def route_order(
        self,
        dest_lat: float,
        dest_lon: float,
        demands: List[OrderDemand],
        candidates: List[WarehouseCandidate],
        max_splits: int = 3
    ) -> RoutingResult:
        if not candidates:
            return RoutingResult(
                strategy_name="NEAREST_GREEDY",
                is_feasible=False,
                allocations=[],
                total_cost=0.0,
                failure_reason="No eligible active warehouses available."
            )

        # Sort candidates by distance to destination
        sorted_candidates = sorted(candidates, key=lambda c: c.distance_km)

        # Track mutable state during allocation pass
        remaining_stock: Dict[str, Dict[str, int]] = {
            c.warehouse_id: dict(c.stock_by_product) for c in candidates
        }
        remaining_capacity: Dict[str, int] = {
            c.warehouse_id: c.capacity_remaining for c in candidates
        }
        used_warehouses = set()
        allocations: List[AllocationUnit] = []
        total_cost = 0.0

        for demand in demands:
            needed = demand.requested_quantity

            for cand in sorted_candidates:
                if needed <= 0:
                    break

                wh_id = cand.warehouse_id
                wh_stock = remaining_stock[wh_id].get(demand.product_id, 0)
                wh_cap = remaining_capacity[wh_id]

                if wh_stock <= 0 or wh_cap <= 0:
                    continue

                # Check max splits constraint if opening a new warehouse
                if wh_id not in used_warehouses and len(used_warehouses) >= max_splits:
                    continue

                alloc_qty = min(needed, wh_stock, wh_cap)
                if alloc_qty > 0:
                    unit_shipping = cand.shipping_base_cost + (cand.distance_km * cand.shipping_cost_per_km)
                    shipping_cost = round(unit_shipping * alloc_qty, 2)
                    handling_cost = round(cand.processing_cost_per_unit * alloc_qty, 2)

                    allocations.append(AllocationUnit(
                        warehouse_id=wh_id,
                        product_id=demand.product_id,
                        quantity=alloc_qty,
                        shipping_cost=shipping_cost,
                        handling_cost=handling_cost
                    ))

                    remaining_stock[wh_id][demand.product_id] -= alloc_qty
                    remaining_capacity[wh_id] -= alloc_qty
                    used_warehouses.add(wh_id)
                    total_cost += (shipping_cost + handling_cost)
                    needed -= alloc_qty

            if needed > 0:
                return RoutingResult(
                    strategy_name="NEAREST_GREEDY",
                    is_feasible=False,
                    allocations=[],
                    total_cost=0.0,
                    failure_reason=f"Insufficient inventory across warehouses for product {demand.product_id}. Unmet quantity: {needed}"
                )

        return RoutingResult(
            strategy_name="NEAREST_GREEDY",
            is_feasible=True,
            allocations=allocations,
            total_cost=round(total_cost, 2),
            split_count=len(used_warehouses)
        )
