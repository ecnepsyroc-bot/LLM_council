"""Security package for LLM Council."""

from .cors import configure_cors, get_cors_config
from .headers import SecurityHeadersMiddleware, CORSSecurityMiddleware
from .rate_limiter import RateLimitMiddleware, RateLimitConfig
from .validation import (
    validate_message_content,
    validate_conversation_update,
    sanitize_for_prompt,
    escape_html,
    ContentLimits,
    ValidationError,
)
from .pii import detect_pii, scan_response_for_pii, PIIReport, PIIMatch

__all__ = [
    "configure_cors",
    "get_cors_config",
    "SecurityHeadersMiddleware",
    "CORSSecurityMiddleware",
    "RateLimitMiddleware",
    "RateLimitConfig",
    "validate_message_content",
    "validate_conversation_update",
    "sanitize_for_prompt",
    "escape_html",
    "ContentLimits",
    "ValidationError",
    "detect_pii",
    "scan_response_for_pii",
    "PIIReport",
    "PIIMatch",
]
