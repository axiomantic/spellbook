#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Spellbook Uninstaller - Remove spellbook from all platforms.

Usage:
    uv run uninstall.py [--platforms PLATFORMS] [--dry-run]

Options:
    --platforms     Comma-separated list (default: all installed)
    --dry-run       Show what would be done without making changes
"""

import argparse
import sys
from pathlib import Path

# Ensure installer package is importable
sys.path.insert(0, str(Path(__file__).parent))

from installer.core import Uninstaller
from installer.ui import print_header, print_warning, print_uninstall_report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Uninstall Spellbook from AI coding platforms"
    )
    parser.add_argument(
        "--platforms",
        type=str,
        default=None,
        help="Comma-separated platforms to uninstall (default: all installed)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without changes",
    )

    args = parser.parse_args()

    spellbook_dir = Path(__file__).parent
    uninstaller = Uninstaller(spellbook_dir)

    platforms = args.platforms.split(",") if args.platforms else None

    print()
    print("=" * 60)
    print("  Spellbook Uninstaller")
    print("=" * 60)
    print()

    if args.dry_run:
        print_warning("DRY RUN - no changes will be made")
        print()

    session = uninstaller.run(
        platforms=platforms,
        dry_run=args.dry_run,
    )

    print_uninstall_report(session)

    return 0 if session.success else 1


if __name__ == "__main__":
    sys.exit(main())
