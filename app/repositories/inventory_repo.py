"""Inventory and Movement database repository with atomic locking."""
from typing import Optional, List, Tuple
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.inventory import Inventory
from app.models.movement import InventoryMovement, MovementType
from app.models.warehouse import Warehouse, WarehouseStatus
from app.models.product import Product
from app.core.exceptions import InsufficientInventoryError, ResourceNotFoundError
from app.core.logging import logger


class InventoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_warehouse_and_product(
        self, warehouse_id: str, product_id: str, for_update: bool = False
    ) -> Optional[Inventory]:
        stmt = select(Inventory).where(
            and_(
                Inventory.warehouse_id == warehouse_id,
                Inventory.product_id == product_id
            )
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create(self, warehouse_id: str, product_id: str) -> Inventory:
        inv = await self.get_by_warehouse_and_product(warehouse_id, product_id, for_update=True)
        if not inv:
            inv = Inventory(
                warehouse_id=warehouse_id,
                product_id=product_id,
                quantity_on_hand=0,
                quantity_reserved=0
            )
            self.session.add(inv)
            await self.session.flush()
        return inv

    async def get_stock_for_products(
        self, product_ids: List[str], active_warehouses_only: bool = True
    ) -> List[Inventory]:
        """Fetch all inventory records for given product IDs, eagerly loading warehouse."""
        stmt = select(Inventory).join(Warehouse).where(Inventory.product_id.in_(product_ids))
        if active_warehouses_only:
            stmt = stmt.where(Warehouse.status == WarehouseStatus.ACTIVE)
        stmt = stmt.options(selectinload(Inventory.warehouse), selectinload(Inventory.product))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def adjust_stock(
        self,
        warehouse_id: str,
        product_id: str,
        quantity_delta: int,
        reason: str = "Adjustment",
        movement_type: MovementType = MovementType.ADJUSTMENT,
        reference_order_id: Optional[str] = None
    ) -> Inventory:
        """Atomically adjust on-hand stock and write to audit ledger."""
        inv = await self.get_or_create(warehouse_id, product_id)
        
        new_on_hand = inv.quantity_on_hand + quantity_delta
        if new_on_hand < inv.quantity_reserved:
            raise InsufficientInventoryError(
                product_id=product_id,
                requested=abs(quantity_delta),
                available=inv.quantity_on_hand - inv.quantity_reserved
            )

        inv.quantity_on_hand = new_on_hand
        inv.version += 1
        await self.session.flush()

        # Audit movement
        movement = InventoryMovement(
            inventory_id=inv.id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            change_type=movement_type,
            quantity_delta=quantity_delta,
            balance_on_hand_after=inv.quantity_on_hand,
            balance_reserved_after=inv.quantity_reserved,
            reference_order_id=reference_order_id,
            reason=reason
        )
        self.session.add(movement)
        await self.session.flush()
        return inv

    async def reserve_stock(
        self,
        warehouse_id: str,
        product_id: str,
        quantity: int,
        order_id: str
    ) -> Inventory:
        """Atomically increment reserved stock count with row lock."""
        inv = await self.get_by_warehouse_and_product(warehouse_id, product_id, for_update=True)
        if not inv:
            raise ResourceNotFoundError(f"Inventory in warehouse {warehouse_id} for product", product_id)

        available = inv.quantity_on_hand - inv.quantity_reserved
        if available < quantity:
            raise InsufficientInventoryError(
                product_id=product_id,
                requested=quantity,
                available=available
            )

        inv.quantity_reserved += quantity
        inv.version += 1
        await self.session.flush()

        # Audit movement
        movement = InventoryMovement(
            inventory_id=inv.id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            change_type=MovementType.RESERVATION_CREATED,
            quantity_delta=quantity,
            balance_on_hand_after=inv.quantity_on_hand,
            balance_reserved_after=inv.quantity_reserved,
            reference_order_id=order_id,
            reason=f"Reservation for order {order_id}"
        )
        self.session.add(movement)
        await self.session.flush()
        return inv

    async def release_reservation(
        self,
        warehouse_id: str,
        product_id: str,
        quantity: int,
        order_id: str
    ) -> Inventory:
        """Atomically release reserved stock count with row lock."""
        inv = await self.get_by_warehouse_and_product(warehouse_id, product_id, for_update=True)
        if not inv:
            raise ResourceNotFoundError(f"Inventory in warehouse {warehouse_id} for product", product_id)

        inv.quantity_reserved = max(0, inv.quantity_reserved - quantity)
        inv.version += 1
        await self.session.flush()

        movement = InventoryMovement(
            inventory_id=inv.id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            change_type=MovementType.RESERVATION_RELEASED,
            quantity_delta=-quantity,
            balance_on_hand_after=inv.quantity_on_hand,
            balance_reserved_after=inv.quantity_reserved,
            reference_order_id=order_id,
            reason=f"Released reservation for order {order_id}"
        )
        self.session.add(movement)
        await self.session.flush()
        return inv

    async def fulfill_stock(
        self,
        warehouse_id: str,
        product_id: str,
        quantity: int,
        order_id: str
    ) -> Inventory:
        """Atomically deduct on-hand and reserved stock upon shipment."""
        inv = await self.get_by_warehouse_and_product(warehouse_id, product_id, for_update=True)
        if not inv:
            raise ResourceNotFoundError(f"Inventory in warehouse {warehouse_id} for product", product_id)

        inv.quantity_on_hand -= quantity
        inv.quantity_reserved = max(0, inv.quantity_reserved - quantity)
        inv.version += 1
        await self.session.flush()

        movement = InventoryMovement(
            inventory_id=inv.id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            change_type=MovementType.FULFILLMENT_DEDUCTED,
            quantity_delta=-quantity,
            balance_on_hand_after=inv.quantity_on_hand,
            balance_reserved_after=inv.quantity_reserved,
            reference_order_id=order_id,
            reason=f"Fulfillment deduction for order {order_id}"
        )
        self.session.add(movement)
        await self.session.flush()
        return inv

    async def list_overview(self) -> List[dict]:
        """Fetch all inventories with warehouse and product joined details."""
        stmt = (
            select(Inventory)
            .options(selectinload(Inventory.warehouse), selectinload(Inventory.product))
            .order_by(Inventory.updated_at.desc())
        )
        result = await self.session.execute(stmt)
        items = result.scalars().all()
        return [
            {
                "inventory_id": inv.id,
                "warehouse_id": inv.warehouse_id,
                "warehouse_code": inv.warehouse.code if inv.warehouse else "N/A",
                "warehouse_name": inv.warehouse.name if inv.warehouse else "N/A",
                "product_id": inv.product_id,
                "product_sku": inv.product.sku if inv.product else "N/A",
                "product_name": inv.product.name if inv.product else "N/A",
                "quantity_on_hand": inv.quantity_on_hand,
                "quantity_reserved": inv.quantity_reserved,
                "quantity_available": inv.quantity_available,
                "updated_at": inv.updated_at,
            }
            for inv in items
        ]

    async def list_movements(
        self, warehouse_id: Optional[str] = None, product_id: Optional[str] = None, limit: int = 100
    ) -> List[InventoryMovement]:
        stmt = select(InventoryMovement)
        if warehouse_id:
            stmt = stmt.where(InventoryMovement.warehouse_id == warehouse_id)
        if product_id:
            stmt = stmt.where(InventoryMovement.product_id == product_id)
        stmt = stmt.order_by(InventoryMovement.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
