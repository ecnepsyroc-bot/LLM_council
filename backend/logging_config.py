"""
Logging configuration for LLM Council.

Features:
- JSON structured logging for production
- Text format for development
- Request ID tracking
- Sensitive data redaction
- Configurable levels
"""

import json
import logging
import re
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Context variable for request ID tracking
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)


def get_request_id() -> Optional[str]:
    """Get the current request ID from context."""
    return request_id_var.get()


def set_request_id(request_id: Optional[str] = None) -> str:
    """Set a request ID in context. Generates one if not provided."""
    rid = request_id or str(uuid.uuid4())[:8]
    request_id_var.set(rid)
    return rid


class SensitiveDataFilter(logging.Filter):
    """Filter to redact sensitive data from log records."""

    # Patterns for sensitive data
    PATTERNS = [
        # API keys
        (re.compile(r'(api[_-]?key["\']?\s*[:=]\s*["\']?)([a-zA-Z0-9_-]{20,})', re.I), r'\1[REDACTED]'),
        # Bearer tokens
        (re.compile(r'(Bearer\s+)([a-zA-Z0-9_.-]+)', re.I), r'\1[REDACTED]'),
        # OpenRouter keys (sk-or-...)
        (re.compile(r'(sk-or-[a-zA-Z0-9_-]{10})[a-zA-Z0-9_-]+', re.I), r'\1...[REDACTED]'),
        # Generic secrets
        (re.compile(r'(secret["\']?\s*[:=]\s*["\']?)([^\s"\']+)', re.I), r'\1[REDACTED]'),
        # Passwords
        (re.compile(r'(password["\']?\s*[:=]\s*["\']?)([^\s"\']+)', re.I), r'\1[REDACTED]'),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact sensitive data from log message."""
        if isinstance(record.msg, str):
            for pattern, replacement in self.PATTERNS:
                record.msg = pattern.sub(replacement, record.msg)

        # Also check args
        if record.args:
            args = list(record.args)
            for i, arg in enumerate(args):
                if isinstance(arg, str):
                    for pattern, replacement in self.PATTERNS:
                        args[i] = pattern.sub(replacement, arg)
            record.args = tuple(args)

        return True


class JSONFormatter(logging.Formatter):
    """JSON log formatter for production."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }

        # Add request ID if available
        request_id = get_request_id()
        if request_id:
            log_data['request_id'] = request_id

        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, 'extra_data') and record.extra_data:
            log_data.update(record.extra_data)

        # Add source location for errors
        if record.levelno >= logging.ERROR:
            log_data['source'] = {
                'file': record.pathname,
                'line': record.lineno,
                'function': record.funcName,
            }

        return json.dumps(log_data)


class TextFormatter(logging.Formatter):
    """Human-readable text formatter for development."""

    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'

    def __init__(self, use_colors: bool = True):
        super().__init__()
        self.use_colors = use_colors

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as colored text."""
        # Get request ID
        request_id = get_request_id()
        rid_str = f"[{request_id}] " if request_id else ""

        # Format timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Get color
        color = self.COLORS.get(record.levelname, '') if self.use_colors else ''
        reset = self.RESET if self.use_colors else ''

        # Build message
        message = f"{timestamp} {color}{record.levelname:8}{reset} {rid_str}{record.name}: {record.getMessage()}"

        # Add exception if present
        if record.exc_info:
            message += '\n' + self.formatException(record.exc_info)

        return message


def setup_logging(
    level: str = "INFO",
    format_type: str = "text",
    log_file: Optional[Path] = None,
) -> logging.Logger:
    """
    Configure application logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: "text" for development, "json" for production
        log_file: Optional path to log file

    Returns:
        Root logger
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Create sensitive data filter
    sensitive_filter = SensitiveDataFilter()

    # Create formatter based on type
    if format_type.lower() == "json":
        formatter = JSONFormatter()
    else:
        # Check if stdout is a TTY for color support
        use_colors = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
        formatter = TextFormatter(use_colors=use_colors)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(sensitive_filter)
    root_logger.addHandler(console_handler)

    # File handler (always JSON for easier parsing)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(JSONFormatter())
        file_handler.addFilter(sensitive_filter)
        root_logger.addHandler(file_handler)

    # Set levels for noisy libraries
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)

    return root_logger


class LoggingMiddleware:
    """
    ASGI middleware for request logging.

    Adds request ID to context and logs request/response.
    """

    def __init__(self, app):
        self.app = app
        self.logger = logging.getLogger('council.http')

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        # Generate request ID
        request_id = set_request_id()

        # Extract request info
        method = scope.get('method', 'UNKNOWN')
        path = scope.get('path', '/')
        client = scope.get('client', ('unknown', 0))

        # Log request
        self.logger.info(
            f"{method} {path}",
            extra={'extra_data': {
                'client_ip': client[0] if client else 'unknown',
                'request_id': request_id,
            }}
        )

        # Track response status
        response_status = [None]

        async def send_wrapper(message):
            if message['type'] == 'http.response.start':
                response_status[0] = message.get('status', 0)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            # Log response
            status = response_status[0] or 0
            level = logging.INFO if status < 400 else logging.WARNING if status < 500 else logging.ERROR
            self.logger.log(
                level,
                f"{method} {path} -> {status}",
                extra={'extra_data': {
                    'status': status,
                    'request_id': request_id,
                }}
            )
