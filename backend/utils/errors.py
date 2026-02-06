"""Error handling and retry utilities."""

import asyncio
import random
import logging
from typing import Callable, Optional
from functools import wraps

logger = logging.getLogger(__name__)


class AppError(Exception):
    pass


class ApiError(AppError):
    pass


class DatabaseError(AppError):
    pass


class RateLimitError(AppError):
    pass


async def with_retry(
    fn: Callable,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    backoff_multiplier: float = 2.0,
    jitter: bool = True,
):
    """Execute async function with exponential backoff retry."""
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await fn()
        except Exception as e:
            last_error = e
            if attempt == max_attempts:
                break
            delay = base_delay * (backoff_multiplier ** (attempt - 1))
            if jitter:
                delay *= random.uniform(0.75, 1.25)
            logger.warning(f"Attempt {attempt}/{max_attempts} failed: {e}. Retrying in {delay:.1f}s")
            await asyncio.sleep(delay)
    raise last_error


def retry_decorator(max_attempts: int = 3, base_delay: float = 1.0):
    """Decorator for async functions with retry logic."""
    def decorator(fn):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            return await with_retry(
                lambda: fn(*args, **kwargs),
                max_attempts=max_attempts,
                base_delay=base_delay,
            )
        return wrapper
    return decorator


def sanitize_for_logging(text: str, max_length: int = 200) -> str:
    """Remove control characters and truncate for safe logging."""
    clean = ''.join(c for c in text if c.isprintable() or c in '\n\t')
    clean = clean.replace('\n', ' ').strip()
    if len(clean) > max_length:
        clean = clean[:max_length] + '...'
    return clean
