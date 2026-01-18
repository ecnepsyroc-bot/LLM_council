"""Rate limiting middleware for LLM Council API."""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Optional
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    # Requests per time window (defaults)
    requests_per_minute: int = 60
    requests_per_hour: int = 500

    # Burst protection (max requests in short window)
    burst_limit: int = 10
    burst_window_seconds: float = 1.0

    # Paths to exclude from rate limiting
    excluded_paths: list = field(default_factory=lambda: ["/", "/health", "/api/config"])

    # Whether to include rate limit headers in response
    include_headers: bool = True

    # Warning threshold (percentage of limit)
    warning_threshold: float = 0.8

    # Disable rate limiting entirely (for testing)
    enabled: bool = True


class SlidingWindowCounter:
    """Sliding window rate limiter implementation."""

    def __init__(self):
        # Store timestamps of requests per client
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _cleanup(self, client_id: str, window_seconds: float) -> None:
        """Remove expired timestamps from the window."""
        cutoff = time.time() - window_seconds
        self._requests[client_id] = [
            ts for ts in self._requests[client_id] if ts > cutoff
        ]

    def count_requests(self, client_id: str, window_seconds: float) -> int:
        """Count requests in the given time window."""
        self._cleanup(client_id, window_seconds)
        return len(self._requests[client_id])

    def record_request(self, client_id: str) -> None:
        """Record a new request timestamp."""
        self._requests[client_id].append(time.time())

    def get_oldest_in_window(self, client_id: str, window_seconds: float) -> float | None:
        """Get the oldest request timestamp in the window."""
        self._cleanup(client_id, window_seconds)
        if self._requests[client_id]:
            return min(self._requests[client_id])
        return None


class RateLimiter:
    """Rate limiter with multiple time windows."""

    def __init__(self, config: RateLimitConfig = None):
        self.config = config or RateLimitConfig()
        self._counter = SlidingWindowCounter()

    def check_rate_limit(
        self,
        client_id: str,
        custom_minute_limit: Optional[int] = None,
        custom_hour_limit: Optional[int] = None,
    ) -> tuple[bool, str, dict]:
        """
        Check if a request should be allowed.

        Args:
            client_id: Unique identifier for the client (IP or API key)
            custom_minute_limit: Override per-minute limit for this client
            custom_hour_limit: Override per-hour limit for this client

        Returns:
            Tuple of (allowed, reason, headers)
            - allowed: Whether the request is allowed
            - reason: Error message if not allowed
            - headers: Rate limit headers to include in response
        """
        now = time.time()

        # Use custom limits if provided, otherwise use config defaults
        minute_limit = custom_minute_limit or self.config.requests_per_minute
        hour_limit = custom_hour_limit or self.config.requests_per_hour

        # Check burst limit (requests in last second)
        burst_count = self._counter.count_requests(client_id, self.config.burst_window_seconds)
        if burst_count >= self.config.burst_limit:
            logger.warning(f"Burst limit exceeded for {client_id[:8]}...")
            return (
                False,
                f"Burst limit exceeded ({self.config.burst_limit} requests per second). Please slow down.",
                self._build_headers(client_id, "burst", limit=minute_limit),
            )

        # Check per-minute limit
        minute_count = self._counter.count_requests(client_id, 60)
        if minute_count >= minute_limit:
            oldest = self._counter.get_oldest_in_window(client_id, 60)
            retry_after = int(60 - (now - oldest)) + 1 if oldest else 60
            logger.warning(f"Minute rate limit exceeded for {client_id[:8]}...")
            return (
                False,
                f"Rate limit exceeded ({minute_limit} requests per minute). Try again in {retry_after} seconds.",
                self._build_headers(client_id, "minute", retry_after, limit=minute_limit),
            )

        # Check per-hour limit
        hour_count = self._counter.count_requests(client_id, 3600)
        if hour_count >= hour_limit:
            oldest = self._counter.get_oldest_in_window(client_id, 3600)
            retry_after = int(3600 - (now - oldest)) + 1 if oldest else 3600
            logger.warning(f"Hour rate limit exceeded for {client_id[:8]}...")
            return (
                False,
                f"Hourly limit exceeded ({hour_limit} requests per hour). Try again in {retry_after // 60} minutes.",
                self._build_headers(client_id, "hour", retry_after, limit=minute_limit),
            )

        # Check warning threshold
        minute_usage = minute_count / minute_limit
        if minute_usage >= self.config.warning_threshold:
            logger.info(
                f"Rate limit warning for {client_id[:8]}...: "
                f"{minute_count}/{minute_limit} ({minute_usage:.0%}) requests used"
            )

        # Request allowed - record it
        self._counter.record_request(client_id)

        return (True, "", self._build_headers(client_id, "ok", limit=minute_limit))

    def _build_headers(
        self,
        client_id: str,
        limit_type: str,
        retry_after: int = None,
        limit: int = None,
    ) -> dict:
        """Build rate limit headers for response."""
        if not self.config.include_headers:
            return {}

        effective_limit = limit or self.config.requests_per_minute
        minute_count = self._counter.count_requests(client_id, 60)
        minute_remaining = max(0, effective_limit - minute_count)

        # Calculate reset time (seconds until window resets)
        oldest = self._counter.get_oldest_in_window(client_id, 60)
        reset_seconds = int(60 - (time.time() - oldest)) if oldest else 60

        headers = {
            "X-RateLimit-Limit": str(effective_limit),
            "X-RateLimit-Remaining": str(minute_remaining),
            "X-RateLimit-Reset": str(reset_seconds),
            "X-RateLimit-Window": "60",
        }

        if retry_after:
            headers["Retry-After"] = str(retry_after)

        return headers


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for rate limiting."""

    def __init__(self, app, config: RateLimitConfig = None):
        super().__init__(app)
        self.limiter = RateLimiter(config)
        self.config = config or RateLimitConfig()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through rate limiter."""

        # Skip if rate limiting is disabled
        if not self.config.enabled:
            return await call_next(request)

        # Skip excluded paths
        if request.url.path in self.config.excluded_paths:
            return await call_next(request)

        # Get client identifier and custom limits
        client_id, custom_minute_limit = self._get_client_info(request)

        # Check rate limit with potential custom limit
        allowed, reason, headers = self.limiter.check_rate_limit(
            client_id,
            custom_minute_limit=custom_minute_limit,
        )

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=reason,
                headers=headers,
            )

        # Process request and add rate limit headers to response
        response = await call_next(request)

        # Add rate limit headers
        for key, value in headers.items():
            response.headers[key] = value

        return response

    def _get_client_info(self, request: Request) -> tuple[str, Optional[int]]:
        """
        Get client identifier and custom rate limit from request.

        Returns:
            Tuple of (client_id, custom_minute_limit)
        """
        custom_limit = None

        # Check if auth context has API key info with custom rate limit
        if hasattr(request.state, 'auth') and request.state.auth:
            auth = request.state.auth
            # Use API key ID as client identifier for per-key limiting
            if hasattr(auth, 'key_id') and auth.key_id:
                client_id = f"key:{auth.key_id}"
                # Check for custom rate limit on the key
                if hasattr(auth, 'rate_limit_per_minute') and auth.rate_limit_per_minute:
                    custom_limit = auth.rate_limit_per_minute
                return client_id, custom_limit

        # Fall back to IP-based identification
        # Prefer X-Forwarded-For for proxied requests
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_id = f"ip:{forwarded.split(',')[0].strip()}"
        else:
            client_id = f"ip:{request.client.host if request.client else 'unknown'}"

        return client_id, custom_limit
