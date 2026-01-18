"""Retry decorator with exponential backoff."""

import asyncio
import functools
import logging
import random
from typing import Callable, Optional, Tuple, Type

from .config import RetryConfig
from .exceptions import OpenRouterError, RateLimitError, ServerError

logger = logging.getLogger(__name__)


def calculate_delay(
    attempt: int,
    config: RetryConfig,
    retry_after: Optional[int] = None,
) -> float:
    """Calculate delay before next retry attempt."""
    if retry_after:
        # Respect Retry-After header
        return min(retry_after, config.max_delay)

    # Exponential backoff
    delay = config.initial_delay * (config.exponential_base**attempt)
    delay = min(delay, config.max_delay)

    # Add jitter to prevent thundering herd
    if config.jitter:
        delay = delay * (0.5 + random.random())

    return delay


def with_retry(
    config: Optional[RetryConfig] = None,
    retryable_exceptions: Tuple[Type[Exception], ...] = (ServerError, RateLimitError),
):
    """
    Decorator for retrying async functions with exponential backoff.

    Usage:
        @with_retry(RetryConfig(max_retries=3))
        async def my_function():
            ...
    """
    config = config or RetryConfig()

    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)

                except retryable_exceptions as e:
                    last_exception = e

                    if attempt == config.max_retries:
                        logger.error(
                            f"Max retries ({config.max_retries}) exceeded for "
                            f"{func.__name__}: {e}"
                        )
                        raise

                    # Get retry_after if available (for rate limits)
                    retry_after = getattr(e, "retry_after", None)
                    delay = calculate_delay(attempt, config, retry_after)

                    logger.warning(
                        f"Retry {attempt + 1}/{config.max_retries} for {func.__name__} "
                        f"after {delay:.1f}s: {e}"
                    )

                    await asyncio.sleep(delay)

                except Exception as e:
                    # Non-retryable exception
                    logger.error(f"Non-retryable error in {func.__name__}: {e}")
                    raise

            # Should not reach here, but just in case
            if last_exception:
                raise last_exception

        return wrapper

    return decorator


class RetryableOperation:
    """
    Context manager for retryable operations with progress tracking.

    Usage:
        async with RetryableOperation(config, "query_model") as op:
            result = await op.execute(my_async_func, *args, **kwargs)
    """

    def __init__(self, config: RetryConfig, operation_name: str):
        self.config = config
        self.operation_name = operation_name
        self.attempts = 0
        self.last_error: Optional[Exception] = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def execute(self, func: Callable, *args, **kwargs):
        """Execute function with retry logic."""
        for attempt in range(self.config.max_retries + 1):
            self.attempts = attempt + 1

            try:
                return await func(*args, **kwargs)

            except (ServerError, RateLimitError) as e:
                self.last_error = e

                if attempt == self.config.max_retries:
                    raise

                retry_after = getattr(e, "retry_after", None)
                delay = calculate_delay(attempt, self.config, retry_after)

                logger.warning(
                    f"{self.operation_name}: Retry {attempt + 1}/{self.config.max_retries} "
                    f"after {delay:.1f}s"
                )

                await asyncio.sleep(delay)

        # Should not reach here
        if self.last_error:
            raise self.last_error
