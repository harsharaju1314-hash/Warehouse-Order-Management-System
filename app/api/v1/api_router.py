"""API v1 router composition."""
from fastapi import APIRouter
from app.api.v1.endpoints import (
    health,
    products,
    warehouses,
    inventory,
    orders,
)

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(products.router, prefix="/products", tags=["Products"])
api_router.include_router(warehouses.router, prefix="/warehouses", tags=["Warehouses"])
api_router.include_router(inventory.router, prefix="/inventory", tags=["Inventory"])
api_router.include_router(orders.router, prefix="/orders", tags=["Orders"])
