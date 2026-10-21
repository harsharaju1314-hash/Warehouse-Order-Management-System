"""Common schemas for pagination, response wrappers, and errors."""
from typing import Generic, TypeVar, List, Optional, Any
from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorResponse(BaseModel):
    error: str
    code: str
    details: Optional[dict[str, Any]] = None


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    size: int
    pages: int


class MessageResponse(BaseModel):
    message: str
    success: bool = True
