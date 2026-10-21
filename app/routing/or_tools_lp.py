"""Google OR-Tools Mixed-Integer Linear Programming (MIP) Optimizer for Warehouse Routing."""
from typing import List, Dict
from ortools.linear_solver import pywraplp
from app.routing.base import (
    BaseRoutingStrategy,
    WarehouseCandidate,
    OrderDemand,
    RoutingResult,
    AllocationUnit
)
from app.core.logging import logger


class ORToolsLPRoutingStrategy(BaseRoutingStrategy):
    """
    Mixed-Integer Programming (MIP) formulation using Google OR-Tools SCIP solver.

    Minimizes: Total Fulfillment Cost (Shipping Distance + Processing Cost + Fixed Dispatch Cost)
    Subject to:
      1. Demand exact satisfaction per product.
      2. Available inventory upper bounds per warehouse & product.
      3. Warehouse daily throughput capacity limits.
      4. Linking constraints between unit allocations and warehouse activation.
      5. Maximum allowed warehouse splits per order.
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
                strategy_name="OR_TOOLS_LP",
                is_feasible=False,
                allocations=[],
                total_cost=0.0,
                failure_reason="No eligible active warehouses available."
            )

        # Total demand check across all candidates
        for demand in demands:
            total_stock_p = sum(c.stock_by_product.get(demand.product_id, 0) for c in candidates)
            if total_stock_p < demand.requested_quantity:
                return RoutingResult(
                    strategy_name="OR_TOOLS_LP",
                    is_feasible=False,
                    allocations=[],
                    total_cost=0.0,
                    failure_reason=(
                        f"Insufficient inventory across all active warehouses for product {demand.product_id}. "
                        f"Requested: {demand.requested_quantity}, Total Available: {total_stock_p}"
                    )
                )

        # Create SCIP solver instance (or CBC fallback)
        solver = pywraplp.Solver.CreateSolver("SCIP")
        if not solver:
            solver = pywraplp.Solver.CreateSolver("CBC")
        if not solver:
            # Fallback to GLOP for continuous relaxation if MIP solvers are unavailable
            solver = pywraplp.Solver.CreateSolver("GLOP")

        if not solver:
            raise RuntimeError("Unable to initialize OR-Tools linear solver (SCIP/CBC/GLOP).")

        total_units_demanded = sum(d.requested_quantity for d in demands)

        # Variables:
        # x[w_idx, p_idx]: Integer units of product p allocated from warehouse w
        x: Dict[tuple, pywraplp.Variable] = {}
        # y[w_idx]: Binary variable, 1 if warehouse w is used, 0 otherwise
        y: Dict[int, pywraplp.Variable] = {}

        for w_idx, cand in enumerate(candidates):
            y[w_idx] = solver.BoolVar(f"y_{w_idx}")
            for p_idx, demand in enumerate(demands):
                stock = cand.stock_by_product.get(demand.product_id, 0)
                upper_bound = min(demand.requested_quantity, stock)
                x[(w_idx, p_idx)] = solver.IntVar(0, upper_bound, f"x_{w_idx}_{p_idx}")

        # Constraint 1: Demand satisfaction for each product
        for p_idx, demand in enumerate(demands):
            solver.Add(
                solver.Sum(x[(w_idx, p_idx)] for w_idx in range(len(candidates))) == demand.requested_quantity
            )

        # Constraint 2: Warehouse capacity limit
        for w_idx, cand in enumerate(candidates):
            solver.Add(
                solver.Sum(x[(w_idx, p_idx)] for p_idx in range(len(demands))) <= cand.capacity_remaining
            )

        # Constraint 3: Linking constraint (x <= M * y) and split limit
        for w_idx, cand in enumerate(candidates):
            solver.Add(
                solver.Sum(x[(w_idx, p_idx)] for p_idx in range(len(demands))) <= total_units_demanded * y[w_idx]
            )

        # Constraint 4: Maximum split warehouses allowed
        solver.Add(
            solver.Sum(y[w_idx] for w_idx in range(len(candidates))) <= max_splits
        )

        # Objective function: Minimize total shipping + processing costs
        objective = solver.Objective()
        for w_idx, cand in enumerate(candidates):
            # Unit shipping cost = base_cost + (distance * per_km_cost)
            unit_shipping = cand.shipping_base_cost + (cand.distance_km * cand.shipping_cost_per_km)
            unit_handling = cand.processing_cost_per_unit
            total_unit_cost = unit_shipping + unit_handling

            for p_idx, demand in enumerate(demands):
                objective.SetCoefficient(x[(w_idx, p_idx)], float(total_unit_cost))

            # Small fixed dispatch cost per active warehouse to favor consolidation
            objective.SetCoefficient(y[w_idx], 2.0)

        objective.SetMinimization()

        status = solver.Solve()

        if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
            return RoutingResult(
                strategy_name="OR_TOOLS_LP",
                is_feasible=False,
                allocations=[],
                total_cost=0.0,
                failure_reason="OR-Tools solver found problem infeasible under current stock, capacity, or split constraints."
            )

        # Extract solution
        allocations: List[AllocationUnit] = []
        total_cost = 0.0
        used_warehouses = set()

        for w_idx, cand in enumerate(candidates):
            wh_used = False
            for p_idx, demand in enumerate(demands):
                val = round(x[(w_idx, p_idx)].solution_value())
                if val > 0:
                    wh_used = True
                    unit_shipping = cand.shipping_base_cost + (cand.distance_km * cand.shipping_cost_per_km)
                    shipping_cost = round(unit_shipping * val, 2)
                    handling_cost = round(cand.processing_cost_per_unit * val, 2)

                    allocations.append(AllocationUnit(
                        warehouse_id=cand.warehouse_id,
                        product_id=demand.product_id,
                        quantity=val,
                        shipping_cost=shipping_cost,
                        handling_cost=handling_cost
                    ))
                    total_cost += (shipping_cost + handling_cost)

            if wh_used:
                used_warehouses.add(cand.warehouse_id)

        return RoutingResult(
            strategy_name="OR_TOOLS_LP",
            is_feasible=True,
            allocations=allocations,
            total_cost=round(total_cost, 2),
            split_count=len(used_warehouses)
        )
