"""Product management REST endpoints."""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.product_service import ProductService
from app.schemas.product import ProductCreate, ProductUpdate, ProductResponse
from app.schemas.common import PaginatedResponse

router = APIRouter()


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    data: ProductCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new product catalog entry."""
    service = ProductService(db)
    return await service.create_product(data)


@router.get("", response_model=PaginatedResponse[ProductResponse])
async def list_products(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    active_only: bool = Query(True),
    db: AsyncSession = Depends(get_db)
):
    """List products with pagination."""
    service = ProductService(db)
    items, total = await service.list_products(page=page, size=size, active_only=active_only)
    pages = (total + size - 1) // size if total > 0 else 1
    return PaginatedResponse(
        items=[ProductResponse.model_validate(p) for p in items],
        total=total,
        page=page,
        size=size,
        pages=pages
    )


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve product details by ID."""
    service = ProductService(db)
    return await service.get_product(product_id)


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str,
    data: ProductUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update product details or active status."""
    service = ProductService(db)
    return await service.update_product(product_id, data)
