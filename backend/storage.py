"""
Storage facade for LLM Council conversations.

This module provides backward-compatible functions that now use SQLite
instead of JSON files. The public API remains unchanged.
"""

from typing import List, Dict, Any, Optional
import uuid

from .database import init_database
from .database.repositories import ConversationRepository, MessageRepository

# Initialize database on module import
init_database()

# Singleton repository instances
_conv_repo = ConversationRepository()
_msg_repo = MessageRepository()


def create_conversation(conversation_id: str = None) -> Dict[str, Any]:
    """
    Create a new conversation.

    Args:
        conversation_id: Optional ID (generated if not provided)

    Returns:
        New conversation dict
    """
    # Note: The repository generates its own ID, but we accept one for compatibility
    # If an ID is provided, we need to handle it specially
    if conversation_id:
        # For backward compatibility, create with the provided ID
        # This requires direct database access
        from .database.connection import transaction
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        with transaction() as conn:
            conn.execute(
                """INSERT INTO conversations (id, title, created_at, updated_at)
                   VALUES (?, 'New Conversation', ?, ?)""",
                (conversation_id, now, now)
            )
        return _conv_repo.get(conversation_id)

    return _conv_repo.create()


def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    """
    Load a conversation from storage.

    Args:
        conversation_id: Unique identifier for the conversation

    Returns:
        Conversation dict or None if not found
    """
    return _conv_repo.get(conversation_id)


def save_conversation(conversation: Dict[str, Any]) -> None:
    """
    Save a conversation to storage.

    Note: This is a legacy function. With SQLite, data is saved automatically
    via add_user_message/add_assistant_message. This function now only
    updates metadata fields.

    Args:
        conversation: Conversation dict to save
    """
    conv_id = conversation.get("id")
    if not conv_id:
        return

    # Update metadata fields if they exist
    _conv_repo.update(
        conv_id,
        title=conversation.get("title"),
        is_pinned=conversation.get("is_pinned"),
        is_hidden=conversation.get("is_hidden")
    )


def list_conversations() -> List[Dict[str, Any]]:
    """
    List all conversations (metadata only).

    Returns:
        List of conversation metadata dicts, sorted by pinned then updated
    """
    return _conv_repo.list_all(include_hidden=True)


def add_user_message(
    conversation_id: str,
    content: str,
    images: List[str] = None
) -> None:
    """
    Add a user message to a conversation.

    Args:
        conversation_id: Conversation identifier
        content: Message content
        images: Optional list of base64 image data (stored in content for now)

    Raises:
        ValueError: If conversation not found
    """
    # For now, embed images in content if provided
    # TODO: Add proper image storage table if needed
    full_content = content
    if images:
        # Store images as JSON in content for backward compatibility
        import json
        full_content = json.dumps({"content": content, "images": images})

    result = _msg_repo.add_user_message(conversation_id, full_content)
    if result is None:
        raise ValueError(f"Conversation {conversation_id} not found")


def add_assistant_message(
    conversation_id: str,
    stage1: List[Dict[str, Any]],
    stage2: List[Dict[str, Any]],
    stage3: Dict[str, Any],
    metadata: Dict[str, Any] = None
) -> None:
    """
    Add an assistant message with all 3 stages to a conversation.

    Args:
        conversation_id: Conversation identifier
        stage1: List of individual model responses
        stage2: List of model rankings
        stage3: Final synthesized response
        metadata: Optional deliberation metadata (label_to_model, aggregate_rankings, etc.)

    Raises:
        ValueError: If conversation not found
    """
    result = _msg_repo.add_assistant_message(
        conversation_id,
        stage1,
        stage2,
        stage3,
        metadata
    )
    if result is None:
        raise ValueError(f"Conversation {conversation_id} not found")


def update_conversation_field(conversation_id: str, field: str, value: Any) -> bool:
    """
    Update a specific field of a conversation.

    Args:
        conversation_id: Conversation identifier
        field: Field name to update (title, is_pinned, is_hidden)
        value: New value

    Returns:
        True if updated, False if not found
    """
    result = _conv_repo.update(conversation_id, **{field: value})
    return result is not None


def delete_conversation(conversation_id: str) -> bool:
    """
    Delete a conversation.

    Args:
        conversation_id: Conversation identifier

    Returns:
        True if deleted, False if not found
    """
    return _conv_repo.delete(conversation_id)


# Legacy compatibility - these functions are no longer needed but kept for compatibility
def ensure_data_dir() -> None:
    """Legacy function - data directory is now managed by database module."""
    pass


def get_conversation_path(conversation_id: str) -> str:
    """Legacy function - returns empty string as JSON files are no longer used."""
    return ""
