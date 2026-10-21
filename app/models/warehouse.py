"""Warehouse ORM model."""
import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, Numeric, DateTime, Enum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class WarehouseStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    MAINTENANCE = "MAINTENANCE"
    OFFLINE = "OFFLINE"


class Warehouse(Base):
    __tablename__ = "warehouses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=True)
    city: Mapped[str] = mapped_column(String(64), nullable=True)
    state: Mapped[str] = mapped_column(String(32), nullable=True)
    postal_code: Mapped[str] = mapped_column(String(16), nullable=True)
    
    # Location coordinates for distance/shipping calculation
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)

    # Capacity constraints
    capacity_limit: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    current_daily_load: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Cost parameters
    shipping_base_cost: Mapped[float] = mapped_column(Numeric(10, 2), default=5.00, nullable=False)
    shipping_cost_per_km: Mapped[float] = mapped_column(Numeric(10, 4), default=0.05, nullable=False)
    processing_cost_per_unit: Mapped[float] = mapped_column(Numeric(10, 2), default=1.50, nullable=False)

    status: Mapped[WarehouseStatus] = mapped_column(
        Enum(WarehouseStatus),
        default=WarehouseStatus.ACTIVE,
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
    inventories = relationship("Inventory", back_populates="warehouse", cascade="all, delete-orphan")
    allocations = relationship("Allocation", back_populates="warehouse")
    movements = relationship("InventoryMovement", back_populates="warehouse")

    __table_args__ = (
        Index("ix_warehouses_status_capacity", "status", "capacity_limit"),
    )
