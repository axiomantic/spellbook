#!/usr/bin/env python3
"""
Generate context files for Spellbook.

Previously, this script scanned available skills and appended a skill registry
to context files. The skill registry has been removed because Claude Code (and
other platforms) discover skills directly from the skills directory.

Now this script simply outputs the included content unchanged.
"""
import sys
import argparse
from pathlib import Path


def generate_context_content(include_content: str = "") -> str:
    """Return the include content unchanged.

    The skill registry that was previously appended here has been removed.
    Skills are discovered directly by the platform from the skills directory.
    """
    if include_content:
        return include_content.rstrip() + "\n"
    return ""


def main():
    parser = argparse.ArgumentParser(description="Generate context files for Spellbook")
    parser.add_argument("output", nargs="?", help="Output file path (default: stdout)")
    parser.add_argument("--include", help="Path to a file to include (prepend) in the output")

    args = parser.parse_args()

    include_content = ""
    if args.include:
        include_path = Path(args.include)
        if include_path.exists():
            include_content = include_path.read_text(encoding="utf-8")
        else:
            print(f"Warning: Include file not found: {args.include}", file=sys.stderr)

    content = generate_context_content(include_content)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        print(f"Generated context at {output_path}")
    else:
        print(content, end="")


if __name__ == "__main__":
    main()
