#!/usr/bin/env python3
"""
Database backup and restore for LLM Council.

Features:
- Timestamped backups with gzip compression
- Backup verification
- Configurable retention policy
- Restore capability

Usage:
    python scripts/backup_db.py [--restore <backup_file>] [--retention-days N] [--no-compress]
"""

import argparse
import gzip
import logging
import shutil
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def setup_logging():
    """Setup logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    return logging.getLogger(__name__)


def get_db_path() -> Path:
    """Get the database path from config or default."""
    try:
        from backend.database.connection import DATABASE_PATH
        return Path(DATABASE_PATH)
    except ImportError:
        return Path(__file__).parent.parent / "data" / "council.db"


def get_backup_dir() -> Path:
    """Get backup directory."""
    backup_dir = Path(__file__).parent.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def create_backup(db_path: Path, compress: bool = True) -> Path:
    """
    Create a backup of the database.

    Args:
        db_path: Path to the database file
        compress: Whether to gzip compress the backup

    Returns:
        Path to the backup file
    """
    logger = logging.getLogger(__name__)

    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    # Generate backup filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = get_backup_dir()

    if compress:
        backup_path = backup_dir / f"council_{timestamp}.db.gz"
    else:
        backup_path = backup_dir / f"council_{timestamp}.db"

    logger.info(f"Creating backup: {backup_path}")

    # Use SQLite backup API for consistency
    source = sqlite3.connect(str(db_path))
    temp_backup = backup_dir / f"council_{timestamp}_temp.db"

    try:
        # Create backup using SQLite backup API
        backup_conn = sqlite3.connect(str(temp_backup))
        with backup_conn:
            source.backup(backup_conn)
        backup_conn.close()
        source.close()

        if compress:
            # Compress the backup
            with open(temp_backup, 'rb') as f_in:
                with gzip.open(backup_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            temp_backup.unlink()
        else:
            temp_backup.rename(backup_path)

        # Get backup size
        backup_size = backup_path.stat().st_size
        original_size = db_path.stat().st_size

        logger.info(f"Backup created successfully")
        logger.info(f"  Original size: {original_size:,} bytes")
        logger.info(f"  Backup size: {backup_size:,} bytes")
        if compress:
            ratio = (1 - backup_size / original_size) * 100
            logger.info(f"  Compression: {ratio:.1f}% reduction")

        return backup_path

    except Exception as e:
        # Clean up temp file on error
        if temp_backup.exists():
            temp_backup.unlink()
        raise


def verify_backup(backup_path: Path) -> dict:
    """
    Verify a backup file is valid.

    Args:
        backup_path: Path to the backup file

    Returns:
        dict with verification results
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Verifying backup: {backup_path}")

    result = {
        'valid': False,
        'tables': [],
        'row_counts': {},
        'error': None
    }

    temp_db = None
    try:
        # Decompress if needed
        if backup_path.suffix == '.gz':
            temp_db = backup_path.with_suffix('')
            with gzip.open(backup_path, 'rb') as f_in:
                with open(temp_db, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            db_to_check = temp_db
        else:
            db_to_check = backup_path

        # Open and verify
        conn = sqlite3.connect(str(db_to_check))

        # Check integrity
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            result['error'] = f"Integrity check failed: {integrity}"
            return result

        # Get tables
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        result['tables'] = [t[0] for t in tables]

        # Get row counts
        for table in result['tables']:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            result['row_counts'][table] = count

        conn.close()
        result['valid'] = True

        logger.info(f"  Integrity: OK")
        logger.info(f"  Tables: {len(result['tables'])}")
        for table, count in result['row_counts'].items():
            logger.info(f"    {table}: {count} rows")

    except Exception as e:
        result['error'] = str(e)
        logger.error(f"Verification failed: {e}")

    finally:
        # Clean up temp file
        if temp_db and temp_db.exists():
            temp_db.unlink()

    return result


def restore_backup(backup_path: Path, db_path: Path, force: bool = False) -> bool:
    """
    Restore database from a backup.

    Args:
        backup_path: Path to the backup file
        db_path: Path to restore to
        force: Overwrite existing database without confirmation

    Returns:
        True if restore was successful
    """
    logger = logging.getLogger(__name__)

    if not backup_path.exists():
        raise FileNotFoundError(f"Backup not found: {backup_path}")

    # Verify backup first
    verification = verify_backup(backup_path)
    if not verification['valid']:
        raise ValueError(f"Backup verification failed: {verification['error']}")

    # Check if target exists
    if db_path.exists() and not force:
        response = input(f"Database exists at {db_path}. Overwrite? [y/N] ")
        if response.lower() != 'y':
            logger.info("Restore cancelled")
            return False

    logger.info(f"Restoring from: {backup_path}")
    logger.info(f"Restoring to: {db_path}")

    # Create backup of current database first
    if db_path.exists():
        pre_restore_backup = create_backup(db_path, compress=True)
        logger.info(f"Created pre-restore backup: {pre_restore_backup}")

    try:
        # Decompress if needed
        if backup_path.suffix == '.gz':
            with gzip.open(backup_path, 'rb') as f_in:
                with open(db_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        else:
            shutil.copy2(backup_path, db_path)

        logger.info("Restore completed successfully")
        return True

    except Exception as e:
        logger.error(f"Restore failed: {e}")
        raise


def cleanup_old_backups(retention_days: int) -> list:
    """
    Remove backups older than retention period.

    Args:
        retention_days: Number of days to keep backups

    Returns:
        List of deleted backup paths
    """
    logger = logging.getLogger(__name__)
    backup_dir = get_backup_dir()
    cutoff = datetime.now() - timedelta(days=retention_days)

    deleted = []
    for backup_file in backup_dir.glob("council_*.db*"):
        # Parse timestamp from filename
        try:
            # Extract timestamp: council_YYYYMMDD_HHMMSS.db[.gz]
            name = backup_file.stem
            if name.endswith('.db'):
                name = name[:-3]  # Remove .db from council_..._temp.db cases
            timestamp_str = name.replace('council_', '')
            if '_temp' in timestamp_str:
                continue  # Skip temp files

            backup_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")

            if backup_time < cutoff:
                backup_file.unlink()
                deleted.append(str(backup_file))
                logger.info(f"Deleted old backup: {backup_file.name}")

        except ValueError:
            # Skip files that don't match our naming pattern
            continue

    return deleted


def list_backups() -> list:
    """List all available backups."""
    backup_dir = get_backup_dir()
    backups = []

    for backup_file in sorted(backup_dir.glob("council_*.db*"), reverse=True):
        if '_temp' in backup_file.name:
            continue

        stat = backup_file.stat()
        backups.append({
            'path': str(backup_file),
            'name': backup_file.name,
            'size': stat.st_size,
            'created': datetime.fromtimestamp(stat.st_mtime).isoformat()
        })

    return backups


def print_backup_list(backups: list):
    """Print formatted backup list."""
    if not backups:
        print("No backups found")
        return

    print("\n" + "=" * 70)
    print("AVAILABLE BACKUPS")
    print("=" * 70)

    for i, backup in enumerate(backups, 1):
        size_mb = backup['size'] / (1024 * 1024)
        print(f"\n{i}. {backup['name']}")
        print(f"   Size: {size_mb:.2f} MB")
        print(f"   Created: {backup['created']}")

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Database backup and restore")
    parser.add_argument("--restore", metavar="FILE", help="Restore from backup file")
    parser.add_argument("--list", action="store_true", help="List available backups")
    parser.add_argument("--verify", metavar="FILE", help="Verify a backup file")
    parser.add_argument("--retention-days", type=int, default=30,
                        help="Days to keep backups (default: 30)")
    parser.add_argument("--no-compress", action="store_true",
                        help="Don't compress backup")
    parser.add_argument("--cleanup", action="store_true",
                        help="Clean up old backups")
    parser.add_argument("--force", action="store_true",
                        help="Force overwrite without confirmation")
    args = parser.parse_args()

    logger = setup_logging()

    try:
        db_path = get_db_path()

        if args.list:
            backups = list_backups()
            print_backup_list(backups)
            return 0

        if args.verify:
            backup_path = Path(args.verify)
            result = verify_backup(backup_path)
            if result['valid']:
                print("Backup is valid")
                return 0
            else:
                print(f"Backup is invalid: {result['error']}")
                return 1

        if args.restore:
            backup_path = Path(args.restore)
            success = restore_backup(backup_path, db_path, force=args.force)
            return 0 if success else 1

        if args.cleanup:
            deleted = cleanup_old_backups(args.retention_days)
            print(f"Cleaned up {len(deleted)} old backups")
            return 0

        # Default: create backup
        backup_path = create_backup(db_path, compress=not args.no_compress)

        # Verify the backup
        verification = verify_backup(backup_path)
        if not verification['valid']:
            logger.error("Backup verification failed!")
            return 1

        # Clean up old backups
        deleted = cleanup_old_backups(args.retention_days)
        if deleted:
            logger.info(f"Cleaned up {len(deleted)} old backups")

        print(f"\nBackup created: {backup_path}")
        return 0

    except Exception as e:
        logger.error(f"Error: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
