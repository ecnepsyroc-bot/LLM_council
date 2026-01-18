"""Pytest configuration and shared fixtures."""

import pytest
import tempfile
import os
from pathlib import Path

# Import fixtures for easy access
from .fixtures.responses import (
    SAMPLE_STAGE1_RESPONSES,
    SAMPLE_STAGE1_WITH_CONFIDENCE,
    make_stage1_response,
)
from .fixtures.rankings import (
    SAMPLE_RANKINGS,
    SAMPLE_LABEL_TO_MODEL,
    UNANIMOUS_RANKINGS,
    SPLIT_RANKINGS,
    make_ranking,
)


@pytest.fixture
def sample_responses():
    """Sample Stage 1 responses without confidence."""
    return SAMPLE_STAGE1_RESPONSES.copy()


@pytest.fixture
def sample_responses_with_confidence():
    """Sample Stage 1 responses with confidence scores."""
    return SAMPLE_STAGE1_WITH_CONFIDENCE.copy()


@pytest.fixture
def sample_rankings():
    """Sample Stage 2 rankings."""
    return SAMPLE_RANKINGS.copy()


@pytest.fixture
def sample_label_to_model():
    """Sample label-to-model mapping."""
    return SAMPLE_LABEL_TO_MODEL.copy()


@pytest.fixture
def unanimous_rankings():
    """Rankings with unanimous agreement."""
    return UNANIMOUS_RANKINGS.copy()


@pytest.fixture
def split_rankings():
    """Rankings with no clear winner (circular preferences)."""
    return SPLIT_RANKINGS.copy()


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Create a temporary database for testing."""
    db_path = tmp_path / "test_council.db"
    data_dir = tmp_path

    # Patch the database path and data dir
    import backend.database.connection as conn_module
    monkeypatch.setattr(conn_module, "DATABASE_PATH", db_path)
    monkeypatch.setattr(conn_module, "DATA_DIR", data_dir)

    # Clear any existing thread-local connection
    if hasattr(conn_module._local, "connection"):
        conn_module._local.connection = None

    # Initialize the database
    from backend.database import init_database
    init_database()

    yield db_path

    # Cleanup
    from backend.database import close_connection
    close_connection()


@pytest.fixture
def test_client(temp_db, monkeypatch):
    """FastAPI test client with temporary database and disabled rate limiting."""
    # Set testing environment BEFORE importing app
    monkeypatch.setenv("TESTING", "1")

    # Force reimport of main module to pick up the env var
    import importlib
    import backend.main
    importlib.reload(backend.main)

    from fastapi.testclient import TestClient
    from backend.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture
def conversation_id(test_client):
    """Create a test conversation and return its ID."""
    response = test_client.post("/api/conversations", json={})
    assert response.status_code == 200, f"Failed to create: {response.text}"
    return response.json()["id"]


@pytest.fixture
def test_client_with_rate_limiting(temp_db, monkeypatch):
    """FastAPI test client with rate limiting ENABLED but auth BYPASSED."""
    # Do NOT set TESTING env var - this keeps rate limiting enabled
    monkeypatch.delenv("TESTING", raising=False)
    # But bypass auth for this test
    monkeypatch.setenv("BYPASS_AUTH", "true")

    # Force reimport of main module to pick up the env var change
    import importlib
    import backend.main
    importlib.reload(backend.main)

    from fastapi.testclient import TestClient
    from backend.main import app

    with TestClient(app) as client:
        yield client
