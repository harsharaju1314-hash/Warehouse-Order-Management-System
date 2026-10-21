"""Inventory ORM model with stock balances and reservation counters."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, ForeignKey, UniqueConstraint, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Inventory(Base):
    __tablename__ = "inventories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    warehouse_id: Mapped[str] = mapped_column(String(36), ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)

    quantity_on_hand: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quantity_reserved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    warehouse = relationship("Warehouse", back_populates="inventories")
    product = relationship("Product", back_populates="inventories")
    movements = relationship("InventoryMovement", back_populates="inventory")

    @property
    def quantity_available(self) -> int:
        """Available stock ready for new orders (on-hand minus reserved)."""
        return max(0, self.quantity_on_hand - self.quantity_reserved)

    __table_args__ = (
        UniqueConstraint("warehouse_id", "product_id", name="uq_inventory_warehouse_product"),
        CheckConstraint("quantity_on_hand >= 0", name="chk_inventory_on_hand_non_negative"),
        CheckConstraint("quantity_reserved >= 0", name="chk_inventory_reserved_non_negative"),
        CheckConstraint("quantity_on_hand >= quantity_reserved", name="chk_inventory_on_hand_gte_reserved"),
        Index("ix_inventory_product_warehouse", "product_id", "warehouse_id"),
        Index("ix_inventory_warehouse_stock", "warehouse_id", "quantity_on_hand", "quantity_reserved"),
    )
