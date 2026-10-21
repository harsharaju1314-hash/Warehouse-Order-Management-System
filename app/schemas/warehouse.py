"""Pydantic schemas for Warehouses."""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from app.models.warehouse import WarehouseStatus


class WarehouseBase(BaseModel):
    code: str = Field(..., min_length=2, max_length=32, description="Unique warehouse identifier")
    name: str = Field(..., min_length=1, max_length=128)
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    capacity_limit: int = Field(1000, gt=0, description="Max daily throughput capacity in units")
    shipping_base_cost: float = Field(5.00, ge=0.0)
    shipping_cost_per_km: float = Field(0.05, ge=0.0)
    processing_cost_per_unit: float = Field(1.50, ge=0.0)


class WarehouseCreate(WarehouseBase):
    pass


class WarehouseUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[WarehouseStatus] = None
    capacity_limit: Optional[int] = Field(None, gt=0)
    shipping_base_cost: Optional[float] = Field(None, ge=0.0)
    shipping_cost_per_km: Optional[float] = Field(None, ge=0.0)
    processing_cost_per_unit: Optional[float] = Field(None, ge=0.0)


class WarehouseResponse(WarehouseBase):
    id: str
    current_daily_load: int
    status: WarehouseStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WarehouseHealthResponse(BaseModel):
    warehouse_id: str
    code: str
    name: str
    status: WarehouseStatus
    is_healthy: bool
    current_daily_load: int
    capacity_limit: int
    available_capacity: int
    active_inventories_count: int
