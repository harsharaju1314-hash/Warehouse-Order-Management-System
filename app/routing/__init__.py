"""Routing module registry and strategy factory."""
from app.routing.base import (
    BaseRoutingStrategy,
    WarehouseCandidate,
    OrderDemand,
    RoutingResult,
    AllocationUnit,
    calculate_haversine_distance_km,
)
from app.routing.greedy_nearest import GreedyNearestRoutingStrategy
from app.routing.or_tools_lp import ORToolsLPRoutingStrategy


def get_routing_strategy(name: str = "OR_TOOLS_LP") -> BaseRoutingStrategy:
    """Factory to retrieve requested routing algorithm."""
    if name.upper() in ("OR_TOOLS", "OR_TOOLS_LP", "LP", "MIP"):
        return ORToolsLPRoutingStrategy()
    elif name.upper() in ("GREEDY", "NEAREST", "NEAREST_GREEDY"):
        return GreedyNearestRoutingStrategy()
    else:
        # Default to OR-Tools LP
        return ORToolsLPRoutingStrategy()


__all__ = [
    "BaseRoutingStrategy",
    "WarehouseCandidate",
    "OrderDemand",
    "RoutingResult",
    "AllocationUnit",
    "calculate_haversine_distance_km",
    "GreedyNearestRoutingStrategy",
    "ORToolsLPRoutingStrategy",
    "get_routing_strategy",
]
