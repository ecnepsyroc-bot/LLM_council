"""Repository for message operations."""

import json
from datetime import datetime, timezone
from typing import Optional

from ..connection import get_connection, transaction


class MessageRepository:
    """Repository for message database operations."""

    def add_user_message(self, conv_id: str, content: str) -> Optional[int]:
        """
        Add a user message to a conversation.

        Args:
            conv_id: The conversation UUID
            content: The message content

        Returns:
            The message ID, or None if conversation not found
        """
        now = datetime.now(timezone.utc).isoformat()

        with transaction() as conn:
            # Verify conversation exists
            exists = conn.execute(
                "SELECT 1 FROM conversations WHERE id = ?", (conv_id,)
            ).fetchone()

            if not exists:
                return None

            cursor = conn.execute(
                """INSERT INTO messages (conversation_id, role, content, created_at)
                   VALUES (?, 'user', ?, ?)""",
                (conv_id, content, now)
            )

            # Update conversation
            conn.execute(
                """UPDATE conversations
                   SET message_count = message_count + 1, updated_at = ?
                   WHERE id = ?""",
                (now, conv_id)
            )

            return cursor.lastrowid

    def add_assistant_message(
        self,
        conv_id: str,
        stage1: list[dict],
        stage2: list[dict],
        stage3: dict,
        metadata: Optional[dict] = None
    ) -> Optional[int]:
        """
        Add an assistant message with all stage data.

        Args:
            conv_id: The conversation UUID
            stage1: List of Stage 1 responses
            stage2: List of Stage 2 rankings
            stage3: Stage 3 synthesis result
            metadata: Optional deliberation metadata

        Returns:
            The message ID, or None if conversation not found
        """
        now = datetime.now(timezone.utc).isoformat()

        with transaction() as conn:
            # Verify conversation exists
            exists = conn.execute(
                "SELECT 1 FROM conversations WHERE id = ?", (conv_id,)
            ).fetchone()

            if not exists:
                return None

            # Insert message
            cursor = conn.execute(
                """INSERT INTO messages (conversation_id, role, created_at)
                   VALUES (?, 'assistant', ?)""",
                (conv_id, now)
            )
            message_id = cursor.lastrowid

            # Insert Stage 1 responses
            for resp in stage1:
                conn.execute(
                    """INSERT INTO stage1_responses
                       (message_id, model, response, confidence, base_model, sample_id, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        message_id,
                        resp["model"],
                        resp["response"],
                        resp.get("confidence"),
                        resp.get("base_model"),
                        resp.get("sample_id"),
                        now
                    )
                )

            # Insert Stage 2 rankings
            for ranking in stage2:
                conn.execute(
                    """INSERT INTO stage2_rankings
                       (message_id, evaluator_model, raw_ranking, parsed_ranking,
                        debate_round, rubric_scores, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        message_id,
                        ranking["model"],
                        ranking["ranking"],
                        json.dumps(ranking.get("parsed_ranking")) if ranking.get("parsed_ranking") else None,
                        ranking.get("debate_round", 1),
                        json.dumps(ranking.get("rubric_scores")) if ranking.get("rubric_scores") else None,
                        now
                    )
                )

            # Insert Stage 3 synthesis
            if stage3:
                conn.execute(
                    """INSERT INTO stage3_synthesis
                       (message_id, chairman_model, response, meta_evaluation, created_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        message_id,
                        stage3["model"],
                        stage3["response"],
                        stage3.get("meta_evaluation"),
                        now
                    )
                )

            # Insert metadata if provided
            if metadata:
                conn.execute(
                    """INSERT INTO deliberation_metadata
                       (message_id, label_to_model, aggregate_rankings, consensus,
                        voting_method, features, stage1_consensus, debate_history, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        message_id,
                        json.dumps(metadata.get("label_to_model", {})),
                        json.dumps(metadata.get("aggregate_rankings")) if metadata.get("aggregate_rankings") else None,
                        json.dumps(metadata.get("consensus")) if metadata.get("consensus") else None,
                        metadata.get("voting_method"),
                        json.dumps(metadata.get("features")) if metadata.get("features") else None,
                        json.dumps(metadata.get("stage1_consensus")) if metadata.get("stage1_consensus") else None,
                        json.dumps(metadata.get("debate_history")) if metadata.get("debate_history") else None,
                        now
                    )
                )

            # Update conversation
            conn.execute(
                """UPDATE conversations
                   SET message_count = message_count + 1, updated_at = ?
                   WHERE id = ?""",
                (now, conv_id)
            )

            return message_id

    def get_metadata(self, message_id: int) -> Optional[dict]:
        """
        Get deliberation metadata for a message.

        Args:
            message_id: The message ID

        Returns:
            Metadata dict or None
        """
        conn = get_connection()
        row = conn.execute(
            """SELECT label_to_model, aggregate_rankings, consensus,
                      voting_method, features, stage1_consensus, debate_history
               FROM deliberation_metadata WHERE message_id = ?""",
            (message_id,)
        ).fetchone()

        if not row:
            return None

        result = {}
        row_dict = dict(row)

        # Parse JSON fields
        for field in ["label_to_model", "aggregate_rankings", "consensus",
                      "features", "stage1_consensus", "debate_history"]:
            if row_dict.get(field):
                result[field] = json.loads(row_dict[field])

        if row_dict.get("voting_method"):
            result["voting_method"] = row_dict["voting_method"]

        return result
