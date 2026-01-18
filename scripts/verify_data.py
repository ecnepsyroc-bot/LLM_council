#!/usr/bin/env python3
"""
Verify data integrity for LLM Council database.

Checks:
- Conversation validity
- Message count accuracy
- Stage data completeness
- Orphaned records
- Data consistency

Usage:
    python scripts/verify_data.py [--fix] [--json] [--verbose]

Exit codes:
    0 = All checks passed
    1 = Warnings found
    2 = Errors found
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database.connection import get_connection, init_database, transaction


def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    return logging.getLogger(__name__)


class DataVerifier:
    """Verify data integrity in the database."""

    def __init__(self, conn, fix: bool = False):
        self.conn = conn
        self.fix = fix
        self.errors = []
        self.warnings = []
        self.fixes = []
        self.stats = {}

    def run_all_checks(self) -> dict:
        """Run all verification checks."""
        self.check_conversations()
        self.check_messages()
        self.check_message_counts()
        self.check_stage1_data()
        self.check_stage2_data()
        self.check_stage3_data()
        self.check_orphaned_records()
        self.check_data_consistency()

        return {
            'stats': self.stats,
            'errors': self.errors,
            'warnings': self.warnings,
            'fixes': self.fixes,
            'passed': len(self.errors) == 0
        }

    def check_conversations(self):
        """Verify all conversations have valid data."""
        logging.info("Checking conversations...")

        # Count conversations
        count = self.conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
        self.stats['conversations'] = count

        # Check for conversations without IDs
        invalid = self.conn.execute(
            "SELECT id FROM conversations WHERE id IS NULL OR id = ''"
        ).fetchall()

        if invalid:
            self.errors.append(f"Found {len(invalid)} conversations with invalid IDs")

        # Check for duplicate IDs
        duplicates = self.conn.execute("""
            SELECT id, COUNT(*) as cnt FROM conversations
            GROUP BY id HAVING cnt > 1
        """).fetchall()

        if duplicates:
            self.errors.append(f"Found {len(duplicates)} duplicate conversation IDs")

        # Check for conversations without titles
        no_title = self.conn.execute(
            "SELECT COUNT(*) FROM conversations WHERE title IS NULL OR title = ''"
        ).fetchone()[0]

        if no_title > 0:
            self.warnings.append(f"Found {no_title} conversations without titles")

        logging.info(f"  Total conversations: {count}")

    def check_messages(self):
        """Verify all messages have valid data."""
        logging.info("Checking messages...")

        # Count messages
        count = self.conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        self.stats['messages'] = count

        # Check for messages without conversation
        orphan_msgs = self.conn.execute("""
            SELECT COUNT(*) FROM messages m
            LEFT JOIN conversations c ON m.conversation_id = c.id
            WHERE c.id IS NULL
        """).fetchone()[0]

        if orphan_msgs > 0:
            self.errors.append(f"Found {orphan_msgs} messages without valid conversation")

        # Check for invalid roles
        invalid_roles = self.conn.execute("""
            SELECT COUNT(*) FROM messages
            WHERE role NOT IN ('user', 'assistant', 'system')
        """).fetchone()[0]

        if invalid_roles > 0:
            self.warnings.append(f"Found {invalid_roles} messages with non-standard roles")

        # Count by role
        role_counts = self.conn.execute("""
            SELECT role, COUNT(*) FROM messages GROUP BY role
        """).fetchall()

        for role, cnt in role_counts:
            self.stats[f'messages_{role}'] = cnt

        logging.info(f"  Total messages: {count}")

    def check_message_counts(self):
        """Verify message counts match actual messages."""
        logging.info("Checking message counts...")

        mismatches = self.conn.execute("""
            SELECT c.id, c.message_count as stored,
                   (SELECT COUNT(*) FROM messages WHERE conversation_id = c.id) as actual
            FROM conversations c
            WHERE c.message_count != (SELECT COUNT(*) FROM messages WHERE conversation_id = c.id)
        """).fetchall()

        if mismatches:
            self.warnings.append(f"Found {len(mismatches)} conversations with incorrect message counts")

            if self.fix:
                with transaction() as tx:
                    tx.execute("""
                        UPDATE conversations
                        SET message_count = (
                            SELECT COUNT(*) FROM messages
                            WHERE messages.conversation_id = conversations.id
                        )
                    """)
                self.fixes.append(f"Fixed message counts for {len(mismatches)} conversations")

        self.stats['message_count_mismatches'] = len(mismatches)
        logging.info(f"  Mismatches: {len(mismatches)}")

    def check_stage1_data(self):
        """Verify Stage 1 response data."""
        logging.info("Checking Stage 1 responses...")

        count = self.conn.execute("SELECT COUNT(*) FROM stage1_responses").fetchone()[0]
        self.stats['stage1_responses'] = count

        # Check for orphaned stage1 responses
        orphaned = self.conn.execute("""
            SELECT COUNT(*) FROM stage1_responses s
            LEFT JOIN messages m ON s.message_id = m.id
            WHERE m.id IS NULL
        """).fetchone()[0]

        if orphaned > 0:
            self.errors.append(f"Found {orphaned} orphaned Stage 1 responses")

        # Check for empty responses
        empty = self.conn.execute(
            "SELECT COUNT(*) FROM stage1_responses WHERE response IS NULL OR response = ''"
        ).fetchone()[0]

        if empty > 0:
            self.warnings.append(f"Found {empty} empty Stage 1 responses")

        # Check assistant messages without stage1
        missing = self.conn.execute("""
            SELECT COUNT(*) FROM messages m
            WHERE m.role = 'assistant'
            AND NOT EXISTS (SELECT 1 FROM stage1_responses WHERE message_id = m.id)
        """).fetchone()[0]

        if missing > 0:
            self.warnings.append(f"Found {missing} assistant messages without Stage 1 data")

        logging.info(f"  Total Stage 1 responses: {count}")

    def check_stage2_data(self):
        """Verify Stage 2 ranking data."""
        logging.info("Checking Stage 2 rankings...")

        count = self.conn.execute("SELECT COUNT(*) FROM stage2_rankings").fetchone()[0]
        self.stats['stage2_rankings'] = count

        # Check for orphaned stage2 rankings
        orphaned = self.conn.execute("""
            SELECT COUNT(*) FROM stage2_rankings s
            LEFT JOIN messages m ON s.message_id = m.id
            WHERE m.id IS NULL
        """).fetchone()[0]

        if orphaned > 0:
            self.errors.append(f"Found {orphaned} orphaned Stage 2 rankings")

        # Check for empty rankings
        empty = self.conn.execute(
            "SELECT COUNT(*) FROM stage2_rankings WHERE ranking_text IS NULL OR ranking_text = ''"
        ).fetchone()[0]

        if empty > 0:
            self.warnings.append(f"Found {empty} empty Stage 2 rankings")

        # Check for unparsed rankings
        unparsed = self.conn.execute(
            "SELECT COUNT(*) FROM stage2_rankings WHERE parsed_ranking IS NULL OR parsed_ranking = '[]'"
        ).fetchone()[0]

        if unparsed > 0:
            self.warnings.append(f"Found {unparsed} Stage 2 rankings without parsed data")

        logging.info(f"  Total Stage 2 rankings: {count}")

    def check_stage3_data(self):
        """Verify Stage 3 synthesis data."""
        logging.info("Checking Stage 3 syntheses...")

        count = self.conn.execute("SELECT COUNT(*) FROM stage3_synthesis").fetchone()[0]
        self.stats['stage3_syntheses'] = count

        # Check for orphaned stage3 syntheses
        orphaned = self.conn.execute("""
            SELECT COUNT(*) FROM stage3_synthesis s
            LEFT JOIN messages m ON s.message_id = m.id
            WHERE m.id IS NULL
        """).fetchone()[0]

        if orphaned > 0:
            self.errors.append(f"Found {orphaned} orphaned Stage 3 syntheses")

        # Check for empty syntheses
        empty = self.conn.execute(
            "SELECT COUNT(*) FROM stage3_synthesis WHERE synthesis IS NULL OR synthesis = ''"
        ).fetchone()[0]

        if empty > 0:
            self.warnings.append(f"Found {empty} empty Stage 3 syntheses")

        # Check assistant messages without stage3
        missing = self.conn.execute("""
            SELECT COUNT(*) FROM messages m
            WHERE m.role = 'assistant'
            AND NOT EXISTS (SELECT 1 FROM stage3_synthesis WHERE message_id = m.id)
        """).fetchone()[0]

        if missing > 0:
            self.warnings.append(f"Found {missing} assistant messages without Stage 3 data")

        logging.info(f"  Total Stage 3 syntheses: {count}")

    def check_orphaned_records(self):
        """Check for orphaned records across all tables."""
        logging.info("Checking for orphaned records...")

        tables = [
            ('stage1_responses', 'message_id', 'messages'),
            ('stage2_rankings', 'message_id', 'messages'),
            ('stage3_synthesis', 'message_id', 'messages'),
            ('messages', 'conversation_id', 'conversations'),
        ]

        total_orphaned = 0
        for table, fk, parent in tables:
            orphaned = self.conn.execute(f"""
                SELECT COUNT(*) FROM {table} t
                LEFT JOIN {parent} p ON t.{fk} = p.id
                WHERE p.id IS NULL
            """).fetchone()[0]

            if orphaned > 0:
                total_orphaned += orphaned

                if self.fix:
                    with transaction() as tx:
                        tx.execute(f"""
                            DELETE FROM {table}
                            WHERE {fk} NOT IN (SELECT id FROM {parent})
                        """)
                    self.fixes.append(f"Deleted {orphaned} orphaned records from {table}")

        self.stats['orphaned_records'] = total_orphaned
        logging.info(f"  Total orphaned records: {total_orphaned}")

    def check_data_consistency(self):
        """Check overall data consistency."""
        logging.info("Checking data consistency...")

        # Check for future dates
        future = self.conn.execute("""
            SELECT COUNT(*) FROM conversations
            WHERE created_at > datetime('now', '+1 day')
        """).fetchone()[0]

        if future > 0:
            self.warnings.append(f"Found {future} conversations with future dates")

        # Check for very old dates (before 2020)
        old = self.conn.execute("""
            SELECT COUNT(*) FROM conversations
            WHERE created_at < '2020-01-01'
        """).fetchone()[0]

        if old > 0:
            self.warnings.append(f"Found {old} conversations with dates before 2020")

        logging.info("  Consistency checks complete")


def print_report(report: dict, as_json: bool = False):
    """Print verification report."""
    if as_json:
        print(json.dumps(report, indent=2))
        return

    print("\n" + "=" * 60)
    print("DATA VERIFICATION REPORT")
    print("=" * 60)

    print("\nStatistics:")
    for key, value in report['stats'].items():
        print(f"  {key}: {value}")

    if report['errors']:
        print(f"\nErrors ({len(report['errors'])}):")
        for error in report['errors']:
            print(f"  ✗ {error}")

    if report['warnings']:
        print(f"\nWarnings ({len(report['warnings'])}):")
        for warning in report['warnings']:
            print(f"  ⚠ {warning}")

    if report['fixes']:
        print(f"\nFixes Applied ({len(report['fixes'])}):")
        for fix in report['fixes']:
            print(f"  ✓ {fix}")

    status = "PASSED" if report['passed'] else "FAILED"
    status_color = "green" if report['passed'] else "red"
    print(f"\nVerification: {status}")
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Verify data integrity")
    parser.add_argument("--fix", action="store_true", help="Attempt to fix issues")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    logger = setup_logging(args.verbose)
    logger.info("Starting data verification...")

    # Initialize database
    init_database()

    # Run verification
    conn = get_connection()
    verifier = DataVerifier(conn, fix=args.fix)
    report = verifier.run_all_checks()

    # Print report
    print_report(report, as_json=args.json)

    # Save report to file
    report_file = Path("logs") / f"verify_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    logger.info(f"Report saved to: {report_file}")

    # Return exit code
    if report['errors']:
        return 2
    if report['warnings']:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
