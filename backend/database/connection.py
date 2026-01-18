"""Database connection management with transaction support."""

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

# Database location
DATA_DIR = Path(__file__).parent.parent.parent / "data"
DATABASE_PATH = DATA_DIR / "council.db"

# Thread-local storage for connections
_local = threading.local()


def get_connection() -> sqlite3.Connection:
    """
    Get thread-local database connection.

    Creates a new connection if one doesn't exist for the current thread.
    Uses WAL mode for better concurrency.
    """
    if not hasattr(_local, "connection") or _local.connection is None:
        # Ensure data directory exists
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        _local.connection = sqlite3.connect(
            str(DATABASE_PATH),
            check_same_thread=False,
            timeout=30.0  # Wait up to 30 seconds for locks
        )
        _local.connection.row_factory = sqlite3.Row

        # Enable foreign keys and WAL mode
        _local.connection.execute("PRAGMA foreign_keys = ON")
        _local.connection.execute("PRAGMA journal_mode = WAL")
        _local.connection.execute("PRAGMA busy_timeout = 30000")

    return _local.connection


def close_connection() -> None:
    """Close the thread-local database connection."""
    if hasattr(_local, "connection") and _local.connection is not None:
        _local.connection.close()
        _local.connection = None


@contextmanager
def transaction() -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager for database transactions.

    Automatically commits on success, rolls back on error.

    Usage:
        with transaction() as conn:
            conn.execute("INSERT INTO ...")
            conn.execute("UPDATE ...")
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_database() -> None:
    """
    Initialize database schema.

    Creates all tables if they don't exist.
    Safe to call multiple times.
    """
    schema_path = Path(__file__).parent / "schema.sql"

    conn = get_connection()
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def reset_database() -> None:
    """
    Reset database by dropping all tables and recreating them.

    WARNING: This deletes all data! Only use for testing.
    """
    conn = get_connection()

    # Drop all tables
    tables = [
        "api_key_audit_log",
        "api_keys",
        "deliberation_metadata",
        "stage3_synthesis",
        "stage2_rankings",
        "stage1_responses",
        "messages",
        "conversations"
    ]

    for table in tables:
        conn.execute(f"DROP TABLE IF EXISTS {table}")

    conn.commit()

    # Recreate schema
    init_database()
