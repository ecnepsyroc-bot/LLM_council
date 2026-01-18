"""
Bootstrap script to create initial admin API key.

Features:
- Check if admin key already exists
- Support for key rotation
- Interactive and non-interactive modes
- Secure key output options

Usage:
    python -m backend.auth.bootstrap [--name NAME] [--permissions PERMS] [--expires DAYS]
    python -m backend.auth.bootstrap --rotate KEY_ID
    python -m backend.auth.bootstrap --non-interactive
"""

import argparse
import os
import stat
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List

# Add parent directory to path for imports when run directly
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.auth.models import APIKeyCreate, Permission
from backend.auth.service import APIKeyService
from backend.database.connection import init_database, get_connection


def get_existing_admin_keys() -> list:
    """Get list of existing admin API keys."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT id, name, key_prefix, created_at, expires_at, is_active
        FROM api_keys
        WHERE permissions LIKE '%admin%' AND is_active = 1
        ORDER BY created_at DESC
    """).fetchall()

    return [
        {
            'id': row[0],
            'name': row[1],
            'prefix': row[2],
            'created_at': row[3],
            'expires_at': row[4],
            'is_active': row[5],
        }
        for row in rows
    ]


def save_key_to_file(api_key: str, filepath: Path) -> bool:
    """
    Save API key to a file with secure permissions.

    Args:
        api_key: The API key to save
        filepath: Path to save the key to

    Returns:
        True if successful
    """
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # Write key
        with open(filepath, 'w') as f:
            f.write(api_key)

        # Set restrictive permissions (owner read/write only)
        if os.name != 'nt':  # Unix-like
            os.chmod(filepath, stat.S_IRUSR | stat.S_IWUSR)

        return True
    except Exception as e:
        print(f"Failed to save key to file: {e}")
        return False


def create_admin_key(
    name: str = "Admin Key",
    permissions: Optional[List[Permission]] = None,
    expires_in_days: Optional[int] = None,
    save_to_file: Optional[Path] = None,
    non_interactive: bool = False,
) -> str:
    """
    Create an admin API key.

    Args:
        name: Key name
        permissions: List of permissions (defaults to all)
        expires_in_days: Days until expiry (None = never)
        save_to_file: Optional path to save key
        non_interactive: Skip confirmation prompts

    Returns:
        The full API key
    """
    # Default to all permissions
    if permissions is None:
        permissions = [
            Permission.READ,
            Permission.WRITE,
            Permission.ADMIN,
            Permission.STREAM,
        ]

    # Check for existing admin keys
    existing = get_existing_admin_keys()

    if existing and not non_interactive:
        print("\n⚠️  Existing admin keys found:")
        for key in existing:
            expires = key['expires_at'] or 'Never'
            print(f"  - {key['name']} ({key['prefix']}...) - Expires: {expires}")

        response = input("\nCreate another key? [y/N] ")
        if response.lower() != 'y':
            print("Cancelled.")
            return None

    # Create the key
    service = APIKeyService()
    request = APIKeyCreate(
        name=name,
        permissions=permissions,
        expires_in_days=expires_in_days,
    )

    result = service.create_key(request)

    # Output
    print("\n" + "=" * 60)
    print("✅ API Key Created Successfully")
    print("=" * 60)
    print(f"\nKey Name: {name}")
    print(f"Permissions: {', '.join(p.value for p in permissions)}")
    print(f"Expires: {result.key.expires_at or 'Never'}")
    print("\n" + "-" * 60)
    print(f"API Key: {result.api_key}")
    print("-" * 60)
    print("\n⚠️  IMPORTANT: Save this key securely!")
    print("   This is the ONLY time it will be displayed.")

    # Save to file if requested
    if save_to_file:
        if save_key_to_file(result.api_key, save_to_file):
            print(f"\n✅ Key saved to: {save_to_file}")
        else:
            print(f"\n❌ Failed to save key to file")

    print("\n" + "=" * 60)

    return result.api_key


def rotate_key(key_id: str) -> Optional[str]:
    """
    Rotate an existing API key (create new, revoke old).

    Args:
        key_id: ID of the key to rotate

    Returns:
        New API key if successful, None otherwise
    """
    service = APIKeyService()

    # Get existing key info
    conn = get_connection()
    row = conn.execute(
        "SELECT name, permissions, expires_at FROM api_keys WHERE id = ?",
        (key_id,)
    ).fetchone()

    if not row:
        print(f"❌ Key not found: {key_id}")
        return None

    name, perms_str, expires_at = row

    # Parse permissions
    permissions = [Permission(p.strip()) for p in perms_str.split(',')]

    # Create new key with same settings
    print(f"\n🔄 Rotating key: {name}")

    new_key = create_admin_key(
        name=f"{name} (Rotated {datetime.now().strftime('%Y-%m-%d')})",
        permissions=permissions,
        non_interactive=True,
    )

    if new_key:
        # Revoke old key
        service.revoke_key(key_id)
        print(f"\n✅ Old key revoked")

    return new_key


def list_keys():
    """List all API keys."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT id, name, key_prefix, permissions, created_at, expires_at, is_active
        FROM api_keys
        ORDER BY created_at DESC
    """).fetchall()

    if not rows:
        print("No API keys found.")
        return

    print("\n" + "=" * 80)
    print("API Keys")
    print("=" * 80)

    for row in rows:
        key_id, name, prefix, perms, created, expires, active = row
        status = "✓ Active" if active else "✗ Revoked"
        expires_str = expires or "Never"

        print(f"\n{name}")
        print(f"  ID: {key_id}")
        print(f"  Prefix: {prefix}...")
        print(f"  Permissions: {perms}")
        print(f"  Created: {created}")
        print(f"  Expires: {expires_str}")
        print(f"  Status: {status}")

    print("\n" + "=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Bootstrap admin API key for LLM Council"
    )
    parser.add_argument(
        "--name", "-n",
        default="Admin Key",
        help="Name for the API key"
    )
    parser.add_argument(
        "--permissions", "-p",
        default="read,write,admin,stream",
        help="Comma-separated permissions (read,write,admin,stream)"
    )
    parser.add_argument(
        "--expires", "-e",
        type=int,
        default=None,
        help="Days until expiry (default: never)"
    )
    parser.add_argument(
        "--save-to",
        type=Path,
        help="Save key to file"
    )
    parser.add_argument(
        "--rotate",
        metavar="KEY_ID",
        help="Rotate an existing key by ID"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all API keys"
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Non-interactive mode (skip confirmations)"
    )

    args = parser.parse_args()

    # Initialize database
    init_database()

    if args.list:
        list_keys()
        return

    if args.rotate:
        rotate_key(args.rotate)
        return

    # Parse permissions
    perm_strs = [p.strip().lower() for p in args.permissions.split(',')]
    permissions = []
    for p in perm_strs:
        try:
            permissions.append(Permission(p))
        except ValueError:
            print(f"Invalid permission: {p}")
            print(f"Valid permissions: {', '.join(p.value for p in Permission)}")
            sys.exit(1)

    # Create key
    create_admin_key(
        name=args.name,
        permissions=permissions,
        expires_in_days=args.expires,
        save_to_file=args.save_to,
        non_interactive=args.non_interactive,
    )


if __name__ == "__main__":
    main()
