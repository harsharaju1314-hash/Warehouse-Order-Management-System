"""Database engine, session management, and base models."""
import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
    AsyncEngine
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event
from app.config import settings
from app.core.logging import logger


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


def get_engine() -> AsyncEngine:
    db_url = settings.effective_async_db_url
    connect_args = {}
    
    if "sqlite" in db_url:
        connect_args["check_same_thread"] = False
        engine = create_async_engine(
            db_url,
            echo=False,
            future=True,
            connect_args=connect_args
        )
        
        # Enforce foreign key constraints in SQLite
        @event.listens_for(engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
            
        return engine
    else:
        # PostgreSQL with asyncpg connection pooling
        return create_async_engine(
            db_url,
            echo=False,
            future=True,
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=300
        )


engine: AsyncEngine = get_engine()
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for obtaining an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables."""
    # Import all models so metadata is populated
    import app.models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized successfully.")
