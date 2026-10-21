"""Pydantic schemas for Orders and Allocations."""
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from app.models.order import OrderStatus
from app.models.allocation import AllocationStatus


class OrderItemCreate(BaseModel):
    product_id: str = Field(..., description="Product UUID to purchase")
    requested_quantity: int = Field(..., gt=0, description="Quantity of product required")


class OrderCreate(BaseModel):
    customer_id: str = Field(..., min_length=1, max_length=64)
    destination_lat: float = Field(..., ge=-90.0, le=90.0, description="Delivery latitude")
    destination_lon: float = Field(..., ge=-180.0, le=180.0, description="Delivery longitude")
    items: List[OrderItemCreate] = Field(..., min_length=1, description="List of items in order")
    routing_strategy: Optional[str] = Field("OR_TOOLS_LP", description="'OR_TOOLS_LP' or 'NEAREST_GREEDY'")


class OrderAllocateRequest(BaseModel):
    routing_strategy: Optional[str] = Field("OR_TOOLS_LP", description="Strategy override for routing")


class AllocationResponse(BaseModel):
    id: str
    order_id: str
    order_item_id: str
    warehouse_id: str
    warehouse_code: Optional[str] = None
    product_id: str
    product_sku: Optional[str] = None
    allocated_quantity: int
    estimated_shipping_cost: float
    estimated_handling_cost: float
    status: AllocationStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderItemResponse(BaseModel):
    id: str
    product_id: str
    product_sku: Optional[str] = None
    product_name: Optional[str] = None
    requested_quantity: int
    unit_price: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderResponse(BaseModel):
    id: str
    idempotency_key: Optional[str] = None
    customer_id: str
    destination_lat: float
    destination_lon: float
    status: OrderStatus
    total_item_price: float
    total_fulfillment_cost: float
    routing_strategy_used: Optional[str] = None
    failure_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemResponse] = []
    allocations: List[AllocationResponse] = []

    model_config = ConfigDict(from_attributes=True)
