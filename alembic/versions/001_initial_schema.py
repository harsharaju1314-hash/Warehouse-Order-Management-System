"""initial schema migration

Revision ID: 001_initial
Revises: 
Create Date: 2026-10-21 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Warehouses table
    op.create_table(
        "warehouses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(32), unique=True, nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("address", sa.String(255), nullable=True),
        sa.Column("city", sa.String(64), nullable=True),
        sa.Column("state", sa.String(32), nullable=True),
        sa.Column("postal_code", sa.String(16), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("capacity_limit", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column("current_daily_load", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("shipping_base_cost", sa.Numeric(10, 2), nullable=False, server_default="5.00"),
        sa.Column("shipping_cost_per_km", sa.Numeric(10, 4), nullable=False, server_default="0.05"),
        sa.Column("processing_cost_per_unit", sa.Numeric(10, 2), nullable=False, server_default="1.50"),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_warehouses_code", "warehouses", ["code"])
    op.create_index("ix_warehouses_status_capacity", "warehouses", ["status", "capacity_limit"])

    # 2. Products table
    op.create_table(
        "products",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("sku", sa.String(64), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("weight_kg", sa.Numeric(8, 3), nullable=False, server_default="1.000"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_products_sku", "products", ["sku"])
    op.create_index("ix_products_sku_active", "products", ["sku", "is_active"])

    # 3. Inventories table
    op.create_table(
        "inventories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("warehouse_id", sa.String(36), sa.ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("quantity_on_hand", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quantity_reserved", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("warehouse_id", "product_id", name="uq_inventory_warehouse_product"),
        sa.CheckConstraint("quantity_on_hand >= 0", name="chk_inventory_on_hand_non_negative"),
        sa.CheckConstraint("quantity_reserved >= 0", name="chk_inventory_reserved_non_negative"),
        sa.CheckConstraint("quantity_on_hand >= quantity_reserved", name="chk_inventory_on_hand_gte_reserved"),
    )
    op.create_index("ix_inventory_product_warehouse", "inventories", ["product_id", "warehouse_id"])
    op.create_index("ix_inventory_warehouse_stock", "inventories", ["warehouse_id", "quantity_on_hand", "quantity_reserved"])

    # 4. Orders table
    op.create_table(
        "orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("idempotency_key", sa.String(128), unique=True, nullable=True),
        sa.Column("customer_id", sa.String(64), nullable=False),
        sa.Column("destination_lat", sa.Float(), nullable=False),
        sa.Column("destination_lon", sa.Float(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("total_item_price", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("total_fulfillment_cost", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("routing_strategy_used", sa.String(32), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_orders_idempotency", "orders", ["idempotency_key"])
    op.create_index("ix_orders_status_created", "orders", ["status", "created_at"])
    op.create_index("ix_orders_customer_status", "orders", ["customer_id", "status"])

    # 5. Order Items table
    op.create_table(
        "order_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("requested_quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("order_id", "product_id", name="uq_order_product"),
        sa.CheckConstraint("requested_quantity > 0", name="chk_order_item_qty_positive"),
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])

    # 6. Allocations table
    op.create_table(
        "allocations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_item_id", sa.String(36), sa.ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("warehouse_id", sa.String(36), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("allocated_quantity", sa.Integer(), nullable=False),
        sa.Column("estimated_shipping_cost", sa.Numeric(10, 2), nullable=False, server_default="0.00"),
        sa.Column("estimated_handling_cost", sa.Numeric(10, 2), nullable=False, server_default="0.00"),
        sa.Column("status", sa.String(32), nullable=False, server_default="RESERVED"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("allocated_quantity > 0", name="chk_allocated_qty_positive"),
    )
    op.create_index("ix_allocations_order_warehouse", "allocations", ["order_id", "warehouse_id"])
    op.create_index("ix_allocations_warehouse_status", "allocations", ["warehouse_id", "status"])

    # 7. Inventory Movements table
    op.create_table(
        "inventory_movements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("inventory_id", sa.String(36), sa.ForeignKey("inventories.id"), nullable=False),
        sa.Column("warehouse_id", sa.String(36), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("change_type", sa.String(32), nullable=False),
        sa.Column("quantity_delta", sa.Integer(), nullable=False),
        sa.Column("balance_on_hand_after", sa.Integer(), nullable=False),
        sa.Column("balance_reserved_after", sa.Integer(), nullable=False),
        sa.Column("reference_order_id", sa.String(36), nullable=True),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_movements_warehouse_product_created", "inventory_movements", ["warehouse_id", "product_id", "created_at"])


def downgrade() -> None:
    op.drop_table("inventory_movements")
    op.drop_table("allocations")
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("inventories")
    op.drop_table("products")
    op.drop_table("warehouses")
