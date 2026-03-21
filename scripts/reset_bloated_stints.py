#!/usr/bin/env python3
"""One-time cleanup: reset bloated stint stacks.

Resets all stint stacks with depth > MAX_STINT_DEPTH (6) to empty.
Run manually when deploying the stint redesign.

Usage:
    python scripts/reset_bloated_stints.py [--dry-run]
"""

import json
import sqlite3
import sys
from pathlib import Path


def main():
    dry_run = "--dry-run" in sys.argv

    db_path = Path.home() / ".local" / "spellbook" / "spellbook.db"
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()

        cursor.execute("SELECT project_path, stack_json FROM stint_stack")
        rows = cursor.fetchall()

        reset_count = 0
        for project_path, stack_json in rows:
            try:
                stack = json.loads(stack_json)
            except (json.JSONDecodeError, TypeError):
                stack = []

            if len(stack) > 6:
                reset_count += 1
                print(f"{'[DRY RUN] ' if dry_run else ''}Reset: {project_path} (depth {len(stack)} -> 0)")
                if not dry_run:
                    cursor.execute(
                        "UPDATE stint_stack SET stack_json = '[]', updated_at = CURRENT_TIMESTAMP WHERE project_path = ?",
                        (project_path,),
                    )

        if not dry_run and reset_count > 0:
            conn.commit()

        print(f"\n{'[DRY RUN] ' if dry_run else ''}Reset {reset_count} bloated stacks (of {len(rows)} total).")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
