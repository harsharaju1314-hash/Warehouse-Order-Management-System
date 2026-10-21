"""Warehouse business service and health status evaluator."""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.warehouse import Warehouse, WarehouseStatus
from app.models.inventory import Inventory
from app.schemas.warehouse import WarehouseCreate, WarehouseUpdate, WarehouseHealthResponse
from app.repositories.warehouse_repo import WarehouseRepository
from app.core.exceptions import ResourceNotFoundError, WOMSException
from app.core.redis import redis_client
from app.core.logging import logger


class WarehouseService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = WarehouseRepository(session)

    async def create_warehouse(self, data: WarehouseCreate) -> Warehouse:
        existing = await self.repo.get_by_code(data.code)
        if existing:
            raise WOMSException(f"Warehouse with code '{data.code}' already exists", code="WAREHOUSE_EXISTS")

        wh = Warehouse(
            code=data.code,
            name=data.name,
            address=data.address,
            city=data.city,
            state=data.state,
            postal_code=data.postal_code,
            latitude=data.latitude,
            longitude=data.longitude,
            capacity_limit=data.capacity_limit,
            shipping_base_cost=data.shipping_base_cost,
            shipping_cost_per_km=data.shipping_cost_per_km,
            processing_cost_per_unit=data.processing_cost_per_unit,
            status=WarehouseStatus.ACTIVE
        )
        created = await self.repo.create(wh)
        await self.session.commit()
        logger.info(f"Created warehouse {created.code} (ID: {created.id})")
        return created

    async def get_warehouse(self, warehouse_id: str) -> Warehouse:
        wh = await self.repo.get_by_id(warehouse_id)
        if not wh:
            raise ResourceNotFoundError("Warehouse", warehouse_id)
        return wh

    async def list_warehouses(self, status: Optional[WarehouseStatus] = None) -> List[Warehouse]:
        return await self.repo.list(status=status)

    async def update_warehouse(self, warehouse_id: str, data: WarehouseUpdate) -> Warehouse:
        wh = await self.repo.get_by_id(warehouse_id)
        if not wh:
            raise ResourceNotFoundError("Warehouse", warehouse_id)

        if data.name is not None:
            wh.name = data.name
        if data.status is not None:
            wh.status = data.status
        if data.capacity_limit is not None:
            wh.capacity_limit = data.capacity_limit
        if data.shipping_base_cost is not None:
            wh.shipping_base_cost = data.shipping_base_cost
        if data.shipping_cost_per_km is not None:
            wh.shipping_cost_per_km = data.shipping_cost_per_km
        if data.processing_cost_per_unit is not None:
            wh.processing_cost_per_unit = data.processing_cost_per_unit

        updated = await self.repo.update(wh)
        await self.session.commit()
        # Invalidate cached health status
        await redis_client.delete(f"warehouse_health:{warehouse_id}")
        logger.info(f"Updated warehouse {warehouse_id} status to {wh.status}")
        return updated

    async def check_health(self, warehouse_id: str) -> WarehouseHealthResponse:
        wh = await self.repo.get_by_id(warehouse_id)
        if not wh:
            raise ResourceNotFoundError("Warehouse", warehouse_id)

        # Count active inventory records
        count_stmt = select(func.count(Inventory.id)).where(Inventory.warehouse_id == warehouse_id)
        inv_count = (await self.session.execute(count_stmt)).scalar_one()

        is_healthy = (wh.status == WarehouseStatus.ACTIVE) and (wh.current_daily_load < wh.capacity_limit)
        available_cap = max(0, wh.capacity_limit - wh.current_daily_load)

        return WarehouseHealthResponse(
            warehouse_id=wh.id,
            code=wh.code,
            name=wh.name,
            status=wh.status,
            is_healthy=is_healthy,
            current_daily_load=wh.current_daily_load,
            capacity_limit=wh.capacity_limit,
            available_capacity=available_cap,
            active_inventories_count=inv_count
        )

    async def get_all_health(self) -> List[WarehouseHealthResponse]:
        warehouses = await self.repo.list()
        return [await self.check_health(wh.id) for wh in warehouses]
