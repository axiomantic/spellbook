"""CLI command for opening the Spellbook admin interface.

Usage:
    python -m spellbook.admin.cli open [--port PORT]

Reads the .mcp-token, requests a single-use handoff URL from the server,
and opens that URL in the default browser. The handoff URL contains an
opaque server-side single-use identifier; the bearer token itself never
appears in any URL (browser history, Referer, process argv).
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

from spellbook.core.config import get_env


def _find_mcp_token() -> str | None:
    """Find and read the .mcp-token file."""
    token_path = Path.home() / ".local" / "spellbook" / ".mcp-token"
    if token_path.exists():
        return token_path.read_text().strip()
    return None


def _get_server_port() -> int:
    """Get the MCP server port from environment or default."""
    return int(get_env("PORT", "8765"))


def admin_open(port: int | None = None) -> int:
    """Request a single-use handoff URL and open it in the browser.

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

    # Request a single-use handoff URL from the server. The bearer token
    # goes in the Authorization header, NOT in the URL or body, so it
    # never lands in browser history, Referer, or process argv.
    handoff_url = f"{base_url}/admin/api/auth/handoff"
    req = urllib.request.Request(handoff_url, data=b"", method="POST")
    req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read())
            login_url = result["login_url"]
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print(
                "Error: Authentication failed (401). The .mcp-token does not "
                "match the running server.",
                file=sys.stderr,
            )
            print(
                "The MCP server may have been restarted with a new token. "
                "Restart your shell or re-source the token, then try again.",
                file=sys.stderr,
            )
        else:
            print(
                f"Error: Server returned HTTP {e.code} from {handoff_url}",
                file=sys.stderr,
            )
            print(f"  {e}", file=sys.stderr)
        return 1
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

    # Open the server-supplied login URL verbatim. The server is the
    # source of truth for the URL; the client never constructs it.
    try:
        webbrowser.open(login_url)
        print(f"Opening admin interface at {base_url}/admin/")
    except Exception:
        print("Could not open browser automatically.", file=sys.stderr)
        print(f"Open this URL in your browser:\n  {login_url}", file=sys.stderr)

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
        help="MCP server port (default: 8765 or PORT env var)",
    )

    args = parser.parse_args(argv)

    if args.command == "open":
        return admin_open(port=args.port)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
