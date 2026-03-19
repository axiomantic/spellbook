#!/usr/bin/env python3
"""Check that the admin frontend dist is up to date with the source.

Computes a SHA-256 hash of all frontend source files (src/, index.html,
package.json, vite.config.ts, tsconfig.json, tailwind.config.js,
postcss.config.js) and compares it to the stored hash in
spellbook/admin/static/.build-hash.

Exit codes:
    0 - dist is up to date (or no frontend source exists)
    1 - dist is stale; needs rebuild

Usage:
    python3 scripts/check_admin_build.py          # check only
    python3 scripts/check_admin_build.py --update  # update hash after build
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = REPO_ROOT / "spellbook" / "admin" / "frontend"
STATIC_DIR = REPO_ROOT / "spellbook" / "admin" / "static"
HASH_FILE = STATIC_DIR / ".build-hash"

# Files/dirs whose content determines the build output
SOURCE_GLOBS = [
    "src/**/*",
    "index.html",
    "package.json",
    "package-lock.json",
    "vite.config.ts",
    "tsconfig.json",
    "tailwind.config.js",
    "postcss.config.js",
]


def compute_source_hash() -> str:
    """Compute a deterministic hash of all frontend source files."""
    hasher = hashlib.sha256()
    files: list[Path] = []
    for pattern in SOURCE_GLOBS:
        files.extend(FRONTEND_DIR.glob(pattern))
    # Sort for determinism
    for path in sorted(f for f in files if f.is_file()):
        rel = path.relative_to(FRONTEND_DIR)
        hasher.update(str(rel).encode())
        hasher.update(path.read_bytes())
    return hasher.hexdigest()


def main() -> int:
    if not FRONTEND_DIR.exists():
        return 0  # no frontend source, nothing to check

    current_hash = compute_source_hash()

    if "--update" in sys.argv:
        HASH_FILE.write_text(current_hash + "\n")
        print(f"Updated build hash: {current_hash[:12]}...")
        return 0

    if not HASH_FILE.exists():
        print("ERROR: No .build-hash file found in spellbook/admin/static/")
        print("Run: cd spellbook/admin/frontend && npm run build")
        print("Then: python3 scripts/check_admin_build.py --update")
        return 1

    stored_hash = HASH_FILE.read_text().strip()
    if current_hash != stored_hash:
        print("ERROR: Admin frontend dist is stale (source files changed since last build)")
        print("Run: cd spellbook/admin/frontend && npm run build")
        print("Then: python3 scripts/check_admin_build.py --update")
        print("Then commit the updated static/ directory")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
