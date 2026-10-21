"""Product business logic and cache synchronization."""
from typing import List, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductUpdate
from app.repositories.product_repo import ProductRepository
from app.core.redis import redis_client
from app.core.exceptions import ResourceNotFoundError, WOMSException
from app.core.logging import logger


class ProductService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ProductRepository(session)

    async def create_product(self, data: ProductCreate) -> Product:
        existing = await self.repo.get_by_sku(data.sku)
        if existing:
            raise WOMSException(f"Product with SKU '{data.sku}' already exists", code="SKU_EXISTS")

        product = Product(
            sku=data.sku,
            name=data.name,
            description=data.description,
            price=data.price,
            weight_kg=data.weight_kg,
            is_active=True
        )
        created = await self.repo.create(product)
        await self.session.commit()
        logger.info(f"Created product SKU: {created.sku} (ID: {created.id})")
        return created

    async def get_product(self, product_id: str) -> Product:
        # Check Redis cache
        cache_key = f"product:{product_id}"
        cached = await redis_client.get_json(cache_key)
        if cached:
            return Product(**cached)

        product = await self.repo.get_by_id(product_id)
        if not product:
            raise ResourceNotFoundError("Product", product_id)

        # Cache product data
        await redis_client.set_json(cache_key, {
            "id": product.id,
            "sku": product.sku,
            "name": product.name,
            "description": product.description,
            "price": float(product.price),
            "weight_kg": float(product.weight_kg),
            "is_active": product.is_active,
            "created_at": product.created_at.isoformat(),
            "updated_at": product.updated_at.isoformat(),
        }, ex=300)
        return product

    async def list_products(
        self, page: int = 1, size: int = 50, active_only: bool = True
    ) -> Tuple[List[Product], int]:
        return await self.repo.list(page=page, size=size, active_only=active_only)

    async def update_product(self, product_id: str, data: ProductUpdate) -> Product:
        product = await self.repo.get_by_id(product_id)
        if not product:
            raise ResourceNotFoundError("Product", product_id)

        if data.name is not None:
            product.name = data.name
        if data.description is not None:
            product.description = data.description
        if data.price is not None:
            product.price = data.price
        if data.weight_kg is not None:
            product.weight_kg = data.weight_kg
        if data.is_active is not None:
            product.is_active = data.is_active

        updated = await self.repo.update(product)
        await self.session.commit()

        # Invalidate cache
        await redis_client.delete(f"product:{product_id}")
        logger.info(f"Updated product ID: {product_id} and invalidated cache")
        return updated
