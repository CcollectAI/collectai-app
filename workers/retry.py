import asyncio
import logging
import time
from functools import wraps

logger = logging.getLogger(__name__)


def with_retry(max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0):
    """Decorator that retries a function with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    if attempt == max_retries:
                        logger.error("Failed after %d retries: %s", max_retries, e)
                        raise
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    logger.warning("Attempt %d/%d failed (%s), retrying in %.1fs",
                                   attempt + 1, max_retries, e, delay)
                    time.sleep(delay)
            raise last_exc
        return wrapper
    return decorator


def with_async_retry(max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0):
    """Decorator that retries an async function with exponential backoff."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    if attempt == max_retries:
                        logger.error("Failed after %d retries: %s", max_retries, e)
                        raise
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    logger.warning("Attempt %d/%d failed (%s), retrying in %.1fs",
                                   attempt + 1, max_retries, e, delay)
                    await asyncio.sleep(delay)
            raise last_exc
        return wrapper
    return decorator


def log_dead_letter(worker_name: str, payload: dict, error: Exception):
    """Log failed jobs that exceeded retries for manual review."""
    logger.error("DEAD_LETTER worker=%s error=%s payload=%s",
                 worker_name, str(error)[:200], str(payload)[:500])
