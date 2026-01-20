"""Tests for authentication system."""

import pytest
from datetime import datetime, timedelta, timezone

from backend.auth.utils import (
    generate_api_key,
    hash_api_key,
    verify_api_key,
    verify_api_key_auto,
    verify_api_key_legacy,
    is_bcrypt_hash,
    is_valid_key_format,
    extract_key_prefix,
    KEY_PREFIX,
    KEY_LENGTH,
)
from backend.auth.models import APIKeyCreate, Permission
from backend.auth.service import APIKeyService
from backend.auth.exceptions import (
    InvalidAPIKeyError,
    ExpiredAPIKeyError,
    RevokedAPIKeyError,
    InsufficientPermissionsError,
)


class TestAPIKeyUtils:
    """Tests for API key utility functions."""

    def test_generate_api_key_format(self):
        """Generated keys have correct format."""
        full_key, prefix, key_hash = generate_api_key()

        assert full_key.startswith(KEY_PREFIX)
        assert len(full_key) == len(KEY_PREFIX) + KEY_LENGTH  # "llmc_" + 32 chars
        assert prefix == full_key[:12]
        # Bcrypt hash starts with $2b$ and is ~60 chars
        assert key_hash.startswith("$2b$")
        assert len(key_hash) == 60

    def test_generate_api_key_uniqueness(self):
        """Each generated key is unique."""
        keys = [generate_api_key()[0] for _ in range(100)]
        assert len(set(keys)) == 100

    def test_hash_api_key_non_deterministic(self):
        """Bcrypt produces different hashes for same key (different salts)."""
        key = "llmc_" + "a" * 32
        hash1 = hash_api_key(key)
        hash2 = hash_api_key(key)
        # Bcrypt produces different hashes due to random salt
        assert hash1 != hash2
        # But both should verify correctly
        assert verify_api_key(key, hash1)
        assert verify_api_key(key, hash2)

    def test_hash_api_key_is_bcrypt(self):
        """Hash is a valid bcrypt hash."""
        key = "llmc_" + "a" * 32
        key_hash = hash_api_key(key)
        assert is_bcrypt_hash(key_hash)
        assert key_hash.startswith("$2b$")

    def test_verify_api_key_valid(self):
        """Valid key verifies correctly."""
        full_key, _, key_hash = generate_api_key()
        assert verify_api_key(full_key, key_hash)

    def test_verify_api_key_invalid(self):
        """Invalid key fails verification."""
        full_key, _, key_hash = generate_api_key()
        wrong_key = full_key[:-1] + "X"
        assert not verify_api_key(wrong_key, key_hash)

    def test_is_valid_key_format_valid(self):
        """Valid format passes."""
        # KEY_LENGTH is 32, so we need 32 chars after "llmc_"
        assert is_valid_key_format("llmc_abcdefghijklmnopqrstuvwxyz12"[:5] + "a" * 32)

    def test_is_valid_key_format_wrong_prefix(self):
        """Wrong prefix fails."""
        assert not is_valid_key_format("xxxx_abcdefghijklmnopqrstuvwxyz12")

    def test_is_valid_key_format_wrong_length(self):
        """Wrong length fails."""
        assert not is_valid_key_format("llmc_abc")

    def test_is_valid_key_format_invalid_chars(self):
        """Invalid characters fail."""
        assert not is_valid_key_format("llmc_abc!@#$%^&*()_+{}|:<>?1234567")

    def test_extract_key_prefix(self):
        """Prefix extraction works correctly."""
        key = "llmc_" + "a" * 32
        assert extract_key_prefix(key) == "llmc_aaaaaaa"  # 12 chars total

    def test_extract_key_prefix_short_key(self):
        """Short key returns full string."""
        key = "short"
        assert extract_key_prefix(key) == "short"

    def test_is_bcrypt_hash_true(self):
        """Bcrypt hashes are correctly identified."""
        assert is_bcrypt_hash("$2b$12$abcdefghijklmnopqrstuvwxyz")
        assert is_bcrypt_hash("$2a$10$abcdefghijklmnopqrstuvwxyz")
        assert is_bcrypt_hash("$2y$12$abcdefghijklmnopqrstuvwxyz")

    def test_is_bcrypt_hash_false(self):
        """Non-bcrypt hashes are correctly identified."""
        # SHA-256 hex hash
        assert not is_bcrypt_hash("a" * 64)
        assert not is_bcrypt_hash("abc123")

    def test_verify_api_key_legacy_valid(self):
        """Legacy SHA-256 verification works."""
        import hashlib
        key = "llmc_" + "a" * 32
        # Create a legacy SHA-256 hash
        salt = key[:12]
        salted = f"{salt}:{key}"
        legacy_hash = hashlib.sha256(salted.encode()).hexdigest()
        assert verify_api_key_legacy(key, legacy_hash)

    def test_verify_api_key_legacy_invalid(self):
        """Legacy verification rejects invalid keys."""
        import hashlib
        key = "llmc_" + "a" * 32
        wrong_key = "llmc_" + "b" * 32
        salt = key[:12]
        salted = f"{salt}:{key}"
        legacy_hash = hashlib.sha256(salted.encode()).hexdigest()
        assert not verify_api_key_legacy(wrong_key, legacy_hash)

    def test_verify_api_key_auto_bcrypt(self):
        """Auto verification detects and verifies bcrypt hashes."""
        key = "llmc_" + "a" * 32
        bcrypt_hash = hash_api_key(key)
        assert verify_api_key_auto(key, bcrypt_hash)

    def test_verify_api_key_auto_legacy(self):
        """Auto verification detects and verifies legacy SHA-256 hashes."""
        import hashlib
        key = "llmc_" + "a" * 32
        salt = key[:12]
        salted = f"{salt}:{key}"
        legacy_hash = hashlib.sha256(salted.encode()).hexdigest()
        assert verify_api_key_auto(key, legacy_hash)


