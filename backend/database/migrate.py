"""Migration script from JSON files to SQLite database."""

import json
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.database.connection import init_database, transaction, get_connection, DATABASE_PATH


def migrate_json_to_sqlite(json_dir: Path = None, verbose: bool = True) -> dict:
    """
    Migrate all JSON conversations to SQLite database.

    Args:
        json_dir: Path to JSON conversations directory (default: data/conversations)
        verbose: Whether to print progress

    Returns:
        Dict with migration statistics
    """
    if json_dir is None:
        json_dir = Path(__file__).parent.parent.parent / "data" / "conversations"

    stats = {
        "total": 0,
        "migrated": 0,
        "skipped": 0,
        "failed": 0,
        "errors": []
    }

    if not json_dir.exists():
        if verbose:
            print(f"No JSON directory found at {json_dir}")
        return stats

    json_files = list(json_dir.glob("*.json"))
    stats["total"] = len(json_files)

    if verbose:
        print(f"Found {len(json_files)} JSON files to migrate")
        print(f"Database path: {DATABASE_PATH}")
        print()

    # Initialize database schema
    init_database()

    conn = get_connection()

    for json_file in json_files:
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                conv = json.load(f)

            conv_id = conv.get("id")
            if not conv_id:
                if verbose:
                    print(f"  SKIP: {json_file.name} - No ID found")
                stats["skipped"] += 1
                continue

            # Check if already migrated
            existing = conn.execute(
                "SELECT 1 FROM conversations WHERE id = ?", (conv_id,)
            ).fetchone()

            if existing:
                if verbose:
                    print(f"  SKIP: {json_file.name} - Already exists")
                stats["skipped"] += 1
                continue

            # Migrate conversation
            _migrate_conversation(conv, verbose)
            stats["migrated"] += 1

            if verbose:
                print(f"  OK: {json_file.name}")

        except Exception as e:
            stats["failed"] += 1
            stats["errors"].append({"file": json_file.name, "error": str(e)})
            if verbose:
                print(f"  FAIL: {json_file.name} - {e}")

    if verbose:
        print()
        print(f"Migration complete:")
        print(f"  Migrated: {stats['migrated']}")
        print(f"  Skipped:  {stats['skipped']}")
        print(f"  Failed:   {stats['failed']}")

    return stats


def _migrate_conversation(conv: dict, verbose: bool = False) -> None:
    """Migrate a single conversation to SQLite."""
    with transaction() as conn:
        # Insert conversation
        conn.execute(
            """INSERT INTO conversations
               (id, title, created_at, updated_at, is_pinned, is_hidden, message_count)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                conv["id"],
                conv.get("title", "New Conversation"),
                conv.get("created_at", ""),
                conv.get("created_at", ""),  # Use created_at as updated_at initially
                1 if conv.get("is_pinned") else 0,
                1 if conv.get("is_hidden") else 0,
                conv.get("message_count", 0)
            )
        )

        # Insert messages
        for msg in conv.get("messages", []):
            created_at = conv.get("created_at", "")

            if msg["role"] == "user":
                conn.execute(
                    """INSERT INTO messages (conversation_id, role, content, created_at)
                       VALUES (?, 'user', ?, ?)""",
                    (conv["id"], msg.get("content", ""), created_at)
                )
            else:
                # Assistant message
                cursor = conn.execute(
                    """INSERT INTO messages (conversation_id, role, created_at)
                       VALUES (?, 'assistant', ?)""",
                    (conv["id"], created_at)
                )
                message_id = cursor.lastrowid

                # Insert Stage 1 responses
                for resp in msg.get("stage1", []):
                    conn.execute(
                        """INSERT INTO stage1_responses
                           (message_id, model, response, confidence, base_model, sample_id, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (
                            message_id,
                            resp.get("model", ""),
                            resp.get("response", ""),
                            resp.get("confidence"),
                            resp.get("base_model"),
                            resp.get("sample_id"),
                            created_at
                        )
                    )

                # Insert Stage 2 rankings
                for ranking in msg.get("stage2", []):
                    conn.execute(
                        """INSERT INTO stage2_rankings
                           (message_id, evaluator_model, raw_ranking, parsed_ranking,
                            debate_round, rubric_scores, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (
                            message_id,
                            ranking.get("model", ""),
                            ranking.get("ranking", ""),
                            json.dumps(ranking.get("parsed_ranking")) if ranking.get("parsed_ranking") else None,
                            ranking.get("debate_round", 1),
                            json.dumps(ranking.get("rubric_scores")) if ranking.get("rubric_scores") else None,
                            created_at
                        )
                    )

                # Insert Stage 3 synthesis
                stage3 = msg.get("stage3")
                if stage3:
                    conn.execute(
                        """INSERT INTO stage3_synthesis
                           (message_id, chairman_model, response, meta_evaluation, created_at)
                           VALUES (?, ?, ?, ?, ?)""",
                        (
                            message_id,
                            stage3.get("model", ""),
                            stage3.get("response", ""),
                            stage3.get("meta_evaluation"),
                            created_at
                        )
                    )


def verify_migration(verbose: bool = True) -> bool:
    """
    Verify the migration was successful.

    Returns:
        True if verification passes
    """
    conn = get_connection()

    # Get counts
    conv_count = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
    msg_count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    s1_count = conn.execute("SELECT COUNT(*) FROM stage1_responses").fetchone()[0]
    s2_count = conn.execute("SELECT COUNT(*) FROM stage2_rankings").fetchone()[0]
    s3_count = conn.execute("SELECT COUNT(*) FROM stage3_synthesis").fetchone()[0]

    if verbose:
        print("\nDatabase contents:")
        print(f"  Conversations:    {conv_count}")
        print(f"  Messages:         {msg_count}")
        print(f"  Stage 1 responses: {s1_count}")
        print(f"  Stage 2 rankings:  {s2_count}")
        print(f"  Stage 3 syntheses: {s3_count}")

    return conv_count > 0 or msg_count == 0  # OK if empty or has data


if __name__ == "__main__":
    print("=" * 50)
    print("LLM Council: JSON to SQLite Migration")
    print("=" * 50)
    print()

    stats = migrate_json_to_sqlite()
    verify_migration()

    if stats["failed"] > 0:
        print("\nErrors:")
        for err in stats["errors"]:
            print(f"  {err['file']}: {err['error']}")
        sys.exit(1)
