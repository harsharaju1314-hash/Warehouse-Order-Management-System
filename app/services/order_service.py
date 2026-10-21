"""Order lifecycle orchestrator with atomic reservations, routing, and idempotency."""
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.order import Order, OrderItem, OrderStatus
from app.models.allocation import Allocation, AllocationStatus
from app.models.warehouse import Warehouse, WarehouseStatus
from app.schemas.order import OrderCreate, OrderAllocateRequest
from app.repositories.order_repo import OrderRepository
from app.repositories.product_repo import ProductRepository
from app.repositories.warehouse_repo import WarehouseRepository
from app.repositories.inventory_repo import InventoryRepository
from app.services.idempotency_service import IdempotencyService
from app.routing import (
    get_routing_strategy,
    WarehouseCandidate,
    OrderDemand,
    calculate_haversine_distance_km
)
from app.core.exceptions import (
    ResourceNotFoundError,
    InsufficientInventoryError,
    OrderStateError,
    InfeasibleOptimizationError,
    WOMSException
)
from app.core.redis import redis_client
from app.core.logging import logger
from app.config import settings


class OrderService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.order_repo = OrderRepository(session)
        self.product_repo = ProductRepository(session)
        self.warehouse_repo = WarehouseRepository(session)
        self.inventory_repo = InventoryRepository(session)
        self.idempotency = IdempotencyService()

    async def create_and_allocate_order(
        self, data: OrderCreate, idempotency_key: Optional[str] = None
    ) -> Order:
        """
        Orchestrates order creation, candidate discovery, linear optimization routing,
        and atomic deadlock-free inventory reservation.
        """
        # 1. Idempotency Check
        if idempotency_key:
            # Check DB first in case key was already committed
            existing_db_order = await self.order_repo.get_by_idempotency_key(idempotency_key)
            if existing_db_order:
                logger.info(f"Order with idempotency key '{idempotency_key}' already exists in DB. Returning.")
                return existing_db_order

            # Coordinate distributed lock/lease in Redis
            await self.idempotency.check_or_lock(idempotency_key)

        try:
            # 2. Product Validation & Pricing Calculation
            order_items: List[OrderItem] = []
            demands: List[OrderDemand] = []
            product_ids = [item.product_id for item in data.items]
            total_item_price = 0.0

            import uuid
            order_id = str(uuid.uuid4())

            for item_in in data.items:
                product = await self.product_repo.get_by_id(item_in.product_id)
                if not product or not product.is_active:
                    raise ResourceNotFoundError("Active Product", item_in.product_id)

                unit_price = float(product.price)
                total_item_price += unit_price * item_in.requested_quantity

                order_item = OrderItem(
                    id=str(uuid.uuid4()),
                    order_id=order_id,
                    product_id=product.id,
                    requested_quantity=item_in.requested_quantity,
                    unit_price=unit_price
                )
                order_items.append(order_item)

                demands.append(OrderDemand(
                    product_id=product.id,
                    requested_quantity=item_in.requested_quantity,
                    unit_price=unit_price,
                    weight_kg=float(product.weight_kg)
                ))

            # 3. Create Order Record (PENDING)
            strategy_name = data.routing_strategy or settings.DEFAULT_ROUTING_STRATEGY
            order = Order(
                id=order_id,
                idempotency_key=idempotency_key,
                customer_id=data.customer_id,
                destination_lat=data.destination_lat,
                destination_lon=data.destination_lon,
                status=OrderStatus.PENDING,
                total_item_price=total_item_price,
                routing_strategy_used=strategy_name
            )
            order = await self.order_repo.create(order, order_items)
            await self.session.flush()

            # 4. Gather Eligible Warehouses & Inventory
            active_warehouses = await self.warehouse_repo.list_active()
            if not active_warehouses:
                order.status = OrderStatus.FAILED
                order.failure_reason = "No active warehouses available."
                await self.session.commit()
                raise InfeasibleOptimizationError("No active warehouses available.")

            stock_records = await self.inventory_repo.get_stock_for_products(
                product_ids, active_warehouses_only=True
            )

            # Build warehouse candidate profiles
            candidates: List[WarehouseCandidate] = []
            for wh in active_warehouses:
                dist = calculate_haversine_distance_km(
                    wh.latitude, wh.longitude, data.destination_lat, data.destination_lon
                )
                # Map product available stock for this warehouse
                wh_stock: Dict[str, int] = {}
                for rec in stock_records:
                    if rec.warehouse_id == wh.id:
                        wh_stock[rec.product_id] = rec.quantity_available

                cap_remaining = max(0, wh.capacity_limit - wh.current_daily_load)
                candidates.append(WarehouseCandidate(
                    warehouse_id=wh.id,
                    warehouse_code=wh.code,
                    latitude=wh.latitude,
                    longitude=wh.longitude,
                    distance_km=dist,
                    shipping_base_cost=float(wh.shipping_base_cost),
                    shipping_cost_per_km=float(wh.shipping_cost_per_km),
                    processing_cost_per_unit=float(wh.processing_cost_per_unit),
                    capacity_remaining=cap_remaining,
                    stock_by_product=wh_stock
                ))

            # 5. Execute Routing Algorithm (OR-Tools LP / Greedy Baseline)
            router = get_routing_strategy(strategy_name)
            result = router.route_order(
                dest_lat=data.destination_lat,
                dest_lon=data.destination_lon,
                demands=demands,
                candidates=candidates,
                max_splits=settings.MAX_WAREHOUSE_SPLITS
            )

            if not result.is_feasible:
                order.status = OrderStatus.FAILED
                order.failure_reason = result.failure_reason
                await self.session.commit()
                if idempotency_key:
                    await self.idempotency.release_on_failure(idempotency_key)
                raise InsufficientInventoryError(
                    product_id="MULTI", requested=0, available=0
                ) if "inventory" in result.failure_reason.lower() else InfeasibleOptimizationError(result.failure_reason)

            # 6. Deadlock-Free Atomic Reservation
            # Sort allocation units by (warehouse_id, product_id) ascending
            sorted_allocs = sorted(result.allocations, key=lambda a: (a.warehouse_id, a.product_id))

            created_allocations: List[Allocation] = []
            # Map product_id to corresponding order_item_id
            product_to_item = {item.product_id: item.id for item in order.items}

            for alloc_unit in sorted_allocs:
                # Lock row and increment reserved
                await self.inventory_repo.reserve_stock(
                    warehouse_id=alloc_unit.warehouse_id,
                    product_id=alloc_unit.product_id,
                    quantity=alloc_unit.quantity,
                    order_id=order.id
                )

                alloc_record = Allocation(
                    id=str(uuid.uuid4()),
                    order_id=order.id,
                    order_item_id=product_to_item[alloc_unit.product_id],
                    warehouse_id=alloc_unit.warehouse_id,
                    product_id=alloc_unit.product_id,
                    allocated_quantity=alloc_unit.quantity,
                    estimated_shipping_cost=alloc_unit.shipping_cost,
                    estimated_handling_cost=alloc_unit.handling_cost,
                    status=AllocationStatus.RESERVED
                )
                created_allocations.append(alloc_record)

                # Increment warehouse daily load
                wh = await self.warehouse_repo.get_by_id(alloc_unit.warehouse_id)
                if wh:
                    wh.current_daily_load += alloc_unit.quantity

            await self.order_repo.add_allocations(created_allocations)

            # 7. Finalize Order Commit
            order.status = OrderStatus.RESERVED
            order.total_fulfillment_cost = result.total_cost
            await self.session.commit()

            # 8. Invalidate Caches
            for pid in product_ids:
                await redis_client.delete(f"stock:{pid}")
            await redis_client.delete("inventory_overview")

            # 9. Complete Idempotency
            if idempotency_key:
                serialized = {
                    "id": order.id,
                    "idempotency_key": order.idempotency_key,
                    "customer_id": order.customer_id,
                    "status": order.status.value,
                    "total_item_price": float(order.total_item_price),
                    "total_fulfillment_cost": float(order.total_fulfillment_cost),
                }
                await self.idempotency.mark_completed(idempotency_key, serialized)

            logger.info(
                f"Order {order.id} successfully RESERVED. Fulfillment Cost: ${order.total_fulfillment_cost:.2f}, "
                f"Strategy: {strategy_name}, Splits: {result.split_count}"
            )
            return await self.order_repo.get_by_id(order.id)

        except Exception as exc:
            await self.session.rollback()
            if idempotency_key and not isinstance(exc, InsufficientInventoryError):
                await self.idempotency.release_on_failure(idempotency_key)
            raise

    async def get_order(self, order_id: str) -> Order:
        order = await self.order_repo.get_by_id(order_id)
        if not order:
            raise ResourceNotFoundError("Order", order_id)
        return order

    async def fulfill_order(self, order_id: str) -> Order:
        """Transitions order from RESERVED -> FULFILLED, deducting actual stock balances."""
        order = await self.order_repo.get_by_id(order_id, for_update=True)
        if not order:
            raise ResourceNotFoundError("Order", order_id)

        if order.status not in (OrderStatus.RESERVED, OrderStatus.PROCESSING):
            raise OrderStateError(order_id, order.status.value, "FULFILL")

        # Deduct actual inventory
        for alloc in order.allocations:
            if alloc.status == AllocationStatus.RESERVED:
                await self.inventory_repo.fulfill_stock(
                    warehouse_id=alloc.warehouse_id,
                    product_id=alloc.product_id,
                    quantity=alloc.allocated_quantity,
                    order_id=order.id
                )
                alloc.status = AllocationStatus.SHIPPED

        order.status = OrderStatus.FULFILLED
        await self.session.commit()

        # Invalidate stock cache
        for alloc in order.allocations:
            await redis_client.delete(f"stock:{alloc.product_id}")
        await redis_client.delete("inventory_overview")

        logger.info(f"Order {order.id} transitioned to FULFILLED")
        return order

    async def cancel_order(self, order_id: str) -> Order:
        """Safely cancels an order and releases all reserved inventory."""
        order = await self.order_repo.get_by_id(order_id, for_update=True)
        if not order:
            raise ResourceNotFoundError("Order", order_id)

        if order.status == OrderStatus.FULFILLED:
            raise OrderStateError(order_id, order.status.value, "CANCEL")

        if order.status == OrderStatus.CANCELLED:
            return order

        # Release reserved quantities if order was reserved
        if order.status in (OrderStatus.RESERVED, OrderStatus.PROCESSING):
            for alloc in order.allocations:
                if alloc.status == AllocationStatus.RESERVED:
                    await self.inventory_repo.release_reservation(
                        warehouse_id=alloc.warehouse_id,
                        product_id=alloc.product_id,
                        quantity=alloc.allocated_quantity,
                        order_id=order.id
                    )
                    alloc.status = AllocationStatus.RELEASED

                    # Decrement warehouse daily load
                    wh = await self.warehouse_repo.get_by_id(alloc.warehouse_id)
                    if wh:
                        wh.current_daily_load = max(0, wh.current_daily_load - alloc.allocated_quantity)

        order.status = OrderStatus.CANCELLED
        await self.session.commit()

        # Invalidate cache
        for alloc in order.allocations:
            await redis_client.delete(f"stock:{alloc.product_id}")
        await redis_client.delete("inventory_overview")

        logger.info(f"Order {order.id} CANCELLED. Reservations safely released.")
        return order

    async def list_orders(
        self,
        status: Optional[OrderStatus] = None,
        customer_id: Optional[str] = None,
        page: int = 1,
        size: int = 50,
    ) -> Tuple[List[Order], int]:
        return await self.order_repo.list(status=status, customer_id=customer_id, page=page, size=size)
