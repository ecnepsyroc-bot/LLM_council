"""PII (Personally Identifiable Information) detection for LLM responses.

Scans LLM outputs for potential PII that shouldn't be exposed,
providing warnings when detected.
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class PIIMatch:
    """A detected PII match."""
    pii_type: str
    value: str
    start: int
    end: int
    redacted: str


@dataclass
class PIIReport:
    """Report of PII detection results."""
    has_pii: bool
    matches: list[PIIMatch]
    redacted_text: str
    warnings: list[str]


# PII detection patterns
PII_PATTERNS = {
    "ssn": (
        r'\b\d{3}-\d{2}-\d{4}\b',
        "Social Security Number"
    ),
    "ssn_no_dash": (
        r'\b\d{9}\b',  # Only flag if surrounded by SSN context
        "Potential SSN (9 consecutive digits)"
    ),
    "credit_card": (
        r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b',
        "Credit Card Number"
    ),
    "credit_card_spaced": (
        r'\b\d{4}[\s-]\d{4}[\s-]\d{4}[\s-]\d{4}\b',
        "Credit Card Number (spaced)"
    ),
    "email": (
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "Email Address"
    ),
    "phone_us": (
        r'(?:\+1[-.\s]?)?(?:\(\d{3}\)[-.\s]?|\b\d{3}[-.\s]?)\d{3}[-.\s]?\d{4}\b',
        "US Phone Number"
    ),
    "ip_address": (
        r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b',
        "IP Address"
    ),
    "date_of_birth": (
        r'\b(?:DOB|date of birth|born on)[:\s]+\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
        "Date of Birth"
    ),
    "passport": (
        r'\b[A-Z]{1,2}\d{6,9}\b',
        "Potential Passport Number"
    ),
    "iban": (
        r'\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}([A-Z0-9]?){0,16}\b',
        "IBAN"
    ),
}

# Patterns that need additional context to avoid false positives
CONTEXT_SENSITIVE_PATTERNS = {
    "ssn_no_dash",
    "passport",  # Too many false positives without context
}


def detect_pii(
    text: str,
    redact: bool = False,
    include_context_sensitive: bool = False
) -> PIIReport:
    """
    Detect potential PII in text.

    Args:
        text: Text to scan for PII
        redact: If True, replace PII with [REDACTED] markers
        include_context_sensitive: Include patterns that may have false positives

    Returns:
        PIIReport with detection results
    """
    if not text:
        return PIIReport(
            has_pii=False,
            matches=[],
            redacted_text=text,
            warnings=[]
        )

    matches: list[PIIMatch] = []
    warnings: list[str] = []
    redacted_text = text

    for pii_type, (pattern, description) in PII_PATTERNS.items():
        # Skip context-sensitive patterns unless requested
        if pii_type in CONTEXT_SENSITIVE_PATTERNS and not include_context_sensitive:
            continue

        for match in re.finditer(pattern, text, re.IGNORECASE):
            value = match.group()

            # Additional validation for context-sensitive patterns
            if pii_type == "ssn_no_dash":
                # Check for SSN context words nearby
                context_start = max(0, match.start() - 30)
                context_end = min(len(text), match.end() + 10)
                context = text[context_start:context_end].lower()
                if not any(word in context for word in ['ssn', 'social', 'security']):
                    continue

            redacted_value = f"[{pii_type.upper()}_REDACTED]"

            matches.append(PIIMatch(
                pii_type=pii_type,
                value=value,
                start=match.start(),
                end=match.end(),
                redacted=redacted_value
            ))

    if matches:
        warnings.append(
            f"Detected {len(matches)} potential PII instance(s) in response"
        )

        # Group by type for summary
        type_counts = {}
        for m in matches:
            type_counts[m.pii_type] = type_counts.get(m.pii_type, 0) + 1

        for pii_type, count in type_counts.items():
            _, description = PII_PATTERNS[pii_type]
            warnings.append(f"  - {description}: {count}")

    # Redact if requested (process in reverse order to maintain positions)
    if redact and matches:
        for m in sorted(matches, key=lambda x: x.start, reverse=True):
            redacted_text = redacted_text[:m.start] + m.redacted + redacted_text[m.end:]

    return PIIReport(
        has_pii=len(matches) > 0,
        matches=matches,
        redacted_text=redacted_text,
        warnings=warnings
    )


def scan_response_for_pii(response: str) -> Optional[dict]:
    """
    Scan an LLM response for PII.

    Returns dict with warning info if PII detected, None otherwise.
    """
    report = detect_pii(response)

    if not report.has_pii:
        return None

    return {
        "pii_detected": True,
        "count": len(report.matches),
        "types": list(set(m.pii_type for m in report.matches)),
        "warnings": report.warnings
    }
