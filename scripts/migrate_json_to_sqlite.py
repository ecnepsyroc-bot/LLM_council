#!/usr/bin/env python3
"""
Migrate conversations from JSON files to SQLite database.

This script imports existing JSON conversations into the SQLite storage,
with full verification and rollback support.

Usage:
    python scripts/migrate_json_to_sqlite.py [--dry-run] [--verify] [--force]
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database.connection import get_connection, init_database, transaction


# Configure logging
def setup_logging(log_file: Path = None):
    """Setup logging to console and optionally to file."""
    handlers = [logging.StreamHandler()]

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=handlers
    )
    return logging.getLogger(__name__)


def parse_datetime(dt_str: str) -> str:
    """Parse datetime string to ISO format."""
    if not dt_str:
        return datetime.now(timezone.utc).isoformat()

    try:
        if 'T' in dt_str:
            return dt_str
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        return dt.isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


def get_json_conversations(json_dir: Path) -> list:
    """Load all JSON conversation files."""
    if not json_dir.exists():
        return []

    conversations = []
    for json_file in sorted(json_dir.glob("*.json")):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                data['_source_file'] = str(json_file)
                conversations.append(data)
        except Exception as e:
            logging.error(f"Failed to load {json_file}: {e}")

    return conversations


def conversation_exists(conn, conv_id: str) -> bool:
    """Check if conversation already exists in database."""
    result = conn.execute(
        "SELECT id FROM conversations WHERE id = ?",
        (conv_id,)
    ).fetchone()
    return result is not None


def migrate_conversation(conn, data: dict, dry_run: bool = False) -> dict:
    """
    Migrate a single conversation to SQLite.

    Returns dict with migration status and details.
    """
    conv_id = data.get('id', Path(data.get('_source_file', '')).stem)
    result = {
        'id': conv_id,
        'status': 'pending',
        'messages_migrated': 0,
        'stage1_migrated': 0,
        'stage2_migrated': 0,
        'stage3_migrated': 0,
        'error': None
    }

    try:
        # Check if already exists
        if conversation_exists(conn, conv_id):
            result['status'] = 'skipped'
            result['error'] = 'Already exists'
            return result

        if dry_run:
            result['status'] = 'dry_run'
            result['messages_migrated'] = len(data.get('messages', []))
            return result

        # Extract data
        created_at = parse_datetime(data.get('created_at', ''))
        updated_at = parse_datetime(data.get('updated_at', created_at))
        title = data.get('title', 'Imported Conversation')
        messages = data.get('messages', [])
        is_pinned = data.get('is_pinned', False)
        is_hidden = data.get('is_hidden', False)

        # Insert conversation
        conn.execute(
            """INSERT INTO conversations
               (id, title, created_at, updated_at, is_pinned, is_hidden, message_count)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (conv_id, title, created_at, updated_at, is_pinned, is_hidden, len(messages))
        )

        # Insert messages
        for i, msg in enumerate(messages):
            role = msg.get('role', 'user')
            msg_id = f"{conv_id}-{i}"
            msg_created = parse_datetime(msg.get('created_at', created_at))

            conn.execute(
                """INSERT INTO messages (id, conversation_id, role, created_at)
                   VALUES (?, ?, ?, ?)""",
                (msg_id, conv_id, role, msg_created)
            )
            result['messages_migrated'] += 1

            if role == 'user':
                content = msg.get('content', '')
                conn.execute(
                    "UPDATE messages SET content = ? WHERE id = ?",
                    (content, msg_id)
                )

            elif role == 'assistant':
                stage1 = msg.get('stage1', [])
                stage2 = msg.get('stage2', [])
                stage3 = msg.get('stage3', {})

                # Insert stage1 responses
                for j, resp in enumerate(stage1):
                    conn.execute(
                        """INSERT INTO stage1_responses
                           (id, message_id, model, response, confidence)
                           VALUES (?, ?, ?, ?, ?)""",
                        (
                            f"{msg_id}-s1-{j}",
                            msg_id,
                            resp.get('model', 'unknown'),
                            resp.get('response', ''),
                            resp.get('confidence')
                        )
                    )
                    result['stage1_migrated'] += 1

                # Insert stage2 rankings
                for j, rank in enumerate(stage2):
                    parsed = rank.get('parsed_ranking', [])
                    conn.execute(
                        """INSERT INTO stage2_rankings
                           (id, message_id, model, ranking_text, parsed_ranking)
                           VALUES (?, ?, ?, ?, ?)""",
                        (
                            f"{msg_id}-s2-{j}",
                            msg_id,
                            rank.get('model', 'unknown'),
                            rank.get('ranking', ''),
                            json.dumps(parsed)
                        )
                    )
                    result['stage2_migrated'] += 1

                # Insert stage3 synthesis
                if stage3:
                    conn.execute(
                        """INSERT INTO stage3_synthesis
                           (id, message_id, model, synthesis)
                           VALUES (?, ?, ?, ?)""",
                        (
                            f"{msg_id}-s3",
                            msg_id,
                            stage3.get('model', 'unknown'),
                            stage3.get('response', '')
                        )
                    )
                    result['stage3_migrated'] += 1

        result['status'] = 'migrated'

    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)

    return result