class TestAPIKeyService:
    """Tests for API key service."""

    @pytest.fixture
    def service(self, temp_db):
        """Get service with test database."""
        return APIKeyService(default_rate_limit=60)

    def test_create_key(self, service):
        """Create a new API key."""
        request = APIKeyCreate(name="Test Key")
        result = service.create_key(request)

        assert result.name == "Test Key"
        assert result.api_key.startswith(KEY_PREFIX)
        assert result.key_prefix == result.api_key[:12]
        assert result.is_active is True
        assert "read" in result.permissions
        assert "write" in result.permissions

    def test_create_key_with_permissions(self, service):
        """Create key with specific permissions."""
        request = APIKeyCreate(
            name="Admin Key",
            permissions=[Permission.READ, Permission.ADMIN],
        )
        result = service.create_key(request)

        assert "read" in result.permissions
        assert "admin" in result.permissions
        assert "write" not in result.permissions

    def test_create_key_with_expiration(self, service):
        """Create key with expiration."""
        request = APIKeyCreate(name="Expiring Key", expires_in_days=30)
        result = service.create_key(request)

        assert result.expires_at is not None
        # Should expire roughly 30 days from now
        now = datetime.now(timezone.utc)
        # Make expires_at timezone-aware if it isn't
        expires_at = result.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        days_until_expiry = (expires_at - now).days
        assert 29 <= days_until_expiry <= 30

    def test_validate_key_success(self, service):
        """Valid key passes validation."""
        request = APIKeyCreate(name="Test Key")
        created = service.create_key(request)

        auth = service.validate_key(created.api_key)

        assert auth.key_prefix == created.key_prefix
        assert Permission.READ in auth.permissions
        assert auth.rate_limit == 60

    def test_validate_key_invalid_format(self, service):
        """Invalid format raises error."""
        with pytest.raises(InvalidAPIKeyError):
            service.validate_key("not-a-valid-key")

    def test_validate_key_nonexistent(self, service):
        """Nonexistent key raises error."""
        with pytest.raises(InvalidAPIKeyError):
            service.validate_key("llmc_" + "x" * 32)

    def test_validate_key_revoked(self, service):
        """Revoked key raises error."""
        request = APIKeyCreate(name="Test Key")
        created = service.create_key(request)

        # Revoke the key
        service.revoke_key(created.id)

        with pytest.raises(RevokedAPIKeyError):
            service.validate_key(created.api_key)

    def test_validate_key_permission_check(self, service):
        """Key without required permission raises error."""
        request = APIKeyCreate(
            name="Read Only Key",
            permissions=[Permission.READ],
        )
        created = service.create_key(request)

        # Should succeed for read
        auth = service.validate_key(created.api_key, required_permission=Permission.READ)
        assert auth is not None

        # Should fail for admin
        with pytest.raises(InsufficientPermissionsError):
            service.validate_key(created.api_key, required_permission=Permission.ADMIN)

    def test_list_keys(self, service):
        """List API keys."""
        # Create a few keys
        service.create_key(APIKeyCreate(name="Key 1"))
        service.create_key(APIKeyCreate(name="Key 2"))

        keys = service.list_keys()

        assert len(keys) >= 2
        # Should not include full API key
        for key in keys:
            assert not hasattr(key, "api_key") or key.api_key is None

    def test_list_keys_exclude_inactive(self, service):
        """List only active keys by default."""
        key1 = service.create_key(APIKeyCreate(name="Active Key"))
        key2 = service.create_key(APIKeyCreate(name="Revoked Key"))

        # Revoke one key
        service.revoke_key(key2.id)

        active_keys = service.list_keys(include_inactive=False)
        all_keys = service.list_keys(include_inactive=True)

        assert len(all_keys) > len(active_keys)

    def test_revoke_key(self, service):
        """Revoke an API key."""
        created = service.create_key(APIKeyCreate(name="Test Key"))

        success = service.revoke_key(created.id)

        assert success is True
        # Key should no longer be valid
        with pytest.raises(RevokedAPIKeyError):
            service.validate_key(created.api_key)

    def test_revoke_nonexistent_key(self, service):
        """Revoking nonexistent key returns False."""
        success = service.revoke_key(99999)
        assert success is False

    def test_delete_key(self, service):
        """Delete an API key permanently."""
        created = service.create_key(APIKeyCreate(name="Test Key"))

        success = service.delete_key(created.id)

        assert success is True
        # Key should be gone entirely
        with pytest.raises(InvalidAPIKeyError):
            service.validate_key(created.api_key)

    def test_rate_limit_override(self, service):
        """Custom rate limit is respected."""
        request = APIKeyCreate(name="High Rate Key", rate_limit_override=1000)
        created = service.create_key(request)

        auth = service.validate_key(created.api_key)

        assert auth.rate_limit == 1000


class TestAuthenticationAPI:
    """Tests for authentication API endpoints."""

    def test_health_endpoint(self, test_client):
        """Health endpoint is accessible without auth."""
        response = test_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_root_endpoint(self, test_client):
        """Root endpoint is accessible without auth."""
        response = test_client.get("/")
        assert response.status_code == 200

    def test_api_endpoints_work_in_test_mode(self, test_client, conversation_id):
        """API endpoints work when auth is bypassed (test mode)."""
        # In test mode, auth is bypassed
        response = test_client.get(f"/api/conversations/{conversation_id}")
        assert response.status_code == 200

    def test_auth_me_returns_none_in_test_mode(self, test_client):
        """Auth me endpoint returns 401 when auth is None (test mode)."""
        # In test mode with bypass, auth is None so this should return 401
        response = test_client.get("/api/auth/me")
        assert response.status_code == 401
