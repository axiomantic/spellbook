"""CLI command for opening the Spellbook admin interface.

Usage:
    python -m spellbook.admin.cli open [--port PORT]

Reads the .mcp-token, exchanges it for a browser auth token,
and opens the admin interface in the default browser.
"""

import argparse
import json
import sys
import urllib.request
import urllib.error
import webbrowser
from pathlib import Path


def _find_mcp_token() -> str | None:
    """Find and read the .mcp-token file."""
    token_path = Path.home() / ".local" / "spellbook" / ".mcp-token"
    if token_path.exists():
        return token_path.read_text().strip()
    return None


def _get_server_port() -> int:
    """Get the MCP server port from environment or default."""
    from spellbook.core.config import get_env

    return int(get_env("PORT", "8765"))


def admin_open(port: int | None = None) -> int:
    """Exchange MCP token for browser auth and open admin interface.

    Returns 0 on success, 1 on error.
    """
    token = _find_mcp_token()
    if not token:
        print(
            "Error: No .mcp-token found at ~/.local/spellbook/.mcp-token",
            file=sys.stderr,
        )
        print(
            "The MCP server must be running. Start it with: spellbook server start",
            file=sys.stderr,
        )
        return 1

    server_port = port or _get_server_port()
    base_url = f"http://127.0.0.1:{server_port}"

    # Exchange token for a one-time auth token
    try:
        exchange_url = f"{base_url}/admin/api/auth/exchange"
        data = json.dumps({"token": token}).encode()
        req = urllib.request.Request(
            exchange_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read())
            exchange_token = result["exchange_token"]
    except urllib.error.URLError as e:
        print(f"Error: Cannot connect to server at {base_url}", file=sys.stderr)
        print(f"  {e}", file=sys.stderr)
        print(
            "Ensure the MCP server is running: spellbook server start",
            file=sys.stderr,
        )
        return 1
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Error: Unexpected response from server: {e}", file=sys.stderr)
        return 1

    # Build callback URL
    callback_url = f"{base_url}/admin/api/auth/callback?auth={exchange_token}"

    # Try to open browser
    try:
        webbrowser.open(callback_url)
        print(f"Opening admin interface at {base_url}/admin/")
    except Exception:
        print("Could not open browser automatically.", file=sys.stderr)
        print(f"Open this URL in your browser:\n  {callback_url}", file=sys.stderr)

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="spellbook-admin",
        description="Spellbook Admin CLI",
    )
    subparsers = parser.add_subparsers(dest="command")

    open_parser = subparsers.add_parser("open", help="Open admin interface in browser")
    open_parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="MCP server port (default: 8765 or SPELLBOOK_MCP_PORT)",
    )

    args = parser.parse_args(argv)

    if args.command == "open":
        return admin_open(port=args.port)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
