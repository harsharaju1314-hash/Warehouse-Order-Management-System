"""Health and diagnostic endpoints."""
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from app.core.redis import redis_client
from app.services.warehouse_service import WarehouseService
from app.schemas.warehouse import WarehouseHealthResponse
from app.core.logging import logger

router = APIRouter()


@router.get("/health", status_code=status.HTTP_200_OK)
async def get_system_health(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Inspects connectivity to PostgreSQL, Redis, and overall cluster health."""
    db_healthy = False
    try:
        await db.execute(text("SELECT 1"))
        db_healthy = True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")

    redis_healthy = False
    try:
        await redis_client.client.ping()
        redis_healthy = True
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")

    wh_service = WarehouseService(db)
    warehouses_health = await wh_service.get_all_health()
    active_wh_count = sum(1 for w in warehouses_health if w.is_healthy)

    is_overall_healthy = db_healthy and redis_healthy and (active_wh_count >= 1)

    return {
        "status": "HEALTHY" if is_overall_healthy else "DEGRADED",
        "database_connected": db_healthy,
        "redis_connected": redis_healthy,
        "active_warehouses_count": active_wh_count,
        "total_warehouses_count": len(warehouses_health),
    }


@router.get("/health/warehouses", response_model=List[WarehouseHealthResponse])
async def get_warehouses_health(db: AsyncSession = Depends(get_db)):
    """Detailed health, load, and capacity status for all warehouse nodes."""
    wh_service = WarehouseService(db)
    return await wh_service.get_all_health()
