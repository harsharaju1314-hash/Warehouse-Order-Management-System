"""Order and Allocation database repository."""
from typing import Optional, List, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.order import Order, OrderItem, OrderStatus
from app.models.allocation import Allocation, AllocationStatus


class OrderRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, order: Order, items: List[OrderItem]) -> Order:
        import uuid
        if not order.id:
            order.id = str(uuid.uuid4())
        self.session.add(order)
        for item in items:
            if not item.id:
                item.id = str(uuid.uuid4())
            item.order = order
            item.order_id = order.id
            self.session.add(item)
        await self.session.flush()
        return order

    async def get_by_id(self, order_id: str, for_update: bool = False) -> Optional[Order]:
        stmt = (
            select(Order)
            .where(Order.id == order_id)
            .options(
                selectinload(Order.items).selectinload(OrderItem.product),
                selectinload(Order.allocations).selectinload(Allocation.warehouse),
                selectinload(Order.allocations).selectinload(Allocation.product),
            )
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_idempotency_key(self, key: str) -> Optional[Order]:
        stmt = (
            select(Order)
            .where(Order.idempotency_key == key)
            .options(
                selectinload(Order.items).selectinload(OrderItem.product),
                selectinload(Order.allocations).selectinload(Allocation.warehouse),
                selectinload(Order.allocations).selectinload(Allocation.product),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_allocations(self, allocations: List[Allocation]) -> List[Allocation]:
        for alloc in allocations:
            self.session.add(alloc)
        await self.session.flush()
        return allocations

    async def update_status(
        self, order: Order, status: OrderStatus, failure_reason: Optional[str] = None
    ) -> Order:
        order.status = status
        if failure_reason is not None:
            order.failure_reason = failure_reason
        await self.session.flush()
        return order

    async def list(
        self,
        status: Optional[OrderStatus] = None,
        customer_id: Optional[str] = None,
        page: int = 1,
        size: int = 50,
    ) -> Tuple[List[Order], int]:
        stmt = select(Order)
        if status:
            stmt = stmt.where(Order.status == status)
        if customer_id:
            stmt = stmt.where(Order.customer_id == customer_id)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()

        stmt = (
            stmt.options(
                selectinload(Order.items).selectinload(OrderItem.product),
                selectinload(Order.allocations).selectinload(Allocation.warehouse),
                selectinload(Order.allocations).selectinload(Allocation.product),
            )
            .order_by(Order.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total
