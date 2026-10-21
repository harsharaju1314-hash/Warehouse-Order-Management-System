"""Pydantic schemas for Products."""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class ProductBase(BaseModel):
    sku: str = Field(..., min_length=2, max_length=64, description="Unique product SKU")
    name: str = Field(..., min_length=1, max_length=255, description="Product title")
    description: Optional[str] = Field(None, max_length=1000)
    price: float = Field(..., gt=0, description="Product price in currency units")
    weight_kg: float = Field(1.0, gt=0, description="Weight per unit in kilograms")


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    price: Optional[float] = Field(None, gt=0)
    weight_kg: Optional[float] = Field(None, gt=0)
    is_active: Optional[bool] = None


class ProductResponse(ProductBase):
    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
