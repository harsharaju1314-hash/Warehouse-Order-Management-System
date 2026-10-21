"""FastAPI application initialization and middleware configuration."""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.core.logging import logger
from app.core.database import init_db, engine
from app.core.redis import redis_client
from app.core.exceptions import (
    WOMSException,
    ResourceNotFoundError,
    InsufficientInventoryError,
    OrderStateError,
    IdempotencyConflictError,
    InfeasibleOptimizationError,
    WarehouseUnavailableError
)
from app.api.v1.api_router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and graceful shutdown."""
    logger.info(f"Starting {settings.APP_NAME} in {settings.APP_ENV} mode...")
    
    # 1. Connect Redis
    await redis_client.connect()
    
    # 2. Initialize Database tables
    await init_db()
    
    logger.info("Application startup completed successfully.")
    yield
    
    # Shutdown
    logger.info("Shutting down application resources...")
    await redis_client.close()
    await engine.dispose()
    logger.info("Clean shutdown completed.")


app = FastAPI(
    title=settings.APP_NAME,
    description="Production-inspired Warehouse Order Management System with Linear Programming routing and atomic reservations.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception Handlers
@app.exception_handler(ResourceNotFoundError)
async def resource_not_found_handler(request: Request, exc: ResourceNotFoundError):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"error": exc.message, "code": exc.code, "details": exc.details}
    )


@app.exception_handler(InsufficientInventoryError)
async def insufficient_inventory_handler(request: Request, exc: InsufficientInventoryError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": exc.message, "code": exc.code, "details": exc.details}
    )


@app.exception_handler(OrderStateError)
async def order_state_handler(request: Request, exc: OrderStateError):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"error": exc.message, "code": exc.code, "details": exc.details}
    )


@app.exception_handler(IdempotencyConflictError)
async def idempotency_conflict_handler(request: Request, exc: IdempotencyConflictError):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"error": exc.message, "code": exc.code, "details": exc.details}
    )


@app.exception_handler(InfeasibleOptimizationError)
async def infeasible_optimization_handler(request: Request, exc: InfeasibleOptimizationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": exc.message, "code": exc.code, "details": exc.details}
    )


@app.exception_handler(WarehouseUnavailableError)
async def warehouse_unavailable_handler(request: Request, exc: WarehouseUnavailableError):
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"error": exc.message, "code": exc.code, "details": exc.details}
    )


@app.exception_handler(WOMSException)
async def domain_exception_handler(request: Request, exc: WOMSException):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": exc.message, "code": exc.code, "details": exc.details}
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled server exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "An internal server error occurred.", "code": "INTERNAL_SERVER_ERROR"}
    )


# Include API v1 Router
app.include_router(api_router, prefix="/api/v1")

# Static frontend assets
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    async def serve_dashboard():
        index_path = os.path.join(static_dir, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"message": "Warehouse Order Management System API is running. Access /docs for Swagger UI."}
