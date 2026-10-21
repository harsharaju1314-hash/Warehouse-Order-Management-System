"""Warehouse management REST endpoints."""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.warehouse_service import WarehouseService
from app.models.warehouse import WarehouseStatus
from app.schemas.warehouse import WarehouseCreate, WarehouseUpdate, WarehouseResponse

router = APIRouter()


@router.post("", response_model=WarehouseResponse, status_code=status.HTTP_201_CREATED)
async def create_warehouse(
    data: WarehouseCreate,
    db: AsyncSession = Depends(get_db)
):
    """Register a new warehouse node."""
    service = WarehouseService(db)
    return await service.create_warehouse(data)


@router.get("", response_model=List[WarehouseResponse])
async def list_warehouses(
    status: Optional[WarehouseStatus] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve all warehouse nodes, optionally filtered by status."""
    service = WarehouseService(db)
    return await service.list_warehouses(status=status)


@router.get("/{warehouse_id}", response_model=WarehouseResponse)
async def get_warehouse(
    warehouse_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve warehouse node details by ID."""
    service = WarehouseService(db)
    return await service.get_warehouse(warehouse_id)


@router.patch("/{warehouse_id}", response_model=WarehouseResponse)
async def update_warehouse(
    warehouse_id: str,
    data: WarehouseUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update warehouse status, capacity, or cost parameters."""
    service = WarehouseService(db)
    return await service.update_warehouse(warehouse_id, data)
