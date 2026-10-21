"""Pydantic schemas registry."""
from app.schemas.common import ErrorResponse, PaginatedResponse, MessageResponse
from app.schemas.product import ProductCreate, ProductUpdate, ProductResponse
from app.schemas.warehouse import (
    WarehouseCreate, WarehouseUpdate, WarehouseResponse, WarehouseHealthResponse
)
from app.schemas.inventory import (
    InventoryAdjustmentRequest, InventoryResponse, InventoryOverviewItem,
    InventoryMovementResponse
)
from app.schemas.order import (
    OrderItemCreate, OrderCreate, OrderAllocateRequest,
    AllocationResponse, OrderItemResponse, OrderResponse
)

__all__ = [
    "ErrorResponse",
    "PaginatedResponse",
    "MessageResponse",
    "ProductCreate",
    "ProductUpdate",
    "ProductResponse",
    "WarehouseCreate",
    "WarehouseUpdate",
    "WarehouseResponse",
    "WarehouseHealthResponse",
    "InventoryAdjustmentRequest",
    "InventoryResponse",
    "InventoryOverviewItem",
    "InventoryMovementResponse",
    "OrderItemCreate",
    "OrderCreate",
    "OrderAllocateRequest",
    "AllocationResponse",
    "OrderItemResponse",
    "OrderResponse",
]