def update_message_counts(conn):
    """Update message counts for all conversations."""
    conn.execute('''
        UPDATE conversations
        SET message_count = (
            SELECT COUNT(*) FROM messages
            WHERE messages.conversation_id = conversations.id
        )
    ''')


def verify_migration(conn, json_dir: Path) -> dict:
    """Verify migration integrity."""
    report = {
        'json_count': 0,
        'db_count': 0,
        'json_messages': 0,
        'db_messages': 0,
        'missing_in_db': [],
        'orphaned_in_db': [],
        'message_count_mismatches': [],
        'passed': True
    }

    # Count JSON files
    json_convs = get_json_conversations(json_dir)
    report['json_count'] = len(json_convs)
    report['json_messages'] = sum(len(c.get('messages', [])) for c in json_convs)
    json_ids = {c.get('id', Path(c.get('_source_file', '')).stem) for c in json_convs}

    # Count DB records
    report['db_count'] = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
    report['db_messages'] = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]

    # Find missing
    db_ids = {row[0] for row in conn.execute("SELECT id FROM conversations").fetchall()}
    report['missing_in_db'] = list(json_ids - db_ids)
    report['orphaned_in_db'] = list(db_ids - json_ids)

    # Check message counts
    for conv_id in db_ids:
        stored_count = conn.execute(
            "SELECT message_count FROM conversations WHERE id = ?",
            (conv_id,)
        ).fetchone()[0]

        actual_count = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE conversation_id = ?",
            (conv_id,)
        ).fetchone()[0]

        if stored_count != actual_count:
            report['message_count_mismatches'].append({
                'id': conv_id,
                'stored': stored_count,
                'actual': actual_count
            })

    # Determine pass/fail
    if report['missing_in_db'] or report['message_count_mismatches']:
        report['passed'] = False

    return report


