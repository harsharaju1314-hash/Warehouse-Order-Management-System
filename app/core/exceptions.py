"""Domain exception hierarchy for Warehouse Order Management System."""
from typing import Optional, Dict, Any


class WOMSException(Exception):
    """Base exception for all domain errors."""
    def __init__(self, message: str, code: str = "INTERNAL_ERROR", details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


# --- Permanent Business / Validation Exceptions (HTTP 4xx, non-retryable) ---

class ResourceNotFoundError(WOMSException):
    """Raised when an entity (product, warehouse, order, etc.) does not exist."""
    def __init__(self, resource: str, identifier: Any):
        super().__init__(
            message=f"{resource} with identifier '{identifier}' not found.",
            code="RESOURCE_NOT_FOUND",
            details={"resource": resource, "identifier": str(identifier)}
        )


class InsufficientInventoryError(WOMSException):
    """Raised when requested product quantities cannot be fulfilled across active warehouses."""
    def __init__(self, product_id: str, requested: int, available: int):
        super().__init__(
            message=f"Insufficient inventory for product {product_id}. Requested: {requested}, Available: {available}",
            code="INSUFFICIENT_INVENTORY",
            details={"product_id": product_id, "requested": requested, "available": available}
        )


class OrderStateError(WOMSException):
    """Raised when an illegal order status transition is attempted."""
    def __init__(self, order_id: str, current_status: str, attempted_action: str):
        super().__init__(
            message=f"Order {order_id} in status '{current_status}' cannot perform '{attempted_action}'.",
            code="INVALID_ORDER_STATE",
            details={"order_id": order_id, "current_status": current_status, "action": attempted_action}
        )


class IdempotencyConflictError(WOMSException):
    """Raised when a concurrent request with the same idempotency key is already running."""
    def __init__(self, idempotency_key: str):
        super().__init__(
            message=f"A request with idempotency key '{idempotency_key}' is currently being processed.",
            code="IDEMPOTENCY_CONFLICT",
            details={"idempotency_key": idempotency_key}
        )


class InfeasibleOptimizationError(WOMSException):
    """Raised when OR-Tools or routing engine cannot find a feasible allocation satisfying all constraints."""
    def __init__(self, reason: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Allocation optimization infeasible: {reason}",
            code="INFEASIBLE_OPTIMIZATION",
            details=details or {}
        )


# --- Transient / Retryable Exceptions (HTTP 503 / 500, retryable) ---

class TransientServiceError(WOMSException):
    """Base class for transient, retryable failures."""
    def __init__(self, message: str, code: str = "TRANSIENT_ERROR", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, code=code, details=details)


class DatabaseLockTimeoutError(TransientServiceError):
    """Raised when row locking (SELECT FOR UPDATE) times out under extreme concurrency."""
    def __init__(self, message: str = "Database row lock acquisition timed out"):
        super().__init__(message=message, code="LOCK_TIMEOUT")


class WarehouseUnavailableError(TransientServiceError):
    """Raised when a warehouse node fails a health check or circuit breaker is OPEN."""
    def __init__(self, warehouse_id: str, reason: str = "Warehouse offline or unhealthy"):
        super().__init__(
            message=f"Warehouse {warehouse_id} is unavailable: {reason}",
            code="WAREHOUSE_UNAVAILABLE",
            details={"warehouse_id": warehouse_id, "reason": reason}
        )
