#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Spellbook Installer - Multi-platform AI assistant skills installation.

Usage:
    uv run install.py                    # Interactive mode with platform selection
    uv run install.py --no-interactive   # Auto-install all available platforms
    uv run install.py --platforms LIST   # Install specific platforms

Options:
    --platforms     Comma-separated list (claude_code,opencode,codex,gemini)
    --force         Reinstall even if version matches
    --dry-run       Show what would be done without making changes
    --verify-mcp    Verify MCP server connectivity after installation
    --no-interactive  Skip platform selection UI
"""

import argparse
import sys
from pathlib import Path

# Ensure installer package is importable
sys.path.insert(0, str(Path(__file__).parent))

from installer.core import Installer
from installer.ui import (
    Spinner,
    print_directory_config,
    print_header,
    print_info,
    print_report,
    print_success,
    print_warning,
)
from installer.components.mcp import verify_mcp_connectivity


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install Spellbook - Multi-platform AI assistant skills"
    )
    parser.add_argument(
        "--platforms",
        type=str,
        default=None,
        help="Comma-separated platforms (claude_code,opencode,codex,gemini)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reinstall even if version matches",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without changes",
    )
    parser.add_argument(
        "--verify-mcp",
        action="store_true",
        help="Verify MCP server connectivity",
    )
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="Skip interactive platform selection",
    )

    args = parser.parse_args()

    spellbook_dir = Path(__file__).parent
    installer = Installer(spellbook_dir)

    print_header(installer.version)

    # Determine platforms to install
    if args.platforms:
        # Explicit platforms provided
        platforms = args.platforms.split(",")
    elif args.no_interactive or not sys.stdin.isatty():
        # Non-interactive mode: auto-detect all available
        platforms = installer.detect_platforms()
        print_info(f"Auto-detected platforms: {', '.join(platforms)}")
        print()
    else:
        # Interactive mode: show platform selection UI
        try:
            from installer.tui import interactive_platform_select, show_post_install_instructions

            platforms = interactive_platform_select()

            if platforms is None:
                print_warning("Installation cancelled")
                return 1

            if not platforms:
                print_warning("No platforms selected")
                return 1

        except (ImportError, Exception) as e:
            # Fall back to auto-detect if TUI fails
            print_warning(f"Interactive mode unavailable ({e}), using auto-detect")
            platforms = installer.detect_platforms()

    # Show directory configuration
    print_directory_config(spellbook_dir, platforms)

    if args.dry_run:
        print_warning("DRY RUN - no changes will be made")
        print()

    with Spinner("Installing"):
        session = installer.run(
            platforms=platforms,
            force=args.force,
            dry_run=args.dry_run,
        )

    if args.verify_mcp and not args.dry_run:
        print()
        server_path = spellbook_dir / "spellbook_mcp" / "server.py"
        with Spinner("Verifying MCP server"):
            success, msg = verify_mcp_connectivity(server_path)
        if success:
            print_success(f"MCP server: {msg}")
        else:
            print_warning(f"MCP server: {msg}")

    print_report(session)

    # Show post-install instructions if interactive and not dry-run
    if not args.dry_run and sys.stdin.isatty():
        try:
            from installer.tui import show_post_install_instructions
            show_post_install_instructions(session.platforms_installed)
        except ImportError:
            pass

    # Exit code: 0 if all succeeded, 1 if any failed
    return 0 if session.success else 1


if __name__ == "__main__":
    sys.exit(main())
