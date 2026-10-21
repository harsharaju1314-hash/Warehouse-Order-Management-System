"""Product database repository."""
from typing import Optional, List, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.product import Product


class ProductRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, product: Product) -> Product:
        self.session.add(product)
        await self.session.flush()
        return product

    async def get_by_id(self, product_id: str) -> Optional[Product]:
        stmt = select(Product).where(Product.id == product_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_sku(self, sku: str) -> Optional[Product]:
        stmt = select(Product).where(Product.sku == sku)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self, page: int = 1, size: int = 50, active_only: bool = True
    ) -> Tuple[List[Product], int]:
        stmt = select(Product)
        if active_only:
            stmt = stmt.where(Product.is_active == True)
        
        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()

        # Paginated items
        stmt = stmt.order_by(Product.created_at.desc()).offset((page - 1) * size).limit(size)
        items = (await self.session.execute(stmt)).scalars().all()
        return list(items), total

    async def update(self, product: Product) -> Product:
        await self.session.flush()
        return product
