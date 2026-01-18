"""Rate limiting middleware for LLM Council API."""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    # Requests per time window
    requests_per_minute: int = 60
    requests_per_hour: int = 500

    # Burst protection (max requests in short window)
    burst_limit: int = 10
    burst_window_seconds: float = 1.0

    # Paths to exclude from rate limiting
    excluded_paths: list = field(default_factory=lambda: ["/", "/api/config"])

    # Whether to include rate limit headers in response
    include_headers: bool = True

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

    def check_rate_limit(self, client_id: str) -> tuple[bool, str, dict]:
        """
        Check if a request should be allowed.

        Args:
            client_id: Unique identifier for the client (IP or API key)

        Returns:
            Tuple of (allowed, reason, headers)
            - allowed: Whether the request is allowed
            - reason: Error message if not allowed
            - headers: Rate limit headers to include in response
        """
        now = time.time()

        # Check burst limit (requests in last second)
        burst_count = self._counter.count_requests(client_id, self.config.burst_window_seconds)
        if burst_count >= self.config.burst_limit:
            return (
                False,
                f"Burst limit exceeded ({self.config.burst_limit} requests per second). Please slow down.",
                self._build_headers(client_id, "burst"),
            )

        # Check per-minute limit
        minute_count = self._counter.count_requests(client_id, 60)
        if minute_count >= self.config.requests_per_minute:
            oldest = self._counter.get_oldest_in_window(client_id, 60)
            retry_after = int(60 - (now - oldest)) + 1 if oldest else 60
            return (
                False,
                f"Rate limit exceeded ({self.config.requests_per_minute} requests per minute). Try again in {retry_after} seconds.",
                self._build_headers(client_id, "minute", retry_after),
            )

        # Check per-hour limit
        hour_count = self._counter.count_requests(client_id, 3600)
        if hour_count >= self.config.requests_per_hour:
            oldest = self._counter.get_oldest_in_window(client_id, 3600)
            retry_after = int(3600 - (now - oldest)) + 1 if oldest else 3600
            return (
                False,
                f"Hourly limit exceeded ({self.config.requests_per_hour} requests per hour). Try again in {retry_after // 60} minutes.",
                self._build_headers(client_id, "hour", retry_after),
            )

        # Request allowed - record it
        self._counter.record_request(client_id)

        return (True, "", self._build_headers(client_id, "ok"))

    def _build_headers(
        self, client_id: str, limit_type: str, retry_after: int = None
    ) -> dict:
        """Build rate limit headers for response."""
        if not self.config.include_headers:
            return {}

        minute_count = self._counter.count_requests(client_id, 60)
        minute_remaining = max(0, self.config.requests_per_minute - minute_count)

        headers = {
            "X-RateLimit-Limit": str(self.config.requests_per_minute),
            "X-RateLimit-Remaining": str(minute_remaining),
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

        # Get client identifier
        # Prefer X-Forwarded-For for proxied requests, fall back to client IP
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_id = forwarded.split(",")[0].strip()
        else:
            client_id = request.client.host if request.client else "unknown"

        # Check rate limit
        allowed, reason, headers = self.limiter.check_rate_limit(client_id)

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
