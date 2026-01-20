"""Authentication utilities for API key management."""

import hashlib
import secrets
import string
from typing import Tuple

import bcrypt

# Key format: llmc_<32 random chars>
KEY_PREFIX = "llmc_"
KEY_LENGTH = 32
KEY_ALPHABET = string.ascii_letters + string.digits

# Bcrypt work factor (12 is recommended for production)
# Higher values are more secure but slower
BCRYPT_ROUNDS = 12


def generate_api_key() -> Tuple[str, str, str]:
    """
    Generate a new API key.

    Returns:
        Tuple of (full_key, key_prefix, key_hash)
        - full_key: The complete API key to give to the user (shown once)
        - key_prefix: First 12 chars for identification in logs/UI
        - key_hash: Bcrypt hash for secure storage
    """
    random_part = "".join(secrets.choice(KEY_ALPHABET) for _ in range(KEY_LENGTH))
    full_key = f"{KEY_PREFIX}{random_part}"
    key_prefix = full_key[:12]  # "llmc_" + first 7 random chars
    key_hash = hash_api_key(full_key)

    return full_key, key_prefix, key_hash


def hash_api_key(key: str) -> str:
    """
    Hash an API key for secure storage using bcrypt.

    Bcrypt automatically generates a random salt and includes it in the hash.
    The work factor makes brute-force attacks computationally expensive.
    """
    key_bytes = key.encode("utf-8")
    hashed = bcrypt.hashpw(key_bytes, bcrypt.gensalt(rounds=BCRYPT_ROUNDS))
    return hashed.decode("utf-8")


def verify_api_key(provided_key: str, stored_hash: str) -> bool:
    """
    Verify an API key against its stored bcrypt hash.

    Bcrypt's checkpw function is constant-time to prevent timing attacks.
    """
    try:
        provided_bytes = provided_key.encode("utf-8")
        stored_bytes = stored_hash.encode("utf-8")
        return bcrypt.checkpw(provided_bytes, stored_bytes)
    except (ValueError, TypeError):
        # Invalid hash format or other bcrypt error
        return False


def verify_api_key_legacy(provided_key: str, stored_hash: str) -> bool:
    """
    Verify an API key against a legacy SHA-256 hash.

    Used for backwards compatibility during migration.
    """
    salt = provided_key[:12] if len(provided_key) >= 12 else provided_key
    salted = f"{salt}:{provided_key}"
    provided_hash = hashlib.sha256(salted.encode()).hexdigest()
    return secrets.compare_digest(provided_hash, stored_hash)


def is_bcrypt_hash(hash_string: str) -> bool:
    """Check if a hash string is a bcrypt hash (starts with $2b$ or $2a$)."""
    return hash_string.startswith(("$2b$", "$2a$", "$2y$"))


def verify_api_key_auto(provided_key: str, stored_hash: str) -> bool:
    """
    Verify an API key, automatically detecting hash type.

    Supports both bcrypt (new) and SHA-256 (legacy) hashes for migration.
    """
    if is_bcrypt_hash(stored_hash):
        return verify_api_key(provided_key, stored_hash)
    else:
        return verify_api_key_legacy(provided_key, stored_hash)


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
