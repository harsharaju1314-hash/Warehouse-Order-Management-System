"""Order and OrderItem ORM models."""
import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import (
    String, Integer, Float, Numeric, DateTime, Enum, ForeignKey,
    UniqueConstraint, CheckConstraint, Index, Text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    RESERVED = "RESERVED"
    PROCESSING = "PROCESSING"
    FULFILLED = "FULFILLED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=True, index=True)
    customer_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    
    # Destination coordinates for shipping cost calculation
    destination_lat: Mapped[float] = mapped_column(Float, nullable=False)
    destination_lon: Mapped[float] = mapped_column(Float, nullable=False)

    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus),
        default=OrderStatus.PENDING,
        nullable=False,
        index=True
    )

    total_item_price: Mapped[float] = mapped_column(Numeric(12, 2), default=0.00, nullable=False)
    total_fulfillment_cost: Mapped[float] = mapped_column(Numeric(12, 2), default=0.00, nullable=False)
    routing_strategy_used: Mapped[str] = mapped_column(String(32), default="OR_TOOLS_LP", nullable=True)
    failure_reason: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    allocations = relationship("Allocation", back_populates="order", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_orders_status_created", "status", "created_at"),
        Index("ix_orders_customer_status", "customer_id", "status"),
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"), nullable=False, index=True)
    requested_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")
    allocations = relationship("Allocation", back_populates="order_item", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("order_id", "product_id", name="uq_order_product"),
        CheckConstraint("requested_quantity > 0", name="chk_order_item_qty_positive"),
    )
