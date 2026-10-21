"""Allocation ORM model tracking warehouse-to-order item fulfillment."""
import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import (
    String, Integer, Numeric, DateTime, Enum, ForeignKey, CheckConstraint, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class AllocationStatus(str, enum.Enum):
    RESERVED = "RESERVED"
    SHIPPED = "SHIPPED"
    RELEASED = "RELEASED"


class Allocation(Base):
    __tablename__ = "allocations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    order_item_id: Mapped[str] = mapped_column(String(36), ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False)
    warehouse_id: Mapped[str] = mapped_column(String(36), ForeignKey("warehouses.id"), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"), nullable=False, index=True)

    allocated_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_shipping_cost: Mapped[float] = mapped_column(Numeric(10, 2), default=0.00, nullable=False)
    estimated_handling_cost: Mapped[float] = mapped_column(Numeric(10, 2), default=0.00, nullable=False)

    status: Mapped[AllocationStatus] = mapped_column(
        Enum(AllocationStatus),
        default=AllocationStatus.RESERVED,
        nullable=False,
        index=True
    )

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
    order = relationship("Order", back_populates="allocations")
    order_item = relationship("OrderItem", back_populates="allocations")
    warehouse = relationship("Warehouse", back_populates="allocations")
    product = relationship("Product")

    __table_args__ = (
        CheckConstraint("allocated_quantity > 0", name="chk_allocated_qty_positive"),
        Index("ix_allocations_order_warehouse", "order_id", "warehouse_id"),
        Index("ix_allocations_warehouse_status", "warehouse_id", "status"),
    )
