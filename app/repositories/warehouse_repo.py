"""Warehouse database repository."""
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.warehouse import Warehouse, WarehouseStatus


class WarehouseRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, warehouse: Warehouse) -> Warehouse:
        self.session.add(warehouse)
        await self.session.flush()
        return warehouse

    async def get_by_id(self, warehouse_id: str) -> Optional[Warehouse]:
        stmt = select(Warehouse).where(Warehouse.id == warehouse_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> Optional[Warehouse]:
        stmt = select(Warehouse).where(Warehouse.code == code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(self, status: Optional[WarehouseStatus] = None) -> List[Warehouse]:
        stmt = select(Warehouse)
        if status:
            stmt = stmt.where(Warehouse.status == status)
        stmt = stmt.order_by(Warehouse.code.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_active(self) -> List[Warehouse]:
        stmt = select(Warehouse).where(Warehouse.status == WarehouseStatus.ACTIVE).order_by(Warehouse.code.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, warehouse: Warehouse) -> Warehouse:
        await self.session.flush()
        return warehouse
