# Warehouse Order Management System (WOMS)

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D.svg)](https://redis.io/)
[![Google OR-Tools](https://img.shields.io/badge/Google%20OR--Tools-MIP-4285F4.svg)](https://developers.google.com/optimization)
[![Tests](https://img.shields.io/badge/Tests-35%20Passing-brightgreen.svg)]()

A high-performance, fault-tolerant **Warehouse Order Management System** designed to orchestrate multi-warehouse inventory allocation, prevent overselling under high concurrency, ensure request idempotency, and minimize fulfillment costs using **Google OR-Tools Mixed-Integer Linear Programming (MIP)**.

---

## Architecture Overview

```
+---------------------------------------------------------------------------------------+
|                                    Client Layer                                       |
|               (Web Dashboard / REST API Clients / Locust Load Generators)             |
+------------------------------------------+--------------------------------------------+
                                           | HTTP / REST (OpenAPI 3.1)
                                           v
+---------------------------------------------------------------------------------------+
|                                  FastAPI Web Layer                                    |
|   - Request Validation (Pydantic v2)        - Idempotency & Duplicate Request Guard   |
|   - Structured Error Responses             - Bounded Timeout Middleware & CORS       |
|   - API Versioning (/api/v1)               - Prometheus/Structured Observability      |
+------------------------------------------+--------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
|                                 Service / Domain Layer                                |
|   - ProductService                          - OrderFulfillmentOrchestrator            |
|   - InventoryService (Atomic Reservations) - HealthCheck & Circuit Breaker Manager    |
|   - RoutingStrategyEngine (Rule-based vs Linear Programming Optimizer)                |
+---------------------+--------------------+--------------------+-----------------------+
                      |                    |                    |
                      v                    v                    v
+-----------------------------+  +-------------------+  +-------------------------------+
|  OR-Tools Linear Optimizer  |  | Multi-Warehouse   |  | Retry & Resilience Engine     |
|  - Continuous relaxation    |  | Routing Strategy  |  | - Exp. Backoff + Jitter       |
|  - Mixed-Integer Prog (MIP) |  | - Nearest/Priority|  | - Transient Error Classifier  |
|  - Cost: Shipping + Handling|  | - Split fulfillment| | - Safe Reservation Rollbacks  |
+-----------------------------+  +-------------------+  +-------------------------------+
                      |                    |                    |
                      +--------------------+--------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
|                              Data & Coordination Layer                                |
|  +--------------------------------------------+  +---------------------------------+  |
|  | PostgreSQL (Authoritative Source of Truth) |  | Redis (Distributed Caching &    |  |
|  | - Normalized 3NF Relational Tables         |  |        Idempotency Lock Store)  |  |
|  | - Row-Level Locking (`FOR UPDATE`)         |  | - Read-through Product/Stock    |  |
|  | - Composite & Partial B-Tree Indexes       |  | - Lock lease & Idempotency Key  |  |
|  | - Strict ACID Inventory Movement Log       |  | - Explicit Invalidation         |  |
|  +--------------------------------------------+  +---------------------------------+  |
+---------------------------------------------------------------------------------------+
```

---

## Key Design Decisions & Architectural Answers

### 1. Why Each Major Design Decision Was Made
- **Relational PostgreSQL as Authoritative Truth:** Financial commitments and inventory stocks require strict ACID transactions. No distributed memory store (e.g. Redis alone) should ever be the sole authoritative source of physical inventory.
- **Ordered Row-Level Locking (`SELECT FOR UPDATE`):** When concurrent orders arrive competing for the same products across warehouses, deadlocks are eliminated entirely by sorting inventory row acquisitions deterministically by `(warehouse_id, product_id) ASC`.
- **Decoupled Routing Strategies:** The routing engine is isolated into a strategy pattern (`BaseRoutingStrategy`), allowing side-by-side unit testing and benchmarking of **Google OR-Tools MIP** versus **Greedy Nearest Baseline** without touching database or HTTP layers.
- **Dual Compatibility Layer (PostgreSQL / SQLite):** Full production configuration targets PostgreSQL with asyncpg connection pooling, while local developer and test environments automatically run on `aiosqlite` and `fakeredis` without requiring external daemon setup.

### 2. How Inventory Consistency is Maintained
1. **Available Stock vs Reserved Stock:**
   Each inventory record maintains:
   $$\text{Available Stock} = \text{On-Hand Stock} - \text{Reserved Stock}$$
   In database models: `quantity_available = quantity_on_hand - quantity_reserved`
2. **Database Check Constraints:**
   - `quantity_on_hand >= 0`
   - `quantity_reserved >= 0`
   - `quantity_on_hand >= quantity_reserved`
3. **Immutable Audit Ledger (`inventory_movements`):**
   Every balance adjustment, reservation creation, reservation release, and shipment deduction is written to an append-only ledger tracking `balance_on_hand_after` and `balance_reserved_after`.

### 3. How Idempotency and Retries Work
- Clients send an optional or required `X-Idempotency-Key` header with mutation requests (e.g. `POST /api/v1/orders`).
- **Phase A (Cache/DB Check):** If the key is already completed in Redis or committed in PostgreSQL, the cached serialized response is immediately returned (HTTP 200/201), completely bypassing order recreation and stock reservation.
- **Phase B (In-Flight Lock):** If another identical request is currently processing, an `IdempotencyConflictError` (HTTP 409) is returned.
- **Phase C (Bounded Retries):** Retries for transient failures (e.g. database lock acquisition timeout, network blip) execute bounded retries with exponential backoff and jitter:
  $$\text{Delay} = \min(\text{MaxDelay}, \text{BaseDelay} \cdot 2^{\text{attempt}-1}) \cdot (0.5 + \text{random}())$$
  Permanent business errors (e.g. `InsufficientInventoryError`, validation failure) fail fast and are never retried.

### 4. Mathematical Formulation of Linear Programming Optimization (Google OR-Tools)

#### Indices & Parameters:
- $w \in W$: Set of eligible, active warehouses ($|W| \ge 3$)
- $p \in P$: Set of items requested in customer order
- $D_p$: Customer demand for product $p$
- $S_{w,p}$: Available stock of product $p$ at warehouse $w$
- $C_w$: Remaining daily throughput capacity at warehouse $w$
- $\text{Dist}_w$: Haversine distance in km from warehouse $w$ to customer coordinates
- $\text{Cost}_w^{\text{unit}} = \text{BaseCost}_w + (\text{Dist}_w \cdot \text{CostPerKm}_w) + \text{HandlingCost}_w$
- $F_w$: Fixed dispatch cost incurred if warehouse $w$ is utilized in the order

#### Decision Variables:
- $x_{w,p} \in \mathbb{Z}_{\ge 0}$: Discrete integer units of product $p$ fulfilled from warehouse $w$.
- $y_w \in \{0, 1\}$: Binary variable indicating if warehouse $w$ is activated ($y_w = 1$ if $\sum_p x_{w,p} > 0$).

#### Objective Function:
$$\min \sum_{w \in W} \sum_{p \in P} \text{Cost}_w^{\text{unit}} \cdot x_{w,p} + \sum_{w \in W} F_w \cdot y_w$$

#### Constraints:
1. **Demand Exact Satisfaction:**
   $$\sum_{w \in W} x_{w,p} = D_p \quad \forall p \in P$$
2. **Stock Availability Ceiling:**
   $$x_{w,p} \le S_{w,p} \quad \forall w \in W, \forall p \in P$$
3. **Warehouse Daily Capacity Ceiling:**
   $$\sum_{p \in P} x_{w,p} \le C_w \quad \forall w \in W$$
4. **Activation Linking Constraint:**
   $$\sum_{p \in P} x_{w,p} \le \left( \sum_{p \in P} D_p \right) \cdot y_w \quad \forall w \in W$$
5. **Maximum Split Warehouses Allowed:**
   $$\sum_{w \in W} y_w \le K_{\text{max}} \quad (\text{default: } 3)$$

---

## Benchmark Results (Measured Data)

### 1. Routing Optimization Benchmark (OR-Tools vs Baseline Greedy)
Measured across identical customer orders and warehouse topologies:

| Metric | Baseline Greedy (Nearest First) | Google OR-Tools MIP Optimizer | Difference / Improvement |
|---|---|---|---|
| **Feasible Orders Satisfied** | 100 / 100 (100%) | 100 / 100 (100%) | Identical Constraint Satisfaction |
| **Total Fulfillment Cost** | **\$50,719.67** | **\$49,597.41** | **-\$1,122.26 (2.21% Cost Reduction)** |
| **Average Solve Latency** | 0.03 ms / order | 7.90 ms / order | Exact global cost minimum |

### 2. Database Query Plan & Indexing Benchmark
Measured via `EXPLAIN QUERY PLAN` over 500 iterations:
- **Product-to-Warehouse Stock Availability Lookup:**
  - Query: Join `inventories` and `warehouses` filtering active status and available stock.
  - Mean Execution Latency: **0.699 ms**
  - Index Benefit: `ix_inventory_warehouse_stock` replaces $O(N)$ full table scan with $O(\log N)$ B-tree index scan.
- **Order Status & Date Query:**
  - Query: Filter by `status = 'RESERVED'` ordered by `created_at DESC` limit 50.
  - Mean Execution Latency: **0.638 ms**
  - Index Benefit: Composite index `ix_orders_status_created` eliminates in-memory sorting.

### 3. Concurrency & Overselling Guarantee
Under 10 concurrent requests competing for 10 units of stock (demanding 30 units total):
- Exactly **3 orders succeeded** (9 units reserved).
- **7 orders safely rejected** with HTTP 422 (`Insufficient inventory`).
- Available stock balance remained non-negative ($1$ unit left). Zero overselling occurred.

---

## Project Structure

```
Warehouse-Order-Management-System/
├── .env.example              # Environment variables template
├── .gitignore                # Git ignore configuration
├── Dockerfile                # Multi-stage Docker container build
├── docker-compose.yml        # PostgreSQL 16, Redis 7, and FastAPI orchestration
├── requirements.txt          # Python 3.12+ pinned dependencies
├── app/
│   ├── main.py               # FastAPI entrypoint, lifespan, CORS, error mappers
│   ├── config.py             # Pydantic Settings configuration
│   ├── core/
│   │   ├── database.py       # Async SQLAlchemy session and engine factory
│   │   ├── redis.py          # Redis client with FakeRedis fallback
│   │   ├── exceptions.py     # Domain exceptions hierarchy
│   │   ├── logging.py        # Structured JSON logging
│   │   └── retry.py          # Exponential backoff + jitter retry decorator
│   ├── models/               # SQLAlchemy 2.0 ORM models
│   ├── schemas/              # Pydantic v2 schemas
│   ├── repositories/         # Database persistence repositories
│   ├── services/             # Business domain orchestration services
│   ├── routing/              # Haversine spatial math, Greedy, and OR-Tools LP
│   └── static/               # Frontend Dashboard (HTML5, CSS3, Vanilla JS)
├── benchmarks/
│   ├── seed_data.py          # Seed generator for products, warehouses, stock
│   ├── query_benchmark.py    # Database query plan and index performance
│   ├── routing_comparison.py # Comparative LP vs Greedy benchmark
│   └── locustfile.py         # Locust high-concurrency load testing
└── tests/                    # Pytest 35+ automated test suite
    ├── conftest.py
    ├── test_products_warehouses.py
    ├── test_inventory.py
    ├── test_orders.py
    ├── test_concurrency.py
    ├── test_idempotency.py
    ├── test_fault_tolerance.py
    ├── test_routing_and_lp.py
    └── test_api_endpoints.py
```

---

## Quickstart & Setup Instructions

### 1. Local Setup with Virtual Environment
```bash
# Clone the repository
git clone https://github.com/harsharaju1314-hash/Warehouse-Order-Management-System.git
cd Warehouse-Order-Management-System

# Create and activate Python 3.12 venv
python -m venv .venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Run database seed
python benchmarks/seed_data.py

# Launch FastAPI server
uvicorn app.main:app --reload --port 8000
```
- Interactive API Documentation: [http://localhost:8000/docs](http://localhost:8000/docs)
- Web Dashboard: [http://localhost:8000/](http://localhost:8000/)

### 2. Docker Compose Deployment
```bash
# Start PostgreSQL, Redis, and WOMS API
docker-compose up -d --build

# Inspect running services
docker-compose ps

# View service logs
docker-compose logs -f api
```

### 3. Running Automated Tests
```bash
pytest -v
```

### 4. Running Benchmarks
```bash
# Routing LP vs Greedy Cost Benchmark
python benchmarks/routing_comparison.py

# Database Query Plan & Indexing Benchmark
python benchmarks/query_benchmark.py

# Locust Load Testing
locust -f benchmarks/locustfile.py --host=http://localhost:8000
```

---

## REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/health` | Inspect PostgreSQL, Redis, and active warehouse nodes |
| `GET` | `/api/v1/health/warehouses` | Detailed capacity, load, and health of each warehouse |
| `POST` | `/api/v1/products` | Create a new product |
| `GET` | `/api/v1/products` | List products with pagination and filters |
| `PATCH` | `/api/v1/products/{id}` | Update product details or active status |
| `POST` | `/api/v1/warehouses` | Register a new warehouse facility |
| `GET` | `/api/v1/warehouses` | List warehouses with coordinates and capacity |
| `PATCH` | `/api/v1/warehouses/{id}` | Update warehouse capacity or status (`ACTIVE`/`OFFLINE`) |
| `GET` | `/api/v1/inventory` | Matrix overview of stock balances across warehouses |
| `POST` | `/api/v1/inventory/adjustments` | Atomic stock adjustment with audit ledger movement |
| `GET` | `/api/v1/inventory/movements` | Query immutable audit ledger of balance changes |
| `POST` | `/api/v1/orders` | Create and route order via LP optimization (Idempotent) |
| `GET` | `/api/v1/orders/{id}` | Retrieve order details and warehouse allocation splits |
| `POST` | `/api/v1/orders/{id}/fulfill` | Confirm order shipment and deduct physical inventory |
| `POST` | `/api/v1/orders/{id}/cancel` | Cancel order and safely release reserved inventory |

---

## What Happens When a Warehouse Becomes Unavailable

1. **Simulation:** Any warehouse can be taken offline via `PATCH /api/v1/warehouses/{id}` with `status: "OFFLINE"`.
2. **Failover Routing:** When an order is placed, only warehouses with `status == "ACTIVE"` and remaining daily throughput capacity are submitted as candidates to the routing solver.
3. **No Crashes / No Overselling:** If the offline warehouse held needed inventory, the system either:
   - Routes to other active warehouses holding sufficient stock.
   - Splits fulfillment among remaining active nodes.
   - Rejects the order gracefully with HTTP 422 if remaining active inventory is insufficient, ensuring no overselling or corrupted reservations occur.

---

## Current Limitations & Future Work
- **Multi-region Redis Replication:** Current Redis deployment operates as a single coordinating instance. In production, Redis Sentinel or Redis Cluster with read replicas would provide distributed failover.
- **Dynamic Real-Time Carrier Rates:** Shipping calculations currently use Haversine great-circle distance. Integration with carrier APIs (FedEx, UPS, DHL) could feed real-time parcel rates into the objective function.
- **Batched Vehicle Routing (VRP):** While orders are optimized on arrival, multi-order batching with vehicle routing constraints could further reduce last-mile logistics costs.
