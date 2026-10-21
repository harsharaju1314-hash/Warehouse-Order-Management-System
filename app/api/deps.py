"""API dependencies for FastAPI routes."""
from typing import Optional, AsyncGenerator
from fastapi import Header, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db


def get_idempotency_key(
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key")
) -> Optional[str]:
    """Extract idempotency key from HTTP header."""
    return x_idempotency_key
