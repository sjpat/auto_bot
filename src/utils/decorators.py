"""
Decorators for common functionality.
"""

import asyncio
import functools
import time
import logging
from typing import Callable, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def retry(
    max_attempts: int = 3,
    delay_seconds: float = 1.0,
    backoff_multiplier: float = 2.0,
    exceptions: tuple = (Exception,),
):
    """
    Retry decorator for synchronous functions.

    Args:
        max_attempts: Maximum number of retry attempts
        delay_seconds: Initial delay between retries
        backoff_multiplier: Multiplier for exponential backoff
        exceptions: Tuple of exceptions to catch

    Example:
        @retry(max_attempts=3, delay_seconds=1.0)
        def fetch_data():
            # This will retry up to 3 times with 1s, 2s, 4s delays
            return api.get_data()
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            attempt = 0
            current_delay = delay_seconds

            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise

                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt}/{max_attempts}), "
                        f"retrying in {current_delay:.1f}s: {e}"
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff_multiplier

            return None

        return wrapper

    return decorator


def async_retry(
    max_attempts: int = 3,
    delay_seconds: float = 1.0,
    backoff_multiplier: float = 2.0,
    exceptions: tuple = (Exception,),
):
    """
    Retry decorator for async functions.

    Args:
        max_attempts: Maximum number of retry attempts
        delay_seconds: Initial delay between retries
        backoff_multiplier: Multiplier for exponential backoff
        exceptions: Tuple of exceptions to catch

    Example:
        @async_retry(max_attempts=3, delay_seconds=1.0)
        async def fetch_data():
            return await api.get_data()
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            attempt = 0
            current_delay = delay_seconds

            while attempt < max_attempts:
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise

                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt}/{max_attempts}), "
                        f"retrying in {current_delay:.1f}s: {e}"
                    )
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff_multiplier

            return None

        return wrapper

    return decorator


def rate_limit(max_calls: int, time_window_seconds: float):
    """
    Rate limiting decorator.

    Args:
        max_calls: Maximum number of calls allowed
        time_window_seconds: Time window in seconds

    Example:
        @rate_limit(max_calls=10, time_window_seconds=60)
        def api_call():
            # Maximum 10 calls per 60 seconds
            return api.fetch()
    """

    def decorator(func: Callable) -> Callable:
        calls = []

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            now = time.time()

            # Remove old calls outside time window
            while calls and calls[0] < now - time_window_seconds:
                calls.pop(0)

            # Check if rate limit exceeded
            if len(calls) >= max_calls:
                sleep_time = calls[0] + time_window_seconds - now
                logger.warning(
                    f"Rate limit exceeded for {func.__name__}, "
                    f"sleeping for {sleep_time:.1f}s"
                )
                await asyncio.sleep(sleep_time)
                calls.pop(0)

            # Record this call
            calls.append(now)

            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            now = time.time()

            # Remove old calls outside time window
            while calls and calls[0] < now - time_window_seconds:
                calls.pop(0)

            # Check if rate limit exceeded
            if len(calls) >= max_calls:
                sleep_time = calls[0] + time_window_seconds - now
                logger.warning(
                    f"Rate limit exceeded for {func.__name__}, "
                    f"sleeping for {sleep_time:.1f}s"
                )
                time.sleep(sleep_time)
                calls.pop(0)

            # Record this call
            calls.append(now)

            return func(*args, **kwargs)

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def timing(func: Callable) -> Callable:
    """
    Decorator to measure function execution time.

    Example:
        @timing
        def slow_function():
            time.sleep(1)
    """

    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs) -> Any:
        start = time.time()
        result = await func(*args, **kwargs)
        elapsed = time.time() - start

        logger.debug(f"{func.__name__} took {elapsed:.3f}s")
        return result

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs) -> Any:
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start

        logger.debug(f"{func.__name__} took {elapsed:.3f}s")
        return result

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper


def cache_with_ttl(ttl_seconds: float):
    """
    Simple cache decorator with TTL (Time To Live).

    Args:
        ttl_seconds: Cache lifetime in seconds

    Example:
        @cache_with_ttl(ttl_seconds=60)
        def expensive_function(arg):
            # Result cached for 60 seconds
            return compute_expensive(arg)
    """

    def decorator(func: Callable) -> Callable:
        cache = {}
        cache_times = {}

        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Create cache key from arguments
            key = str(args) + str(kwargs)
            now = time.time()

            # Check if cached and not expired
            if key in cache and key in cache_times:
                if now - cache_times[key] < ttl_seconds:
                    logger.debug(f"Cache hit for {func.__name__}")
                    return cache[key]

            # Call function and cache result
            result = func(*args, **kwargs)
            cache[key] = result
            cache_times[key] = now

            return result

        return wrapper

    return decorator
