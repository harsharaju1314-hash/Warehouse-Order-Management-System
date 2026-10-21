"""Pydantic schemas for Inventory."""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from app.models.movement import MovementType


class InventoryAdjustmentRequest(BaseModel):
    warehouse_id: str = Field(..., description="Target warehouse UUID")
    product_id: str = Field(..., description="Target product UUID")
    quantity_delta: int = Field(..., description="Positive to add stock, negative to decrease")
    reason: Optional[str] = Field("Manual adjustment", max_length=255)
    movement_type: Optional[MovementType] = Field(MovementType.ADJUSTMENT)


class InventoryResponse(BaseModel):
    id: str
    warehouse_id: str
    product_id: str
    quantity_on_hand: int
    quantity_reserved: int
    quantity_available: int
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InventoryOverviewItem(BaseModel):
    inventory_id: str
    warehouse_id: str
    warehouse_code: str
    warehouse_name: str
    product_id: str
    product_sku: str
    product_name: str
    quantity_on_hand: int
    quantity_reserved: int
    quantity_available: int
    updated_at: datetime


class InventoryMovementResponse(BaseModel):
    id: str
    inventory_id: str
    warehouse_id: str
    product_id: str
    change_type: MovementType
    quantity_delta: int
    balance_on_hand_after: int
    balance_reserved_after: int
    reference_order_id: Optional[str] = None
    reason: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
