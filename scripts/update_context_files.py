#!/usr/bin/env python3
"""
Pre-commit hook to update context files.

CLAUDE.spellbook.md is the installable template that gets inserted into user 
config directories for Claude, Codex, and OpenCode. Gemini uses native extensions.

Regenerates context files and checks if they need updating.
If files changed, updates them and exits with error so user can re-stage.
"""
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
GENERATE_SCRIPT = SCRIPT_DIR / "generate_context.py"
CLAUDE_MD = REPO_ROOT / "CLAUDE.spellbook.md"

# Only CLAUDE.spellbook.md needed now (Gemini uses extensions/gemini/GEMINI.md)
CONTEXT_FILES = [
    REPO_ROOT / "CLAUDE.spellbook.md",
]


def generate_context(output_path: Path) -> str:
    """Generate context content using generate_context.py."""
    cmd = [
        sys.executable,
        str(GENERATE_SCRIPT),
        "--include", str(CLAUDE_MD),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error generating context: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout


def main():
    if not GENERATE_SCRIPT.exists():
        print(f"Error: {GENERATE_SCRIPT} not found", file=sys.stderr)
        sys.exit(1)

    files_updated = []

    for context_file in CONTEXT_FILES:
        # Read existing content
        existing = ""
        if context_file.exists():
            existing = context_file.read_text(encoding="utf-8")

        # Generate new content
        new_content = generate_context(context_file)

        # Compare
        if existing != new_content:
            # Update the file
            context_file.write_text(new_content, encoding="utf-8")
            files_updated.append(context_file.name)

    if files_updated:
        print(f"Updated context files: {', '.join(files_updated)}")
        print("Please stage the updated files and retry commit:")
        print(f"  git add {' '.join(files_updated)}")
        sys.exit(1)

    # All files up to date
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
