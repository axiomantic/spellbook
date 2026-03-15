#!/usr/bin/env python3
"""Backfill session_id and timestamp fields on existing fractal nodes.

Scans Claude Code JSONL session transcripts to find fractal_claim_work,
fractal_add_node (answer), and fractal_synthesize_node tool calls, then
matches them to database nodes that are missing session_id/timestamps.

Usage:
    python3 scripts/backfill_fractal_sessions.py          # dry-run
    python3 scripts/backfill_fractal_sessions.py --apply   # write to DB
"""

import json
import os
import sqlite3
import sys
from pathlib import Path


FRACTAL_DB = Path.home() / ".local" / "spellbook" / "fractal.db"
CLAUDE_PROJECTS = Path.home() / ".claude" / "projects"

# Tool name patterns (MCP tool names as they appear in JSONL)
CLAIM_WORK = "fractal_claim_work"
ADD_NODE = "fractal_add_node"
SYNTHESIZE_NODE = "fractal_synthesize_node"


def load_nodes_needing_backfill(db_path):
    """Load all nodes with session_id IS NULL and status != 'open'."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT id, graph_id, node_type, status, session_id, "
        "claimed_at, answered_at, synthesized_at "
        "FROM nodes WHERE status != 'open' AND session_id IS NULL"
    )
    nodes = {row["id"]: dict(row) for row in cursor.fetchall()}
    conn.close()
    return nodes


def find_jsonl_files():
    """Find all JSONL session transcript files."""
    if not CLAUDE_PROJECTS.exists():
        print(f"  Claude projects directory not found: {CLAUDE_PROJECTS}")
        return []
    files = sorted(CLAUDE_PROJECTS.glob("**/*.jsonl"))
    return files


def extract_tool_calls_from_entry(entry):
    """Extract fractal tool_use blocks from a JSONL entry.

    Tool calls appear in 'progress' entries as subagent messages, or in
    'assistant' entries at the top level. The nesting varies:

    Progress entries:
      entry.data.message.message.content -> list of content blocks
      entry.data.message.type -> "assistant" or "user"

    Top-level assistant entries:
      entry.message.content -> list of content blocks

    Returns list of (tool_name, tool_use_id, input_dict, timestamp).
    """
    results = []
    timestamp = entry.get("timestamp")
    entry_type = entry.get("type")

    content_lists = []

    if entry_type == "progress":
        data = entry.get("data", {})
        msg = data.get("message", {})
        if msg.get("type") == "assistant":
            inner = msg.get("message", {})
            content = inner.get("content", [])
            if isinstance(content, list):
                content_lists.append(content)
    elif entry_type == "assistant":
        content = entry.get("message", {}).get("content", [])
        if isinstance(content, list):
            content_lists.append(content)

    for content in content_lists:
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "tool_use":
                continue
            name = block.get("name", "")
            if CLAIM_WORK in name or ADD_NODE in name or SYNTHESIZE_NODE in name:
                results.append((
                    name,
                    block.get("id"),
                    block.get("input", {}),
                    timestamp,
                ))

    return results


def extract_tool_results_from_entry(entry):
    """Extract fractal tool_result blocks from a JSONL entry.

    Returns dict of {tool_use_id: content_string}.
    """
    results = {}
    entry_type = entry.get("type")

    content_lists = []

    if entry_type == "progress":
        data = entry.get("data", {})
        msg = data.get("message", {})
        if msg.get("type") == "user":
            inner = msg.get("message", {})
            content = inner.get("content", [])
            if isinstance(content, list):
                content_lists.append(content)
    elif entry_type == "user":
        content = entry.get("message", {}).get("content", [])
        if isinstance(content, list):
            content_lists.append(content)

    for content in content_lists:
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "tool_result":
                continue
            tool_use_id = block.get("tool_use_id")
            if tool_use_id:
                results[tool_use_id] = block.get("content", "")

    return results


def parse_tool_result_json(content):
    """Parse a tool_result content string as JSON, returning dict or None."""
    if not isinstance(content, str):
        return None
    try:
        return json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return None


def scan_jsonl_file(filepath, target_graph_ids, target_node_ids):
    """Scan a single JSONL file for fractal tool calls.

    Returns a list of matched updates:
        [{"node_id": ..., "session_id": ..., "claimed_at": ..., ...}, ...]
    """
    session_id = filepath.stem
    updates = []

    # First pass: collect all tool_use calls and tool_results
    pending_claims = {}  # tool_use_id -> (graph_id, worker_id, timestamp)
    pending_add_answers = {}  # tool_use_id -> (graph_id, parent_id, timestamp)
    synthesize_matches = []  # (node_id, timestamp, session_id)

    try:
        with open(filepath, "r") as f:
            lines = f.readlines()

        # We need tool_use_ids from claim_work/add_node calls to find their
        # tool_results in subsequent lines. The tool_result lines do NOT
        # contain the tool name, only the tool_use_id. So we must:
        #   Pass 1: scan for tool_use calls (lines mentioning fractal tools)
        #   Pass 2: scan for tool_results matching pending tool_use_ids

        # Pass 1: find tool_use calls
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Quick filter: only parse lines mentioning fractal tools
            if CLAIM_WORK not in line and ADD_NODE not in line and SYNTHESIZE_NODE not in line:
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            for tool_name, tool_use_id, tool_input, timestamp in extract_tool_calls_from_entry(entry):
                graph_id = tool_input.get("graph_id", "")

                if graph_id not in target_graph_ids:
                    continue

                if CLAIM_WORK in tool_name:
                    pending_claims[tool_use_id] = (graph_id, tool_input.get("worker_id"), timestamp)

                elif ADD_NODE in tool_name:
                    pending_add_answers[tool_use_id] = (graph_id, tool_input.get("parent_id"), timestamp, tool_input.get("node_type", ""))

                elif SYNTHESIZE_NODE in tool_name:
                    node_id = tool_input.get("node_id", "")
                    if node_id in target_node_ids:
                        synthesize_matches.append((node_id, timestamp, session_id))

        # Pass 2: find tool_results for pending claim_work and add_node calls
        pending_ids = set(pending_claims.keys()) | set(pending_add_answers.keys())
        tool_results = {}

        if pending_ids:
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Quick filter: check if any pending tool_use_id appears
                if not any(tid in line for tid in pending_ids):
                    continue

                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                for tool_use_id, content in extract_tool_results_from_entry(entry).items():
                    if tool_use_id in pending_ids:
                        tool_results[tool_use_id] = content

                # Stop early if we found all results
                if len(tool_results) >= len(pending_ids):
                    break

        # Now resolve pending claims using tool_results
        for tool_use_id, (graph_id, worker_id, timestamp) in pending_claims.items():
            content = tool_results.get(tool_use_id)
            if content is None:
                continue
            result = parse_tool_result_json(content)
            if result is None:
                continue
            node_id = result.get("node_id")
            if node_id and node_id in target_node_ids:
                updates.append({
                    "node_id": node_id,
                    "session_id": session_id,
                    "claimed_at": timestamp,
                })

        # Resolve add_node calls using tool_results
        for tool_use_id, (graph_id, parent_id, timestamp, node_type) in pending_add_answers.items():
            content = tool_results.get(tool_use_id)
            if content is None:
                continue
            result = parse_tool_result_json(content)
            if result is None:
                continue
            node_id = result.get("node_id")
            if node_id and node_id in target_node_ids:
                update = {
                    "node_id": node_id,
                    "session_id": session_id,
                }
                # Only set answered_at for answer nodes, not question nodes
                if node_type == "answer":
                    update["answered_at"] = timestamp
                updates.append(update)

        # Synthesize matches are already resolved (node_id is in the input)
        for node_id, timestamp, sid in synthesize_matches:
            updates.append({
                "node_id": node_id,
                "session_id": sid,
                "synthesized_at": timestamp,
            })

    except Exception as e:
        print(f"  Error reading {filepath.name}: {e}")

    return updates


def merge_updates(all_updates):
    """Merge multiple updates for the same node_id into a single record.

    When multiple updates exist for the same node, we merge timestamp fields
    and prefer the session_id from the claim_work call (earliest operation).
    """
    merged = {}
    for update in all_updates:
        node_id = update["node_id"]
        if node_id not in merged:
            merged[node_id] = {
                "node_id": node_id,
                "session_id": None,
                "claimed_at": None,
                "answered_at": None,
                "synthesized_at": None,
            }
        record = merged[node_id]

        # Merge fields, preferring earliest session_id
        if update.get("session_id"):
            if record["session_id"] is None:
                record["session_id"] = update["session_id"]
            elif update.get("claimed_at"):
                # Prefer session from claim_work
                record["session_id"] = update["session_id"]

        for field in ("claimed_at", "answered_at", "synthesized_at"):
            if update.get(field) and record[field] is None:
                record[field] = update[field]

    return merged


def apply_updates(db_path, merged_updates, dry_run=True):
    """Apply merged updates to the database."""
    if not merged_updates:
        return 0

    conn = sqlite3.connect(str(db_path))
    updated = 0

    for node_id, record in merged_updates.items():
        set_clauses = []
        params = []

        if record["session_id"]:
            set_clauses.append("session_id = ?")
            params.append(record["session_id"])
        if record["claimed_at"]:
            set_clauses.append("claimed_at = ?")
            params.append(record["claimed_at"])
        if record["answered_at"]:
            set_clauses.append("answered_at = ?")
            params.append(record["answered_at"])
        if record["synthesized_at"]:
            set_clauses.append("synthesized_at = ?")
            params.append(record["synthesized_at"])

        if not set_clauses:
            continue

        params.append(node_id)
        sql = f"UPDATE nodes SET {', '.join(set_clauses)} WHERE id = ?"

        if dry_run:
            print(f"  [DRY-RUN] {sql}")
            print(f"            params={params}")
        else:
            conn.execute(sql, params)

        updated += 1

    if not dry_run:
        conn.commit()
    conn.close()
    return updated


def main():
    apply = "--apply" in sys.argv
    mode = "APPLY" if apply else "DRY-RUN"

    print(f"Fractal Session Backfill ({mode})")
    print("=" * 60)

    # Step 1: Load nodes needing backfill
    if not FRACTAL_DB.exists():
        print(f"ERROR: Fractal database not found at {FRACTAL_DB}")
        sys.exit(1)

    print(f"\nDatabase: {FRACTAL_DB}")
    nodes = load_nodes_needing_backfill(FRACTAL_DB)
    print(f"Nodes needing backfill: {len(nodes)}")

    if not nodes:
        print("Nothing to backfill. All nodes already have session_id set.")
        return

    # Build lookup sets for efficient filtering
    target_node_ids = set(nodes.keys())
    target_graph_ids = {n["graph_id"] for n in nodes.values()}
    print(f"Across {len(target_graph_ids)} graphs: {', '.join(sorted(target_graph_ids)[:5])}{'...' if len(target_graph_ids) > 5 else ''}")

    # Step 2: Find JSONL files
    print(f"\nScanning JSONL files under {CLAUDE_PROJECTS}/")
    jsonl_files = find_jsonl_files()
    print(f"Found {len(jsonl_files)} session transcripts")

    # Step 3: Scan each file
    all_updates = []
    files_with_matches = 0
    files_scanned = 0

    for filepath in jsonl_files:
        files_scanned += 1
        updates = scan_jsonl_file(filepath, target_graph_ids, target_node_ids)
        if updates:
            files_with_matches += 1
            all_updates.extend(updates)
            matched_nodes = {u["node_id"] for u in updates}
            print(f"  {filepath.parent.name}/{filepath.name}: {len(updates)} matches ({len(matched_nodes)} nodes)")

        # Progress every 50 files
        if files_scanned % 50 == 0:
            print(f"  ... scanned {files_scanned}/{len(jsonl_files)} files, {len(all_updates)} matches so far")

    print(f"\nScan complete: {files_scanned} files scanned, {files_with_matches} had matches")
    print(f"Total raw matches: {len(all_updates)}")

    # Step 4: Merge updates
    merged = merge_updates(all_updates)
    print(f"Unique nodes matched: {len(merged)}")

    # Step 5: Show summary
    nodes_with_session = sum(1 for r in merged.values() if r["session_id"])
    nodes_with_claimed = sum(1 for r in merged.values() if r["claimed_at"])
    nodes_with_answered = sum(1 for r in merged.values() if r["answered_at"])
    nodes_with_synthesized = sum(1 for r in merged.values() if r["synthesized_at"])
    unmatched = len(target_node_ids) - len(merged)

    print(f"\nBackfill summary:")
    print(f"  session_id:     {nodes_with_session} nodes")
    print(f"  claimed_at:     {nodes_with_claimed} nodes")
    print(f"  answered_at:    {nodes_with_answered} nodes")
    print(f"  synthesized_at: {nodes_with_synthesized} nodes")
    print(f"  unmatched:      {unmatched} nodes (no JSONL match found)")

    if unmatched > 0:
        unmatched_by_graph = {}
        for node_id in target_node_ids - set(merged.keys()):
            gid = nodes[node_id]["graph_id"]
            unmatched_by_graph.setdefault(gid, []).append(node_id)
        print(f"\n  Unmatched by graph:")
        for gid, nids in sorted(unmatched_by_graph.items()):
            print(f"    {gid}: {len(nids)} nodes")

    # Step 6: Apply or show dry-run
    if merged:
        print(f"\n{'Applying' if apply else 'Would apply'} {len(merged)} updates:")
        updated = apply_updates(FRACTAL_DB, merged, dry_run=not apply)
        if apply:
            print(f"\nDone. Updated {updated} nodes in {FRACTAL_DB}")
        else:
            print(f"\nDry-run complete. Run with --apply to write {updated} updates to the database.")


if __name__ == "__main__":
    main()
