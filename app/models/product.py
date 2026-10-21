"""Product ORM model."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Numeric, Boolean, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sku: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=True)
    price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    weight_kg: Mapped[float] = mapped_column(Numeric(8, 3), default=1.000, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    inventories = relationship("Inventory", back_populates="product", cascade="all, delete-orphan")
    order_items = relationship("OrderItem", back_populates="product")
    movements = relationship("InventoryMovement", back_populates="product")

    __table_args__ = (
        Index("ix_products_sku_active", "sku", "is_active"),
    )
