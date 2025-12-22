"""Rate limiter for external API calls."""

import asyncio
import time
from typing import Dict
from dataclasses import dataclass, field
from threading import Lock

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RateLimiter:
    """
    Token bucket rate limiter.

    Attributes:
        requests_per_second: Maximum requests per second
        burst_size: Maximum burst size (bucket capacity)
    """

    requests_per_second: float
    burst_size: int = 10
    _tokens: float = field(init=False)
    _last_update: float = field(init=False)
    _lock: Lock = field(default_factory=Lock, init=False)

    def __post_init__(self):
        self._tokens = float(self.burst_size)
        self._last_update = time.monotonic()

    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_update
        self._tokens = min(
            self.burst_size,
            self._tokens + elapsed * self.requests_per_second,
        )
        self._last_update = now

    def acquire(self, tokens: int = 1) -> float:
        """
        Acquire tokens, blocking if necessary.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            Time waited in seconds
        """
        with self._lock:
            self._refill()

            if self._tokens >= tokens:
                self._tokens -= tokens
                return 0.0

            # Calculate wait time
            tokens_needed = tokens - self._tokens
            wait_time = tokens_needed / self.requests_per_second

            logger.debug(f"Rate limit: waiting {wait_time:.2f}s for {tokens} tokens")
            time.sleep(wait_time)

            self._tokens = 0
            self._last_update = time.monotonic()
            return wait_time

    async def acquire_async(self, tokens: int = 1) -> float:
        """
        Async version of acquire.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            Time waited in seconds
        """
        with self._lock:
            self._refill()

            if self._tokens >= tokens:
                self._tokens -= tokens
                return 0.0

            tokens_needed = tokens - self._tokens
            wait_time = tokens_needed / self.requests_per_second

        logger.debug(f"Rate limit: waiting {wait_time:.2f}s for {tokens} tokens")
        await asyncio.sleep(wait_time)

        with self._lock:
            self._tokens = 0
            self._last_update = time.monotonic()

        return wait_time


class RateLimiterRegistry:
    """Registry of rate limiters for different services."""

    def __init__(self):
        self._limiters: Dict[str, RateLimiter] = {}
        self._lock = Lock()

    def get(self, name: str, requests_per_second: float = 10, burst_size: int = 10) -> RateLimiter:
        """
        Get or create a rate limiter.

        Args:
            name: Limiter name
            requests_per_second: Max requests per second
            burst_size: Max burst size

        Returns:
            RateLimiter instance
        """
        with self._lock:
            if name not in self._limiters:
                self._limiters[name] = RateLimiter(
                    requests_per_second=requests_per_second,
                    burst_size=burst_size,
                )
            return self._limiters[name]


# Global registry
rate_limiters = RateLimiterRegistry()

# Pre-configured limiters
sec_edgar_limiter = rate_limiters.get("sec_edgar", requests_per_second=10, burst_size=5)
openai_limiter = rate_limiters.get("openai", requests_per_second=50, burst_size=20)
