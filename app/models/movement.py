"""InventoryMovement audit ledger ORM model."""
import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, Enum, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class MovementType(str, enum.Enum):
    RESTOCK = "RESTOCK"
    ADJUSTMENT = "ADJUSTMENT"
    RESERVATION_CREATED = "RESERVATION_CREATED"
    RESERVATION_RELEASED = "RESERVATION_RELEASED"
    FULFILLMENT_DEDUCTED = "FULFILLMENT_DEDUCTED"


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    inventory_id: Mapped[str] = mapped_column(String(36), ForeignKey("inventories.id"), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), ForeignKey("warehouses.id"), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"), nullable=False, index=True)

    change_type: Mapped[MovementType] = mapped_column(Enum(MovementType), nullable=False, index=True)
    quantity_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_on_hand_after: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_reserved_after: Mapped[int] = mapped_column(Integer, nullable=False)

    reference_order_id: Mapped[str] = mapped_column(String(36), nullable=True, index=True)
    reason: Mapped[str] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )

    # Relationships
    inventory = relationship("Inventory", back_populates="movements")
    warehouse = relationship("Warehouse", back_populates="movements")
    product = relationship("Product", back_populates="movements")

    __table_args__ = (
        Index("ix_movements_warehouse_product_created", "warehouse_id", "product_id", "created_at"),
    )
