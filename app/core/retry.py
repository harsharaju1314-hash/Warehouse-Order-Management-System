"""Retry utility with exponential backoff, jitter, and transient failure classification."""
import asyncio
import functools
import random
from typing import Callable, Any, Tuple, Type
from app.config import settings
from app.core.exceptions import (
    TransientServiceError,
    DatabaseLockTimeoutError,
    WarehouseUnavailableError,
    WOMSException
)
from app.core.logging import logger

# Exceptions that are considered transient and safe to retry
DEFAULT_RETRYABLE_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    TransientServiceError,
    DatabaseLockTimeoutError,
    WarehouseUnavailableError,
    ConnectionError,
    TimeoutError,
)


def is_retryable_exception(exc: Exception) -> bool:
    """Classify whether an exception is transient or permanent."""
    if isinstance(exc, DEFAULT_RETRYABLE_EXCEPTIONS):
        return True
    
    # Check for DB deadlock / lock timeout strings in driver errors
    msg = str(exc).lower()
    if "deadlock detected" in msg or "could not obtain lock" in msg or "database is locked" in msg:
        return True
        
    return False


def with_retry(
    max_retries: int = settings.MAX_RETRIES,
    base_delay: float = settings.RETRY_BASE_DELAY,
    max_delay: float = settings.RETRY_MAX_DELAY,
    jitter: bool = settings.RETRY_JITTER,
    retryable_exceptions: Tuple[Type[Exception], ...] = DEFAULT_RETRYABLE_EXCEPTIONS
):
    """Decorator for async functions to automatically retry on transient failures."""
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            attempt = 0
            while True:
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:
                    attempt += 1
                    
                    # If not retryable or max attempts reached, fail immediately
                    if not is_retryable_exception(exc) or attempt > max_retries:
                        if attempt > max_retries:
                            logger.error(
                                f"Retry exhausted for {func.__name__} after {max_retries} attempts. Last error: {exc}"
                            )
                        raise exc

                    # Calculate exponential backoff delay
                    delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
                    if jitter:
                        delay = delay * (0.5 + random.random())

                    logger.warning(
                        f"Transient failure in {func.__name__} (attempt {attempt}/{max_retries}): {exc}. "
                        f"Retrying in {delay:.3f}s..."
                    )
                    await asyncio.sleep(delay)
        return wrapper
    return decorator
