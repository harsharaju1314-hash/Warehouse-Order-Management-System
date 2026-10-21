"""Order management and fulfillment REST endpoints."""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.deps import get_idempotency_key
from app.services.order_service import OrderService
from app.models.order import OrderStatus
from app.schemas.order import (
    OrderCreate,
    OrderResponse,
    OrderAllocateRequest
)
from app.schemas.common import PaginatedResponse

router = APIRouter()


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    data: OrderCreate,
    idempotency_key: Optional[str] = Depends(get_idempotency_key),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new order and immediately run linear programming optimization routing
    to atomically reserve inventory across eligible warehouses.
    Guarded by X-Idempotency-Key header to prevent duplicate submissions.
    """
    service = OrderService(db)
    return await service.create_and_allocate_order(data, idempotency_key=idempotency_key)


@router.get("", response_model=PaginatedResponse[OrderResponse])
async def list_orders(
    status: Optional[OrderStatus] = Query(None),
    customer_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    """List orders with pagination and filtering."""
    service = OrderService(db)
    items, total = await service.list_orders(
        status=status, customer_id=customer_id, page=page, size=size
    )
    pages = (total + size - 1) // size if total > 0 else 1
    return PaginatedResponse(
        items=[OrderResponse.model_validate(o) for o in items],
        total=total,
        page=page,
        size=size,
        pages=pages
    )


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve full details of an order, including warehouse allocations and item breakdowns."""
    service = OrderService(db)
    return await service.get_order(order_id)


@router.post("/{order_id}/fulfill", response_model=OrderResponse)
async def fulfill_order(
    order_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Confirm shipment and deduct actual inventory balances from warehouses."""
    service = OrderService(db)
    return await service.fulfill_order(order_id)


@router.post("/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(
    order_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Cancel order and safely release all reserved inventory back to warehouse stocks."""
    service = OrderService(db)
    return await service.cancel_order(order_id)
