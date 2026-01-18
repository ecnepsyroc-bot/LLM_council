#!/usr/bin/env python3
"""
API Key Management CLI for LLM Council.

Commands:
    create  - Create new API key
    list    - List all keys (prefix only)
    revoke  - Revoke key by ID
    status  - Check key status
    audit   - View audit log for key
    rotate  - Rotate key (create new, revoke old)

Usage:
    python scripts/manage_keys.py create --name "My Key" --permissions read,write
    python scripts/manage_keys.py list
    python scripts/manage_keys.py revoke <key_id>
    python scripts/manage_keys.py status <prefix>
    python scripts/manage_keys.py audit <key_id>
    python scripts/manage_keys.py rotate <key_id>
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.auth.models import APIKeyCreate, Permission
from backend.auth.service import APIKeyService
from backend.database.connection import init_database, get_connection


# ANSI color codes
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def color(text: str, color_code: str) -> str:
    """Apply color to text."""
    return f"{color_code}{text}{Colors.RESET}"


def print_json(data: dict):
    """Print data as JSON."""
    print(json.dumps(data, indent=2, default=str))


def cmd_create(args):
    """Create a new API key."""
    # Parse permissions
    perm_strs = [p.strip().lower() for p in args.permissions.split(',')]
    permissions = []
    for p in perm_strs:
        try:
            permissions.append(Permission(p))
        except ValueError:
            print(color(f"Invalid permission: {p}", Colors.RED))
            print(f"Valid permissions: {', '.join(p.value for p in Permission)}")
            return 1

    service = APIKeyService()
    request = APIKeyCreate(
        name=args.name,
        permissions=permissions,
        expires_in_days=args.expires,
        rate_limit_per_minute=args.rate_limit,
    )

    result = service.create_key(request)

    if args.json:
        print_json({
            'id': result.key.id,
            'name': result.key.name,
            'api_key': result.api_key,
            'prefix': result.key.key_prefix,
            'permissions': [p.value for p in permissions],
            'expires_at': result.key.expires_at,
        })
    else:
        print()
        print(color("✅ API Key Created", Colors.GREEN))
        print(color("-" * 50, Colors.CYAN))
        print(f"Name: {args.name}")
        print(f"ID: {result.key.id}")
        print(f"Permissions: {', '.join(p.value for p in permissions)}")
        print(f"Expires: {result.key.expires_at or 'Never'}")
        print(color("-" * 50, Colors.CYAN))
        print(color(f"API Key: {result.api_key}", Colors.BOLD))
        print(color("-" * 50, Colors.CYAN))
        print(color("⚠️  Save this key securely! It won't be shown again.", Colors.YELLOW))
        print()

    return 0


def cmd_list(args):
    """List all API keys."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT id, name, key_prefix, permissions, created_at, expires_at,
               is_active, last_used_at
        FROM api_keys
        ORDER BY created_at DESC
    """).fetchall()

    if args.json:
        keys = []
        for row in rows:
            keys.append({
                'id': row[0],
                'name': row[1],
                'prefix': row[2],
                'permissions': row[3].split(','),
                'created_at': row[4],
                'expires_at': row[5],
                'is_active': bool(row[6]),
                'last_used_at': row[7],
            })
        print_json(keys)
        return 0

    if not rows:
        print("No API keys found.")
        return 0

    print()
    print(color("=" * 80, Colors.CYAN))
    print(color("API Keys", Colors.BOLD))
    print(color("=" * 80, Colors.CYAN))

    for row in rows:
        key_id, name, prefix, perms, created, expires, active, last_used = row
        status_color = Colors.GREEN if active else Colors.RED
        status = "Active" if active else "Revoked"

        print()
        print(color(f"  {name}", Colors.BOLD))
        print(f"    ID: {key_id}")
        print(f"    Prefix: {prefix}...")
        print(f"    Permissions: {perms}")
        print(f"    Created: {created}")
        print(f"    Expires: {expires or 'Never'}")
        print(f"    Last Used: {last_used or 'Never'}")
        print(f"    Status: {color(status, status_color)}")

    print()
    print(color("=" * 80, Colors.CYAN))
    print(f"Total: {len(rows)} keys")
    print()

    return 0


def cmd_revoke(args):
    """Revoke an API key."""
    service = APIKeyService()

    # Get key info first
    conn = get_connection()
    row = conn.execute(
        "SELECT name, key_prefix, is_active FROM api_keys WHERE id = ?",
        (args.key_id,)
    ).fetchone()

    if not row:
        print(color(f"Key not found: {args.key_id}", Colors.RED))
        return 1

    name, prefix, is_active = row

    if not is_active:
        print(color(f"Key is already revoked: {name}", Colors.YELLOW))
        return 0

    # Confirm
    if not args.yes:
        print(f"\nAbout to revoke key: {name} ({prefix}...)")
        response = input("Are you sure? [y/N] ")
        if response.lower() != 'y':
            print("Cancelled.")
            return 0

    # Revoke
    success = service.revoke_key(args.key_id)

    if success:
        if args.json:
            print_json({'revoked': True, 'key_id': args.key_id})
        else:
            print(color(f"\n✅ Key revoked: {name}", Colors.GREEN))
        return 0
    else:
        print(color(f"Failed to revoke key", Colors.RED))
        return 1


def cmd_status(args):
    """Check status of a key by prefix."""
    conn = get_connection()
    row = conn.execute("""
        SELECT id, name, key_prefix, permissions, created_at, expires_at,
               is_active, last_used_at, usage_count
        FROM api_keys
        WHERE key_prefix = ? OR id = ?
    """, (args.prefix, args.prefix)).fetchone()

    if not row:
        print(color(f"Key not found: {args.prefix}", Colors.RED))
        return 1

    key_id, name, prefix, perms, created, expires, active, last_used, usage = row

    if args.json:
        print_json({
            'id': key_id,
            'name': name,
            'prefix': prefix,
            'permissions': perms.split(','),
            'created_at': created,
            'expires_at': expires,
            'is_active': bool(active),
            'last_used_at': last_used,
            'usage_count': usage,
        })
    else:
        status = color("Active", Colors.GREEN) if active else color("Revoked", Colors.RED)

        # Check expiry
        expiry_status = ""
        if expires:
            exp_date = datetime.fromisoformat(expires.replace('Z', '+00:00'))
            if exp_date < datetime.now(exp_date.tzinfo):
                expiry_status = color(" (EXPIRED)", Colors.RED)

        print()
        print(color(f"Key Status: {name}", Colors.BOLD))
        print(color("-" * 50, Colors.CYAN))
        print(f"  ID: {key_id}")
        print(f"  Prefix: {prefix}...")
        print(f"  Status: {status}{expiry_status}")
        print(f"  Permissions: {perms}")
        print(f"  Created: {created}")
        print(f"  Expires: {expires or 'Never'}")
        print(f"  Last Used: {last_used or 'Never'}")
        print(f"  Usage Count: {usage}")
        print()

    return 0


def cmd_audit(args):
    """View audit log for a key."""
    conn = get_connection()

    # Verify key exists
    key = conn.execute(
        "SELECT name FROM api_keys WHERE id = ?",
        (args.key_id,)
    ).fetchone()

    if not key:
        print(color(f"Key not found: {args.key_id}", Colors.RED))
        return 1

    # Get audit logs
    rows = conn.execute("""
        SELECT timestamp, endpoint, ip_address, user_agent, success, error_message
        FROM audit_logs
        WHERE api_key_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
    """, (args.key_id, args.limit)).fetchall()

    if args.json:
        logs = []
        for row in rows:
            logs.append({
                'timestamp': row[0],
                'endpoint': row[1],
                'ip_address': row[2],
                'user_agent': row[3],
                'success': bool(row[4]),
                'error': row[5],
            })
        print_json({'key_id': args.key_id, 'name': key[0], 'logs': logs})
        return 0

    print()
    print(color(f"Audit Log: {key[0]}", Colors.BOLD))
    print(color("=" * 80, Colors.CYAN))

    if not rows:
        print("No audit logs found.")
        return 0

    for row in rows:
        timestamp, endpoint, ip, ua, success, error = row
        status = color("✓", Colors.GREEN) if success else color("✗", Colors.RED)

        print(f"\n{status} {timestamp}")
        print(f"   Endpoint: {endpoint}")
        print(f"   IP: {ip}")
        if error:
            print(f"   Error: {color(error, Colors.RED)}")

    print()
    print(color("=" * 80, Colors.CYAN))
    print(f"Showing last {len(rows)} entries")
    print()

    return 0


def cmd_rotate(args):
    """Rotate an API key."""
    service = APIKeyService()
    conn = get_connection()

    # Get existing key info
    row = conn.execute(
        "SELECT name, permissions, expires_at, is_active FROM api_keys WHERE id = ?",
        (args.key_id,)
    ).fetchone()

    if not row:
        print(color(f"Key not found: {args.key_id}", Colors.RED))
        return 1

    name, perms_str, expires_at, is_active = row

    if not is_active:
        print(color(f"Cannot rotate revoked key: {name}", Colors.RED))
        return 1

    # Confirm
    if not args.yes:
        print(f"\nAbout to rotate key: {name}")
        print("This will create a new key and revoke the old one.")
        response = input("Are you sure? [y/N] ")
        if response.lower() != 'y':
            print("Cancelled.")
            return 0

    # Parse permissions
    permissions = [Permission(p.strip()) for p in perms_str.split(',')]

    # Create new key
    new_name = f"{name} (Rotated {datetime.now().strftime('%Y-%m-%d')})"
    request = APIKeyCreate(
        name=new_name,
        permissions=permissions,
        expires_in_days=None,  # New key doesn't expire
    )

    result = service.create_key(request)

    # Revoke old key
    service.revoke_key(args.key_id)

    if args.json:
        print_json({
            'old_key_id': args.key_id,
            'new_key_id': result.key.id,
            'new_api_key': result.api_key,
            'name': new_name,
        })
    else:
        print()
        print(color("✅ Key Rotated Successfully", Colors.GREEN))
        print(color("-" * 50, Colors.CYAN))
        print(f"Old Key: {name} (revoked)")
        print(f"New Key: {new_name}")
        print(color("-" * 50, Colors.CYAN))
        print(color(f"New API Key: {result.api_key}", Colors.BOLD))
        print(color("-" * 50, Colors.CYAN))
        print(color("⚠️  Save this key securely! It won't be shown again.", Colors.YELLOW))
        print()

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="API Key Management CLI for LLM Council",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s create --name "Production Key" --permissions read,write
  %(prog)s list
  %(prog)s revoke abc123
  %(prog)s status lc_
  %(prog)s audit abc123 --limit 50
  %(prog)s rotate abc123
        """
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output as JSON"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Create command
    create_parser = subparsers.add_parser("create", help="Create new API key")
    create_parser.add_argument("--name", "-n", required=True, help="Key name")
    create_parser.add_argument(
        "--permissions", "-p",
        default="read,write",
        help="Comma-separated permissions (default: read,write)"
    )
    create_parser.add_argument(
        "--expires", "-e",
        type=int,
        help="Days until expiry"
    )
    create_parser.add_argument(
        "--rate-limit", "-r",
        type=int,
        help="Custom rate limit per minute"
    )

    # List command
    list_parser = subparsers.add_parser("list", help="List all API keys")

    # Revoke command
    revoke_parser = subparsers.add_parser("revoke", help="Revoke an API key")
    revoke_parser.add_argument("key_id", help="Key ID to revoke")
    revoke_parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation"
    )

    # Status command
    status_parser = subparsers.add_parser("status", help="Check key status")
    status_parser.add_argument("prefix", help="Key prefix or ID")

    # Audit command
    audit_parser = subparsers.add_parser("audit", help="View audit log")
    audit_parser.add_argument("key_id", help="Key ID")
    audit_parser.add_argument(
        "--limit", "-l",
        type=int,
        default=20,
        help="Number of entries (default: 20)"
    )

    # Rotate command
    rotate_parser = subparsers.add_parser("rotate", help="Rotate an API key")
    rotate_parser.add_argument("key_id", help="Key ID to rotate")
    rotate_parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Initialize database
    init_database()

    # Route to command handler
    commands = {
        'create': cmd_create,
        'list': cmd_list,
        'revoke': cmd_revoke,
        'status': cmd_status,
        'audit': cmd_audit,
        'rotate': cmd_rotate,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
