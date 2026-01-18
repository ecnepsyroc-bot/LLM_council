"""Authentication utilities for API key management."""

import hashlib
import secrets
import string
from typing import Tuple

# Key format: llmc_<32 random chars>
KEY_PREFIX = "llmc_"
KEY_LENGTH = 32
KEY_ALPHABET = string.ascii_letters + string.digits


def generate_api_key() -> Tuple[str, str, str]:
    """
    Generate a new API key.

    Returns:
        Tuple of (full_key, key_prefix, key_hash)
        - full_key: The complete API key to give to the user (shown once)
        - key_prefix: First 12 chars for identification in logs/UI
        - key_hash: SHA-256 hash for secure storage
    """
    random_part = "".join(secrets.choice(KEY_ALPHABET) for _ in range(KEY_LENGTH))
    full_key = f"{KEY_PREFIX}{random_part}"
    key_prefix = full_key[:12]  # "llmc_" + first 7 random chars
    key_hash = hash_api_key(full_key)

    return full_key, key_prefix, key_hash


def hash_api_key(key: str) -> str:
    """
    Hash an API key for secure storage.

    Uses SHA-256 with a consistent salt derived from the key prefix.
    This allows us to verify keys without storing them in plain text.
    """
    # Use key prefix as salt to prevent rainbow table attacks
    # while still allowing prefix-based lookups
    salt = key[:12] if len(key) >= 12 else key
    salted = f"{salt}:{key}"
    return hashlib.sha256(salted.encode()).hexdigest()


def verify_api_key(provided_key: str, stored_hash: str) -> bool:
    """
    Verify an API key against its stored hash.

    Uses constant-time comparison to prevent timing attacks.
    """
    provided_hash = hash_api_key(provided_key)
    return secrets.compare_digest(provided_hash, stored_hash)


def extract_key_prefix(key: str) -> str:
    """Extract the prefix from an API key for identification."""
    return key[:12] if len(key) >= 12 else key


def is_valid_key_format(key: str) -> bool:
    """Check if a string matches the expected API key format."""
    if not key.startswith(KEY_PREFIX):
        return False
    if len(key) != len(KEY_PREFIX) + KEY_LENGTH:
        return False
    random_part = key[len(KEY_PREFIX) :]
    return all(c in KEY_ALPHABET for c in random_part)
