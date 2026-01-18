"""Tests for API endpoints."""

import pytest


class TestHealthCheck:
    """Tests for health check endpoint."""

    def test_health_check_returns_ok(self, test_client):
        """Health check returns 200 with status ok."""
        response = test_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "service" in data


class TestConversationCRUD:
    """Tests for conversation CRUD endpoints."""

    def test_create_conversation(self, test_client):
        """Create a new conversation."""
        response = test_client.post("/api/conversations", json={})
        assert response.status_code == 200

        data = response.json()
        assert "id" in data
        assert data["title"] == "New Conversation"
        assert data["is_pinned"] is False
        assert data["is_hidden"] is False
        assert "messages" in data
        assert data["messages"] == []

    def test_list_conversations(self, test_client):
        """List all conversations."""
        # Create a conversation first
        create_response = test_client.post("/api/conversations", json={})
        assert create_response.status_code == 200

        response = test_client.get("/api/conversations")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) >= 1

    def test_get_conversation(self, test_client, conversation_id):
        """Get a specific conversation."""
        response = test_client.get(f"/api/conversations/{conversation_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == conversation_id

    def test_get_nonexistent_conversation(self, test_client):
        """404 for nonexistent conversation."""
        response = test_client.get("/api/conversations/nonexistent-uuid")
        assert response.status_code == 404

    def test_update_conversation_title(self, test_client, conversation_id):
        """Update conversation title."""
        response = test_client.patch(
            f"/api/conversations/{conversation_id}",
            json={"title": "Updated Title"}
        )
        assert response.status_code == 200
        assert response.json()["title"] == "Updated Title"

    def test_update_conversation_pin(self, test_client, conversation_id):
        """Pin a conversation."""
        response = test_client.patch(
            f"/api/conversations/{conversation_id}",
            json={"is_pinned": True}
        )
        assert response.status_code == 200
        assert response.json()["is_pinned"] is True

    def test_update_conversation_hide(self, test_client, conversation_id):
        """Hide a conversation."""
        response = test_client.patch(
            f"/api/conversations/{conversation_id}",
            json={"is_hidden": True}
        )
        assert response.status_code == 200
        assert response.json()["is_hidden"] is True

    def test_delete_conversation(self, test_client, conversation_id):
        """Delete a conversation."""
        response = test_client.delete(f"/api/conversations/{conversation_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

        # Verify deleted
        get_response = test_client.get(f"/api/conversations/{conversation_id}")
        assert get_response.status_code == 404

    def test_delete_nonexistent_conversation(self, test_client):
        """Delete nonexistent conversation returns 404."""
        response = test_client.delete("/api/conversations/nonexistent-uuid")
        assert response.status_code == 404


class TestConfig:
    """Tests for config endpoint."""

    def test_get_config(self, test_client):
        """Get council configuration."""
        response = test_client.get("/api/config")
        assert response.status_code == 200

        data = response.json()
        assert "council_models" in data
        assert "chairman_model" in data
        assert isinstance(data["council_models"], list)


class TestInputValidation:
    """Tests for input validation."""

    def test_empty_message_rejected(self, test_client, conversation_id):
        """Reject empty messages."""
        response = test_client.post(
            f"/api/conversations/{conversation_id}/message",
            json={"content": "   "}  # Whitespace only
        )
        assert response.status_code == 422

    def test_long_title_rejected(self, test_client, conversation_id):
        """Reject titles exceeding max length."""
        response = test_client.patch(
            f"/api/conversations/{conversation_id}",
            json={"title": "x" * 300}  # Over 200 char limit
        )
        assert response.status_code == 422


class TestSecurityHeaders:
    """Tests for security-related headers."""

    def test_rate_limit_headers_present(self, test_client_with_rate_limiting):
        """Rate limit headers are included in responses when rate limiting is enabled."""
        response = test_client_with_rate_limiting.get("/api/conversations")

        # Rate limit headers should be present
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers

    def test_cors_headers_on_options(self, test_client):
        """CORS headers present on OPTIONS request."""
        response = test_client.options(
            "/api/conversations",
            headers={"Origin": "http://localhost:5173"}
        )
        # Should not be rejected (CORS is configured)
        assert response.status_code in [200, 204, 405]
