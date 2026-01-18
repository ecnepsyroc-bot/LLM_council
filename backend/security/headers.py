"""
Security headers middleware for LLM Council.

Adds security headers to all responses:
- Content-Security-Policy
- X-Content-Type-Options
- X-Frame-Options
- X-XSS-Protection
- Referrer-Policy
- Strict-Transport-Security (optional, for HTTPS)
"""

from typing import Callable, Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.

    These headers help protect against common web vulnerabilities
    including XSS, clickjacking, and MIME type sniffing.
    """

    def __init__(
        self,
        app,
        enable_hsts: bool = False,
        hsts_max_age: int = 31536000,  # 1 year
        csp_report_uri: Optional[str] = None,
    ):
        """
        Initialize security headers middleware.

        Args:
            app: FastAPI application
            enable_hsts: Enable Strict-Transport-Security (only for HTTPS)
            hsts_max_age: HSTS max-age in seconds
            csp_report_uri: Optional URI for CSP violation reports
        """
        super().__init__(app)
        self.enable_hsts = enable_hsts
        self.hsts_max_age = hsts_max_age
        self.csp_report_uri = csp_report_uri

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and add security headers to response."""
        response = await call_next(request)

        # Content-Security-Policy
        # Restrictive policy that allows inline styles (needed for some UI frameworks)
        csp_directives = [
            "default-src 'self'",
            "script-src 'self'",
            "style-src 'self' 'unsafe-inline'",  # Allow inline styles for UI
            "img-src 'self' data: https:",
            "font-src 'self'",
            "connect-src 'self'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
        ]

        if self.csp_report_uri:
            csp_directives.append(f"report-uri {self.csp_report_uri}")

        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # XSS protection (legacy but still useful for older browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions Policy (formerly Feature-Policy)
        # Disable dangerous browser features
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), "
            "camera=(), "
            "geolocation=(), "
            "gyroscope=(), "
            "magnetometer=(), "
            "microphone=(), "
            "payment=(), "
            "usb=()"
        )

        # HSTS (only enable when behind HTTPS termination)
        if self.enable_hsts:
            response.headers["Strict-Transport-Security"] = (
                f"max-age={self.hsts_max_age}; includeSubDomains"
            )

        # Prevent caching of sensitive data
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"

        return response


class CORSSecurityMiddleware(BaseHTTPMiddleware):
    """
    Enhanced CORS middleware with security considerations.

    Provides fine-grained control over CORS headers with
    security-focused defaults.
    """

    def __init__(
        self,
        app,
        allowed_origins: list[str] = None,
        allowed_methods: list[str] = None,
        allowed_headers: list[str] = None,
        allow_credentials: bool = False,
        max_age: int = 86400,  # 24 hours
    ):
        super().__init__(app)
        self.allowed_origins = allowed_origins or []
        self.allowed_methods = allowed_methods or ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
        self.allowed_headers = allowed_headers or [
            "Content-Type",
            "Authorization",
            "X-API-Key",
            "X-Request-ID",
        ]
        self.allow_credentials = allow_credentials
        self.max_age = max_age

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Handle CORS preflight and add headers."""
        origin = request.headers.get("origin")

        # Handle preflight OPTIONS request
        if request.method == "OPTIONS":
            response = Response(status_code=204)
        else:
            response = await call_next(request)

        # Only add CORS headers if origin is in allowed list
        if origin and self._is_allowed_origin(origin):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = ", ".join(self.allowed_methods)
            response.headers["Access-Control-Allow-Headers"] = ", ".join(self.allowed_headers)
            response.headers["Access-Control-Max-Age"] = str(self.max_age)

            if self.allow_credentials:
                response.headers["Access-Control-Allow-Credentials"] = "true"

            # Expose custom headers to client
            response.headers["Access-Control-Expose-Headers"] = (
                "X-Request-ID, X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset"
            )

        return response

    def _is_allowed_origin(self, origin: str) -> bool:
        """Check if origin is in allowed list."""
        if not self.allowed_origins:
            return False

        if "*" in self.allowed_origins:
            return True

        # Exact match
        if origin in self.allowed_origins:
            return True

        # Check for wildcard subdomain patterns
        for allowed in self.allowed_origins:
            if allowed.startswith("*."):
                domain = allowed[2:]
                if origin.endswith(domain) or origin.endswith(f".{domain}"):
                    return True

        return False
