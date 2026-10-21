"""Pytest fixtures and test environment setup."""
import os
import pytest
import pytest_asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Configure environment for testing before importing app modules
os.environ["USE_SQLITE"] = "true"
os.environ["SQLITE_DB_PATH"] = "./test_warehouse.db"
os.environ["USE_FAKE_REDIS"] = "true"

from app.config import settings
settings.USE_SQLITE = True
settings.SQLITE_DB_PATH = "./test_warehouse.db"
settings.USE_FAKE_REDIS = True

from app.core.database import Base, get_db
from app.core.redis import redis_client
from app.main import app


test_engine = create_async_engine(
    "sqlite+aiosqlite:///./test_warehouse.db",
    connect_args={"check_same_thread": False},
    echo=False
)

TestAsyncSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestAsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_database():
    """Create test tables at start of test session and clean up after."""
    await redis_client.connect()
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await redis_client.close()
    await test_engine.dispose()
    if os.path.exists("./test_warehouse.db"):
        try:
            os.remove("./test_warehouse.db")
        except OSError:
            pass


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestAsyncSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
