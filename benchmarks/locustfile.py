"""Locust load testing scenario simulating high-concurrency order submissions and queries."""
import random
import uuid
from locust import HttpUser, task, between


class WarehouseSystemUser(HttpUser):
    wait_time = between(0.1, 0.5)

    def on_start(self):
        """Fetch active products to populate order payloads."""
        self.product_ids = []
        try:
            res = self.client.get("/api/v1/products?size=20")
            if res.status_code == 200:
                data = res.json()
                self.product_ids = [p["id"] for p in data.get("items", [])]
        except Exception:
            pass

    @task(5)
    def query_inventory_overview(self):
        """Read-heavy stock queries."""
        self.client.get("/api/v1/inventory", name="/api/v1/inventory")

    @task(3)
    def query_warehouses_health(self):
        """Health check polling."""
        self.client.get("/api/v1/health", name="/api/v1/health")

    @task(4)
    def submit_optimized_order(self):
        """Submit order routed via Google OR-Tools Linear Optimizer."""
        if not self.product_ids:
            return

        product_id = random.choice(self.product_ids)
        idempotency_key = f"locust_{uuid.uuid4().hex}"
        
        payload = {
            "customer_id": f"LOAD-CUST-{random.randint(100, 999)}",
            "destination_lat": round(random.uniform(30.0, 45.0), 4),
            "destination_lon": round(random.uniform(-120.0, -75.0), 4),
            "routing_strategy": "OR_TOOLS_LP",
            "items": [
                {
                    "product_id": product_id,
                    "requested_quantity": random.randint(1, 5)
                }
            ]
        }

        self.client.post(
            "/api/v1/orders",
            json=payload,
            headers={"X-Idempotency-Key": idempotency_key},
            name="/api/v1/orders [OR_TOOLS_LP]"
        )

    @task(1)
    def list_orders(self):
        """Poll order tracking list."""
        self.client.get("/api/v1/orders?size=10", name="/api/v1/orders [List]")
