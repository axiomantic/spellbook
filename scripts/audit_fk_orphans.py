"""Audit spellbook, fractal, and coordination databases for orphaned foreign key references.

Checks a curated list of known foreign key relationships against the
referenced tables to find rows where the referenced ID does not exist.
Reports counts per table/column.

Usage: uv run python scripts/audit_fk_orphans.py
"""

import sqlite3
from pathlib import Path

DB_DIR = Path.home() / ".local" / "spellbook"

# Map: (db_file, child_table, child_column, parent_table, parent_column)
# Table/column names below are hardcoded constants, not user input.
# NOTE: forged.db is excluded as it has no foreign key relationships.
FK_CHECKS = [
    # spellbook.db
    ("spellbook.db", "subagents", "soul_id", "souls", "id"),
    ("spellbook.db", "memory_citations", "memory_id", "memories", "id"),
    ("spellbook.db", "memory_branches", "memory_id", "memories", "id"),
    ("spellbook.db", "experiment_variants", "experiment_id", "experiments", "id"),
    ("spellbook.db", "variant_assignments", "experiment_id", "experiments", "id"),
    ("spellbook.db", "variant_assignments", "variant_id", "experiment_variants", "id"),
    # fractal.db
    ("fractal.db", "nodes", "graph_id", "graphs", "id"),
    ("fractal.db", "nodes", "parent_id", "nodes", "id"),
    ("fractal.db", "edges", "graph_id", "graphs", "id"),
    ("fractal.db", "edges", "from_node", "nodes", "id"),
    ("fractal.db", "edges", "to_node", "nodes", "id"),
    # coordination.db
    ("coordination.db", "workers", "swarm_id", "swarms", "swarm_id"),
    ("coordination.db", "events", "swarm_id", "swarms", "swarm_id"),
]


def audit():
    orphans_found = False
    for db_file, child_table, child_col, parent_table, parent_col in FK_CHECKS:
        db_path = DB_DIR / db_file
        if not db_path.exists():
            print(f"  SKIP {db_file} (not found)")
            continue

        conn = sqlite3.connect(str(db_path))
        try:
            # Check if child table exists
            tables = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
            if child_table not in tables or parent_table not in tables:
                continue

            # Count orphans (child FK value not null and not in parent table)
            query = f"""
                SELECT COUNT(*) FROM {child_table}
                WHERE {child_col} IS NOT NULL
                AND {child_col} NOT IN (SELECT {parent_col} FROM {parent_table})
            """
            count = conn.execute(query).fetchone()[0]
            if count > 0:
                orphans_found = True
                print(f"  ORPHAN: {db_file}.{child_table}.{child_col} -> "
                      f"{parent_table}.{parent_col}: {count} orphaned rows")
        finally:
            conn.close()

    if not orphans_found:
        print("  No orphaned FK references found. Safe to enable PRAGMA foreign_keys=ON.")
    else:
        print("\n  WARNING: Orphaned rows found. These must be cleaned up before")
        print("  enabling PRAGMA foreign_keys=ON, or FK enforcement should be")
        print("  deferred until after cleanup.")

    return not orphans_found


if __name__ == "__main__":
    print("Auditing databases for orphaned FK references...")
    clean = audit()
    exit(0 if clean else 1)
