"""Inventory management and stock audit REST endpoints."""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.inventory_service import InventoryService
from app.schemas.inventory import (
    InventoryAdjustmentRequest,
    InventoryResponse,
    InventoryOverviewItem,
    InventoryMovementResponse
)

router = APIRouter()


@router.get("", response_model=List[InventoryOverviewItem])
async def get_inventory_overview(
    db: AsyncSession = Depends(get_db)
):
    """Retrieve full inventory balance matrix across all warehouses and products."""
    service = InventoryService(db)
    return await service.get_overview()


@router.post("/adjustments", response_model=InventoryResponse, status_code=status.HTTP_200_OK)
async def adjust_inventory(
    data: InventoryAdjustmentRequest,
    db: AsyncSession = Depends(get_db)
):
    """Atomically adjust on-hand stock and create an immutable audit ledger movement."""
    service = InventoryService(db)
    return await service.adjust_stock(data)


@router.get("/movements", response_model=List[InventoryMovementResponse])
async def get_inventory_movements(
    warehouse_id: Optional[str] = Query(None),
    product_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve historical inventory movements for audit trail."""
    service = InventoryService(db)
    return await service.get_movements(warehouse_id=warehouse_id, product_id=product_id, limit=limit)
