"""Seed data generator for products, warehouses, and inventory."""
import asyncio
import random
from app.core.database import AsyncSessionLocal, init_db
from app.models.product import Product
from app.models.warehouse import Warehouse, WarehouseStatus
from app.models.inventory import Inventory
from app.models.movement import InventoryMovement, MovementType
from app.core.logging import logger


WAREHOUSE_SEEDS = [
    {
        "code": "WH-US-EAST-01",
        "name": "New York Distribution Center",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "capacity_limit": 5000,
        "shipping_base_cost": 5.00,
        "shipping_cost_per_km": 0.04,
        "processing_cost_per_unit": 1.20,
        "status": WarehouseStatus.ACTIVE
    },
    {
        "code": "WH-US-WEST-01",
        "name": "San Francisco Fulfillment Center",
        "latitude": 37.7749,
        "longitude": -122.4194,
        "capacity_limit": 6000,
        "shipping_base_cost": 4.50,
        "shipping_cost_per_km": 0.035,
        "processing_cost_per_unit": 1.50,
        "status": WarehouseStatus.ACTIVE
    },
    {
        "code": "WH-US-CENTRAL-01",
        "name": "Chicago Logistics Hub",
        "latitude": 41.8781,
        "longitude": -87.6298,
        "capacity_limit": 8000,
        "shipping_base_cost": 3.80,
        "shipping_cost_per_km": 0.03,
        "processing_cost_per_unit": 1.10,
        "status": WarehouseStatus.ACTIVE
    },
    {
        "code": "WH-US-SOUTH-01",
        "name": "Dallas Fast-Ship Facility",
        "latitude": 32.7767,
        "longitude": -96.7970,
        "capacity_limit": 4500,
        "shipping_base_cost": 4.00,
        "shipping_cost_per_km": 0.032,
        "processing_cost_per_unit": 1.15,
        "status": WarehouseStatus.ACTIVE
    }
]

PRODUCT_SEEDS = [
    {"sku": "SKU-ELEC-001", "name": "Ultra-Wide Gaming Monitor 34\"", "price": 499.99, "weight_kg": 7.2},
    {"sku": "SKU-ELEC-002", "name": "Wireless Ergonomic Mouse", "price": 49.99, "weight_kg": 0.25},
    {"sku": "SKU-ELEC-003", "name": "Mechanical RGB Keyboard", "price": 119.99, "weight_kg": 1.1},
    {"sku": "SKU-ELEC-004", "name": "Noise Cancelling Headphones", "price": 249.99, "weight_kg": 0.35},
    {"sku": "SKU-ELEC-005", "name": "USB-C Multiport Docking Station", "price": 89.99, "weight_kg": 0.45},
    {"sku": "SKU-OFF-001", "name": "Standing Desk Converter", "price": 179.99, "weight_kg": 14.5},
    {"sku": "SKU-OFF-002", "name": "Ergonomic Mesh Office Chair", "price": 299.99, "weight_kg": 18.0},
    {"sku": "SKU-OFF-003", "name": "LED Monitor Light Bar", "price": 39.99, "weight_kg": 0.5},
    {"sku": "SKU-NET-001", "name": "Wi-Fi 7 Mesh Router System", "price": 349.99, "weight_kg": 1.8},
    {"sku": "SKU-NET-002", "name": "Cat 8 Ethernet Cable 10m", "price": 19.99, "weight_kg": 0.3},
]


async def seed_database():
    """Seeds database with default products, warehouses, and realistic inventory."""
    import uuid
    from datetime import datetime, timezone

    logger.info("Starting database seeding...")
    await init_db()

    async with AsyncSessionLocal() as session:
        # 1. Seed Warehouses
        created_warehouses = []
        for wh_data in WAREHOUSE_SEEDS:
            wh = Warehouse(
                id=str(uuid.uuid4()),
                code=wh_data["code"],
                name=wh_data["name"],
                latitude=wh_data["latitude"],
                longitude=wh_data["longitude"],
                capacity_limit=wh_data["capacity_limit"],
                shipping_base_cost=wh_data["shipping_base_cost"],
                shipping_cost_per_km=wh_data["shipping_cost_per_km"],
                processing_cost_per_unit=wh_data["processing_cost_per_unit"],
                status=wh_data["status"]
            )
            session.add(wh)
            created_warehouses.append(wh)

        # 2. Seed Products
        created_products = []
        for prod_data in PRODUCT_SEEDS:
            prod = Product(
                id=str(uuid.uuid4()),
                sku=prod_data["sku"],
                name=prod_data["name"],
                price=prod_data["price"],
                weight_kg=prod_data["weight_kg"],
                is_active=True
            )
            session.add(prod)
            created_products.append(prod)

        await session.flush()

        # 3. Seed Inventory & Movements across warehouses
        for wh in created_warehouses:
            for prod in created_products:
                qty = random.randint(250, 1500)
                inv = Inventory(
                    id=str(uuid.uuid4()),
                    warehouse_id=wh.id,
                    product_id=prod.id,
                    quantity_on_hand=qty,
                    quantity_reserved=0,
                    version=1
                )
                session.add(inv)
                await session.flush()

                movement = InventoryMovement(
                    id=str(uuid.uuid4()),
                    inventory_id=inv.id,
                    warehouse_id=wh.id,
                    product_id=prod.id,
                    change_type=MovementType.RESTOCK,
                    quantity_delta=qty,
                    balance_on_hand_after=qty,
                    balance_reserved_after=0,
                    reason="Initial Warehouse Seed Supply"
                )
                session.add(movement)

        await session.commit()
        logger.info(
            f"Successfully seeded {len(created_warehouses)} warehouses, "
            f"{len(created_products)} products, and {len(created_warehouses) * len(created_products)} inventory lines."
        )


if __name__ == "__main__":
    asyncio.run(seed_database())
