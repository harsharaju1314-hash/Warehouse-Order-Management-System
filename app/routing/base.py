"""Base routing abstractions and spatial cost calculations."""
import math
from abc import ABC, abstractmethod
from typing import Dict, List, NamedTuple
from dataclasses import dataclass


def calculate_haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on the Earth in kilometers."""
    radius_km = 6371.0088

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(radius_km * c, 2)


@dataclass
class WarehouseCandidate:
    warehouse_id: str
    warehouse_code: str
    latitude: float
    longitude: float
    distance_km: float
    shipping_base_cost: float
    shipping_cost_per_km: float
    processing_cost_per_unit: float
    capacity_remaining: int
    stock_by_product: Dict[str, int]  # product_id -> available_stock


@dataclass
class OrderDemand:
    product_id: str
    requested_quantity: int
    unit_price: float
    weight_kg: float


@dataclass
class AllocationUnit:
    warehouse_id: str
    product_id: str
    quantity: int
    shipping_cost: float
    handling_cost: float

    @property
    def total_cost(self) -> float:
        return self.shipping_cost + self.handling_cost


@dataclass
class RoutingResult:
    strategy_name: str
    is_feasible: bool
    allocations: List[AllocationUnit]
    total_cost: float
    failure_reason: str = ""
    split_count: int = 0


class BaseRoutingStrategy(ABC):
    @abstractmethod
    def route_order(
        self,
        dest_lat: float,
        dest_lon: float,
        demands: List[OrderDemand],
        candidates: List[WarehouseCandidate],
        max_splits: int = 3
    ) -> RoutingResult:
        """Determines warehouse allocations to satisfy order demands."""
        pass
