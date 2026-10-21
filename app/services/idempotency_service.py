"""Distributed idempotency coordinator using Redis and PostgreSQL."""
from typing import Optional, Dict, Any
from app.core.redis import redis_client
from app.core.exceptions import IdempotencyConflictError
from app.core.logging import logger


class IdempotencyService:
    def __init__(self):
        self.ttl_seconds = 86400  # 24 hour retention for completed operations

    async def check_or_lock(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Check if an idempotency key was previously processed.
        Returns cached response dict if already completed.
        Raises IdempotencyConflictError if currently in flight.
        Locks the key for processing if new.
        """
        redis_key = f"idempotency:{key}"
        cached = await redis_client.get_json(redis_key)
        
        if cached:
            status = cached.get("status")
            if status == "COMPLETED":
                logger.info(f"Idempotent hit for key '{key}'. Returning cached completed response.")
                return cached.get("response")
            elif status == "PROCESSING":
                raise IdempotencyConflictError(key)

        # Acquire processing lease (lease expires in 60s to prevent permanent deadlock on hard crash)
        acquired = await redis_client.set_json(
            redis_key,
            {"status": "PROCESSING"},
            ex=60
        )
        if not acquired:
            raise IdempotencyConflictError(key)

        return None

    async def mark_completed(self, key: str, response_payload: Dict[str, Any]) -> None:
        """Mark the idempotency key as completed with the serializable response."""
        redis_key = f"idempotency:{key}"
        await redis_client.set_json(
            redis_key,
            {
                "status": "COMPLETED",
                "response": response_payload
            },
            ex=self.ttl_seconds
        )
        logger.info(f"Marked idempotency key '{key}' as COMPLETED in Redis")

    async def release_on_failure(self, key: str) -> None:
        """Release processing lock on transient failure to allow subsequent retries."""
        redis_key = f"idempotency:{key}"
        await redis_client.delete(redis_key)
        logger.info(f"Released idempotency lock for key '{key}' after failure")
