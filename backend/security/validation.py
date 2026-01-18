"""Input validation and sanitization for LLM Council API."""

import re
import html
from dataclasses import dataclass
from typing import Optional


@dataclass
class ContentLimits:
    """Content size and format limits."""

    # Message content limits
    MAX_MESSAGE_LENGTH: int = 50_000  # 50KB
    MIN_MESSAGE_LENGTH: int = 1

    # Title limits
    MAX_TITLE_LENGTH: int = 200
    MIN_TITLE_LENGTH: int = 1

    # Image limits
    MAX_IMAGE_SIZE: int = 10 * 1024 * 1024  # 10MB base64
    MAX_IMAGES_PER_MESSAGE: int = 5

    # Rate limits for content
    MAX_CONSECUTIVE_NEWLINES: int = 4
    MAX_CONSECUTIVE_SPACES: int = 20


class ValidationError(Exception):
    """Raised when input validation fails."""

    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


def validate_message_content(
    content: str,
    images: list[str] = None,
    limits: ContentLimits = None
) -> tuple[str, list[str]]:
    """
    Validate and sanitize message content.

    Args:
        content: The message text content
        images: Optional list of base64-encoded images
        limits: Content limits configuration

    Returns:
        Tuple of (sanitized_content, validated_images)

    Raises:
        ValidationError: If validation fails
    """
    limits = limits or ContentLimits()
    images = images or []

    # Check content exists and is not just whitespace
    if not content or not content.strip():
        raise ValidationError("content", "Message content cannot be empty")

    # Strip and check length
    content = content.strip()

    if len(content) < limits.MIN_MESSAGE_LENGTH:
        raise ValidationError("content", f"Message must be at least {limits.MIN_MESSAGE_LENGTH} character(s)")

    if len(content) > limits.MAX_MESSAGE_LENGTH:
        raise ValidationError(
            "content",
            f"Message exceeds maximum length of {limits.MAX_MESSAGE_LENGTH:,} characters"
        )

    # Sanitize content
    content = _sanitize_content(content, limits)

    # Validate images
    validated_images = []
    if len(images) > limits.MAX_IMAGES_PER_MESSAGE:
        raise ValidationError(
            "images",
            f"Maximum {limits.MAX_IMAGES_PER_MESSAGE} images allowed per message"
        )

    for i, img in enumerate(images):
        validated_img = _validate_image(img, i, limits)
        validated_images.append(validated_img)

    return content, validated_images


def validate_conversation_update(
    title: Optional[str] = None,
    is_pinned: Optional[bool] = None,
    is_hidden: Optional[bool] = None,
    limits: ContentLimits = None
) -> dict:
    """
    Validate conversation update fields.

    Args:
        title: Optional new title
        is_pinned: Optional pin status
        is_hidden: Optional hidden status
        limits: Content limits configuration

    Returns:
        Dict of validated fields (only includes non-None values)

    Raises:
        ValidationError: If validation fails
    """
    limits = limits or ContentLimits()
    validated = {}

    if title is not None:
        title = title.strip()

        if len(title) < limits.MIN_TITLE_LENGTH:
            raise ValidationError("title", "Title cannot be empty")

        if len(title) > limits.MAX_TITLE_LENGTH:
            raise ValidationError(
                "title",
                f"Title exceeds maximum length of {limits.MAX_TITLE_LENGTH} characters"
            )

        # Sanitize title - escape HTML and remove control characters
        title = html.escape(title)
        title = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', title)

        validated["title"] = title

    if is_pinned is not None:
        if not isinstance(is_pinned, bool):
            raise ValidationError("is_pinned", "Must be a boolean value")
        validated["is_pinned"] = is_pinned

    if is_hidden is not None:
        if not isinstance(is_hidden, bool):
            raise ValidationError("is_hidden", "Must be a boolean value")
        validated["is_hidden"] = is_hidden

    return validated


