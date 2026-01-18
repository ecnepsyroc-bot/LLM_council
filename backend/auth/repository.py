"""Database operations for API keys."""

import json
from datetime import datetime, timezone
from typing import List, Optional


def _utcnow() -> datetime:
    """Get current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)

from ..database.connection import get_connection, transaction
from .models import APIKeyInDB


class APIKeyRepository:
    """Repository for API key database operations."""

    def create(
        self,
        key_hash: str,
        key_prefix: str,
        name: str,
        expires_at: Optional[datetime] = None,
        permissions: Optional[List[str]] = None,
        rate_limit_override: Optional[int] = None,
    ) -> APIKeyInDB:
        """Create a new API key record."""
        permissions = permissions or ["read", "write", "stream"]

        with transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO api_keys (key_hash, key_prefix, name, expires_at,
                                      permissions, rate_limit_override)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    key_hash,
                    key_prefix,
                    name,
                    expires_at.isoformat() if expires_at else None,
                    json.dumps(permissions),
                    rate_limit_override,
                ),
            )

            return self.get_by_id(cursor.lastrowid)

    def get_by_id(self, key_id: int) -> Optional[APIKeyInDB]:
        """Get API key by ID."""
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM api_keys WHERE id = ?", (key_id,)
        ).fetchone()

        return self._row_to_model(row) if row else None

    def get_by_prefix(self, prefix: str) -> Optional[APIKeyInDB]:
        """Get API key by prefix (for verification)."""
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM api_keys WHERE key_prefix = ?", (prefix,)
        ).fetchone()

        return self._row_to_model(row) if row else None

    def get_by_hash(self, key_hash: str) -> Optional[APIKeyInDB]:
        """Get API key by hash."""
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM api_keys WHERE key_hash = ?", (key_hash,)
        ).fetchone()

        return self._row_to_model(row) if row else None

    def list_all(self, include_inactive: bool = False) -> List[APIKeyInDB]:
        """List all API keys."""
        conn = get_connection()
        query = "SELECT * FROM api_keys"
        if not include_inactive:
            query += " WHERE is_active = 1"
        query += " ORDER BY created_at DESC"

        rows = conn.execute(query).fetchall()
        return [self._row_to_model(row) for row in rows]

    def update_last_used(self, key_id: int) -> None:
        """Update the last_used_at timestamp."""
        conn = get_connection()
        conn.execute(
            "UPDATE api_keys SET last_used_at = ? WHERE id = ?",
            (_utcnow().isoformat(), key_id),
        )
        conn.commit()

    def revoke(self, key_id: int) -> bool:
        """Revoke an API key."""
        with transaction() as conn:
            cursor = conn.execute(
                "UPDATE api_keys SET is_active = 0 WHERE id = ?",
                (key_id,),
            )
            return cursor.rowcount > 0

    def delete(self, key_id: int) -> bool:
        """Permanently delete an API key."""
        with transaction() as conn:
            cursor = conn.execute("DELETE FROM api_keys WHERE id = ?", (key_id,))
            return cursor.rowcount > 0

    def log_usage(
        self,
        api_key_id: int,
        action: str,
        endpoint: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> None:
        """Log API key usage for auditing."""
        conn = get_connection()
        conn.execute(
            """
            INSERT INTO api_key_audit_log
            (api_key_id, action, endpoint, ip_address, user_agent, request_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (api_key_id, action, endpoint, ip_address, user_agent, request_id),
        )
        conn.commit()

    def _row_to_model(self, row) -> APIKeyInDB:
        """Convert database row to Pydantic model."""
        data = dict(row)
        data["permissions"] = (
            json.loads(data["permissions"]) if data["permissions"] else []
        )
        data["metadata"] = (
            json.loads(data["metadata"]) if data.get("metadata") else None
        )
        # Convert is_active from int to bool
        data["is_active"] = bool(data.get("is_active", 1))
        return APIKeyInDB(**data)
