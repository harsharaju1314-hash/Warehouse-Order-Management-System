"""Inventory business service with transactional integrity and cache invalidation."""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.inventory import Inventory
from app.models.movement import MovementType, InventoryMovement
from app.schemas.inventory import InventoryAdjustmentRequest, InventoryOverviewItem
from app.repositories.inventory_repo import InventoryRepository
from app.repositories.product_repo import ProductRepository
from app.repositories.warehouse_repo import WarehouseRepository
from app.core.exceptions import ResourceNotFoundError
from app.core.redis import redis_client
from app.core.logging import logger


class InventoryService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = InventoryRepository(session)
        self.product_repo = ProductRepository(session)
        self.warehouse_repo = WarehouseRepository(session)

    async def adjust_stock(self, data: InventoryAdjustmentRequest) -> Inventory:
        # Validate warehouse exists
        wh = await self.warehouse_repo.get_by_id(data.warehouse_id)
        if not wh:
            raise ResourceNotFoundError("Warehouse", data.warehouse_id)

        # Validate product exists
        prod = await self.product_repo.get_by_id(data.product_id)
        if not prod:
            raise ResourceNotFoundError("Product", data.product_id)

        inv = await self.repo.adjust_stock(
            warehouse_id=data.warehouse_id,
            product_id=data.product_id,
            quantity_delta=data.quantity_delta,
            reason=data.reason or "Manual adjustment",
            movement_type=data.movement_type or MovementType.ADJUSTMENT
        )
        await self.session.commit()

        # Invalidate stock cache for this product
        await redis_client.delete(f"stock:{data.product_id}")
        await redis_client.delete("inventory_overview")

        logger.info(
            f"Adjusted stock for WH: {data.warehouse_id}, Product: {data.product_id}, "
            f"Delta: {data.quantity_delta}, New On-Hand: {inv.quantity_on_hand}"
        )
        return inv

    async def get_overview(self) -> List[InventoryOverviewItem]:
        # Check cache
        cached = await redis_client.get_json("inventory_overview")
        if cached:
            return [InventoryOverviewItem(**item) for item in cached]

        overview_dicts = await self.repo.list_overview()
        items = [InventoryOverviewItem(**item) for item in overview_dicts]

        # Cache overview
        await redis_client.set_json(
            "inventory_overview",
            [item.model_dump(mode="json") for item in items],
            ex=60
        )
        return items

    async def get_movements(
        self, warehouse_id: Optional[str] = None, product_id: Optional[str] = None, limit: int = 100
    ) -> List[InventoryMovement]:
        return await self.repo.list_movements(warehouse_id=warehouse_id, product_id=product_id, limit=limit)