def print_report(results: list, verify_report: dict = None):
    """Print migration report."""
    print("\n" + "=" * 60)
    print("MIGRATION REPORT")
    print("=" * 60)

    # Count by status
    by_status = {}
    for r in results:
        status = r['status']
        by_status[status] = by_status.get(status, 0) + 1

    print(f"\nConversations processed: {len(results)}")
    for status, count in sorted(by_status.items()):
        print(f"  {status}: {count}")

    # Totals
    total_messages = sum(r['messages_migrated'] for r in results)
    total_stage1 = sum(r['stage1_migrated'] for r in results)
    total_stage2 = sum(r['stage2_migrated'] for r in results)
    total_stage3 = sum(r['stage3_migrated'] for r in results)

    print(f"\nData migrated:")
    print(f"  Messages: {total_messages}")
    print(f"  Stage 1 responses: {total_stage1}")
    print(f"  Stage 2 rankings: {total_stage2}")
    print(f"  Stage 3 syntheses: {total_stage3}")

    # Errors
    errors = [r for r in results if r['status'] == 'error']
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors:
            print(f"  {e['id']}: {e['error']}")

    # Verification
    if verify_report:
        print("\n" + "-" * 60)
        print("VERIFICATION")
        print("-" * 60)
        print(f"JSON files: {verify_report['json_count']}")
        print(f"DB conversations: {verify_report['db_count']}")
        print(f"JSON messages: {verify_report['json_messages']}")
        print(f"DB messages: {verify_report['db_messages']}")

        if verify_report['missing_in_db']:
            print(f"\nMissing in DB: {verify_report['missing_in_db']}")

        if verify_report['message_count_mismatches']:
            print(f"\nMessage count mismatches:")
            for m in verify_report['message_count_mismatches']:
                print(f"  {m['id']}: stored={m['stored']}, actual={m['actual']}")

        status = "PASSED" if verify_report['passed'] else "FAILED"
        print(f"\nVerification: {status}")

    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Migrate JSON conversations to SQLite")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be migrated")
    parser.add_argument("--verify", action="store_true", help="Verify migration after completion")
    parser.add_argument("--force", action="store_true", help="Re-migrate existing conversations")
    parser.add_argument("--json-dir", type=Path, default=Path("data/conversations"),
                        help="JSON conversations directory")
    args = parser.parse_args()

    # Setup logging
    log_file = Path("logs") / f"migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    logger = setup_logging(log_file if not args.dry_run else None)

    logger.info("=" * 60)
    logger.info("JSON to SQLite Migration")
    logger.info("=" * 60)

    # Initialize database
    init_database()

    # Get JSON conversations
    json_dir = Path(__file__).parent.parent / args.json_dir
    conversations = get_json_conversations(json_dir)
    logger.info(f"Found {len(conversations)} JSON conversation files")

    if not conversations:
        logger.info("No conversations to migrate")
        return 0

    # Migrate
    results = []
    conn = get_connection()

    for conv in conversations:
        conv_id = conv.get('id', Path(conv.get('_source_file', '')).stem)

        # Handle force flag
        if args.force and not args.dry_run:
            if conversation_exists(conn, conv_id):
                # Delete existing
                with transaction() as tx:
                    tx.execute("DELETE FROM stage3_synthesis WHERE message_id IN (SELECT id FROM messages WHERE conversation_id = ?)", (conv_id,))
                    tx.execute("DELETE FROM stage2_rankings WHERE message_id IN (SELECT id FROM messages WHERE conversation_id = ?)", (conv_id,))
                    tx.execute("DELETE FROM stage1_responses WHERE message_id IN (SELECT id FROM messages WHERE conversation_id = ?)", (conv_id,))
                    tx.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
                    tx.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
                logger.info(f"Deleted existing: {conv_id[:8]}...")

        # Migrate
        if args.dry_run:
            result = migrate_conversation(conn, conv, dry_run=True)
        else:
            with transaction() as tx:
                result = migrate_conversation(tx, conv, dry_run=False)

        results.append(result)

        status_icon = {
            'migrated': '✓',
            'skipped': '○',
            'dry_run': '?',
            'error': '✗'
        }.get(result['status'], '?')

        logger.info(f"  [{status_icon}] {conv_id[:8]}... - {result['status']} ({result['messages_migrated']} messages)")

    # Update message counts
    if not args.dry_run:
        with transaction() as tx:
            update_message_counts(tx)
        logger.info("Updated message counts")

    # Verify
    verify_report = None
    if args.verify and not args.dry_run:
        verify_report = verify_migration(conn, json_dir)

    # Print report
    print_report(results, verify_report)

    if log_file and not args.dry_run:
        logger.info(f"Log saved to: {log_file}")

    # Return exit code
    if verify_report and not verify_report['passed']:
        return 1
    if any(r['status'] == 'error' for r in results):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