def sanitize_for_prompt(text: str) -> str:
    """
    Sanitize user text before including in LLM prompts.

    This helps prevent prompt injection attacks by:
    1. Detecting and neutralizing common injection patterns
    2. Adding clear content boundaries

    Args:
        text: User-provided text

    Returns:
        Sanitized text safe for prompt inclusion
    """
    if not text:
        return ""

    sanitized = text.strip()

    # Patterns that might indicate prompt injection attempts
    injection_patterns = [
        # Instruction override attempts
        (r'(?i)ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|context)', '[CONTENT FILTERED]'),
        (r'(?i)disregard\s+(all\s+)?(previous|prior|above|earlier)', '[CONTENT FILTERED]'),
        (r'(?i)forget\s+(everything|all)\s+(above|before|prior)', '[CONTENT FILTERED]'),

        # Role/persona manipulation
        (r'(?i)you\s+are\s+now\s+(a|an|the)\s+', '[CONTENT FILTERED]'),
        (r'(?i)act\s+as\s+(if\s+)?(you\s+)?(are|were)\s+(a|an|the)', '[CONTENT FILTERED]'),
        (r'(?i)pretend\s+(to\s+be|you\s+are)', '[CONTENT FILTERED]'),

        # System prompt extraction
        (r'(?i)what\s+(is|are)\s+your\s+(system\s+)?(prompt|instructions)', '[CONTENT FILTERED]'),
        (r'(?i)repeat\s+(your\s+)?(system\s+)?(prompt|instructions)', '[CONTENT FILTERED]'),
        (r'(?i)show\s+(me\s+)?(your\s+)?(system\s+)?(prompt|instructions)', '[CONTENT FILTERED]'),

        # Delimiter injection
        (r'```system', '```text'),
        (r'<system>', '[system]'),
        (r'</system>', '[/system]'),

        # Fake message boundaries
        (r'(?i)^(user|assistant|system)\s*:', lambda m: f'[{m.group(1)}]:'),
    ]

    for pattern, replacement in injection_patterns:
        if callable(replacement):
            sanitized = re.sub(pattern, replacement, sanitized)
        else:
            sanitized = re.sub(pattern, replacement, sanitized)

    return sanitized


def _sanitize_content(content: str, limits: ContentLimits) -> str:
    """Sanitize message content."""
    # Remove null bytes
    content = content.replace('\x00', '')

    # Limit consecutive newlines
    pattern = r'\n{' + str(limits.MAX_CONSECUTIVE_NEWLINES + 1) + r',}'
    replacement = '\n' * limits.MAX_CONSECUTIVE_NEWLINES
    content = re.sub(pattern, replacement, content)

    # Limit consecutive spaces (but preserve code indentation)
    # Only collapse spaces that aren't at the start of a line
    def collapse_spaces(match):
        spaces = match.group(0)
        if len(spaces) > limits.MAX_CONSECUTIVE_SPACES:
            return ' ' * limits.MAX_CONSECUTIVE_SPACES
        return spaces

    content = re.sub(r'(?<!^)(?<!\n) {2,}', collapse_spaces, content)

    return content


def _validate_image(image: str, index: int, limits: ContentLimits) -> str:
    """Validate a single base64 image."""
    # Check size
    if len(image) > limits.MAX_IMAGE_SIZE:
        raise ValidationError(
            "images",
            f"Image {index + 1} exceeds maximum size of {limits.MAX_IMAGE_SIZE // 1024 // 1024}MB"
        )

    # Validate base64 data URL format
    valid_pattern = r'^data:image/(png|jpeg|jpg|gif|webp);base64,[A-Za-z0-9+/=]+$'
    if not re.match(valid_pattern, image):
        raise ValidationError(
            "images",
            f"Image {index + 1} has invalid format. Must be a base64-encoded PNG, JPEG, GIF, or WebP."
        )

    return image


def escape_html(text: str) -> str:
    """Escape HTML entities in text."""
    return html.escape(text)
