"""Repository for conversation CRUD operations."""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from ..connection import get_connection, transaction


class ConversationRepository:
    """Repository for conversation database operations."""

    def create(self, title: str = "New Conversation") -> dict:
        """
        Create a new conversation.

        Args:
            title: Optional title for the conversation

        Returns:
            The created conversation dict with id, title, timestamps, etc.
        """
        conv_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        with transaction() as conn:
            conn.execute(
                """INSERT INTO conversations (id, title, created_at, updated_at)
                   VALUES (?, ?, ?, ?)""",
                (conv_id, title, now, now)
            )

        return self.get(conv_id)

    def get(self, conv_id: str) -> Optional[dict]:
        """
        Get a conversation by ID with all messages and stage data.

        Args:
            conv_id: The conversation UUID

        Returns:
            Full conversation dict with messages, or None if not found
        """
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (conv_id,)
        ).fetchone()

        if not row:
            return None

        conv = dict(row)
        # Convert SQLite integers to booleans
        conv["is_pinned"] = bool(conv["is_pinned"])
        conv["is_hidden"] = bool(conv["is_hidden"])
        conv["messages"] = self._get_messages(conv_id)

        return conv

    def list_all(self, include_hidden: bool = False) -> list[dict]:
        """
        List all conversations (metadata only, no messages).

        Args:
            include_hidden: Whether to include hidden conversations

        Returns:
            List of conversation dicts (without messages)
        """
        conn = get_connection()

        if include_hidden:
            query = """SELECT id, title, created_at, updated_at, is_pinned, is_hidden, message_count
                       FROM conversations
                       ORDER BY is_pinned DESC, updated_at DESC"""
            rows = conn.execute(query).fetchall()
        else:
            query = """SELECT id, title, created_at, updated_at, is_pinned, is_hidden, message_count
                       FROM conversations
                       WHERE is_hidden = 0
                       ORDER BY is_pinned DESC, updated_at DESC"""
            rows = conn.execute(query).fetchall()

        result = []
        for row in rows:
            conv = dict(row)
            conv["is_pinned"] = bool(conv["is_pinned"])
            conv["is_hidden"] = bool(conv["is_hidden"])
            result.append(conv)

        return result

    def update(self, conv_id: str, **fields) -> Optional[dict]:
        """
        Update conversation fields.

        Args:
            conv_id: The conversation UUID
            **fields: Fields to update (title, is_pinned, is_hidden)

        Returns:
            Updated conversation dict, or None if not found
        """
        allowed = {"title", "is_pinned", "is_hidden"}
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}

        if not updates:
            return self.get(conv_id)

        # Convert booleans to integers for SQLite
        for key in ["is_pinned", "is_hidden"]:
            if key in updates:
                updates[key] = 1 if updates[key] else 0

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values())
        values.append(datetime.now(timezone.utc).isoformat())
        values.append(conv_id)

        with transaction() as conn:
            cursor = conn.execute(
                f"UPDATE conversations SET {set_clause}, updated_at = ? WHERE id = ?",
                values
            )
            if cursor.rowcount == 0:
                return None

        return self.get(conv_id)

    def delete(self, conv_id: str) -> bool:
        """
        Delete a conversation and all related data.

        Args:
            conv_id: The conversation UUID

        Returns:
            True if deleted, False if not found
        """
        with transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM conversations WHERE id = ?", (conv_id,)
            )
            return cursor.rowcount > 0

    def increment_message_count(self, conv_id: str) -> None:
        """Increment the message count for a conversation."""
        now = datetime.now(timezone.utc).isoformat()
        with transaction() as conn:
            conn.execute(
                """UPDATE conversations
                   SET message_count = message_count + 1, updated_at = ?
                   WHERE id = ?""",
                (now, conv_id)
            )

    def _get_messages(self, conv_id: str) -> list[dict]:
        """Get all messages for a conversation with full stage data."""
        conn = get_connection()

        rows = conn.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id",
            (conv_id,)
        ).fetchall()

        messages = []
        for row in rows:
            msg = dict(row)

            if msg["role"] == "assistant":
                # Remove content field for assistant messages (it's in stages)
                msg.pop("content", None)
                msg["stage1"] = self._get_stage1(msg["id"])
                msg["stage2"] = self._get_stage2(msg["id"])
                msg["stage3"] = self._get_stage3(msg["id"])

            # Remove internal fields from output
            msg.pop("id", None)
            msg.pop("conversation_id", None)
            msg.pop("created_at", None)

            messages.append(msg)

        return messages

    def _get_stage1(self, message_id: int) -> list[dict]:
        """Get Stage 1 responses for a message."""
        conn = get_connection()
        rows = conn.execute(
            """SELECT model, response, confidence, base_model, sample_id
               FROM stage1_responses WHERE message_id = ?""",
            (message_id,)
        ).fetchall()

        results = []
        for row in rows:
            resp = dict(row)
            # Remove None values for cleaner output
            results.append({k: v for k, v in resp.items() if v is not None})

        return results

    def _get_stage2(self, message_id: int) -> list[dict]:
        """Get Stage 2 rankings for a message."""
        conn = get_connection()
        rows = conn.execute(
            """SELECT evaluator_model as model, raw_ranking as ranking,
                      parsed_ranking, debate_round, rubric_scores
               FROM stage2_rankings WHERE message_id = ?""",
            (message_id,)
        ).fetchall()

        results = []
        for row in rows:
            ranking = dict(row)

            # Parse JSON fields
            if ranking.get("parsed_ranking"):
                ranking["parsed_ranking"] = json.loads(ranking["parsed_ranking"])
            if ranking.get("rubric_scores"):
                ranking["rubric_scores"] = json.loads(ranking["rubric_scores"])

            # Remove None values
            results.append({k: v for k, v in ranking.items() if v is not None})

        return results

    def _get_stage3(self, message_id: int) -> Optional[dict]:
        """Get Stage 3 synthesis for a message."""
        conn = get_connection()
        row = conn.execute(
            """SELECT chairman_model as model, response, meta_evaluation
               FROM stage3_synthesis WHERE message_id = ?""",
            (message_id,)
        ).fetchone()

        if not row:
            return None

        result = dict(row)
        return {k: v for k, v in result.items() if v is not None}
