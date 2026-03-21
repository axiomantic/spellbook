"""Memory consolidation pipeline.

Batch-extracts structured memories from raw events via heuristic strategies.
Handles dedup, bibliographic coupling, FTS5 sync, and error recovery.
Client-side LLM synthesis available via memory_get_unconsolidated/memory_store_memories tools.
"""

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, TypedDict

from sqlalchemy import func, select

from spellbook.db.engines import get_sync_session
from spellbook.db.spellbook_models import (
    Memory,
    MemoryCitation,
    RawEvent,
)
from spellbook.memory.store import (
    get_unconsolidated_events,
    insert_memory,
    insert_branch_association,
    insert_link,
    mark_events_consolidated,
    log_audit,
    purge_deleted,
    _content_hash,
)

EVENT_THRESHOLD = 10

# --- Heuristic consolidation thresholds ---

# Jaccard similarity threshold for near-duplicate detection.
# 0.6 chosen over 0.8 because memory events often describe the same concept
# with different wording (e.g., "edited auth module" vs "modified authentication code").
SIMILARITY_THRESHOLD = 0.6

# Tag overlap boost added to Jaccard score when events share >= 50% of tags.
TAG_OVERLAP_BOOST = 0.1

# Minimum shared tags for tag-based grouping.
MIN_SHARED_TAGS = 2

# Maximum time gap (in minutes) between events in a temporal cluster.
TEMPORAL_GAP_MINUTES = 30

# Minimum meaningful words after stop-word filtering for Jaccard comparison.
MIN_MEANINGFUL_WORDS = 3

# Stop words for keyword extraction (inlined from context_filtering to avoid coupling).
_STOP_WORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "have", "he", "in", "is", "it", "its", "of", "on", "or",
    "that", "the", "to", "was", "were", "will", "with",
})


class StrategyMemory(TypedDict):
    """Structure returned by each heuristic strategy for a grouped memory.

    Documents expected key structure across all 4 strategies, enabling
    static type checkers to catch key typos (e.g., 'citation' vs 'citations').
    """
    content: str
    memory_type: str
    tags: List[str]
    citations: List[Dict[str, Any]]
    event_ids: List[int]
    strategy: str
    branches: List[str]


def _extract_keywords(text: str) -> set:
    """Extract meaningful keywords from text, filtering stop words and short words."""
    return {w for w in text.lower().split() if w not in _STOP_WORDS and len(w) > 2}


def _event_text(event: Dict[str, Any]) -> str:
    """Build comparable text from an event's subject and summary."""
    return f"{event['subject']}: {event['summary']}"


# Known file extensions for citation extraction.
# Avoids false positives from version strings like "v2.0 release" or "section 3.1".
_FILE_EXTENSIONS = frozenset({
    ".py", ".ts", ".js", ".jsx", ".tsx", ".md", ".toml", ".yaml", ".yml",
    ".json", ".cfg", ".ini", ".txt", ".rst", ".html", ".css", ".scss",
    ".sh", ".bash", ".zsh", ".sql", ".graphql", ".proto", ".go", ".rs",
    ".java", ".kt", ".swift", ".c", ".cpp", ".h", ".hpp",
})


def _extract_citations(subject: str) -> List[Dict[str, Any]]:
    """Extract file path citations from a subject string.

    Matches subjects that look like file paths: contain a path separator (/)
    or end with a known file extension. The broad `"." in subject` check was
    removed to prevent false positives on version strings (e.g., "v2.0 release")
    and section references (e.g., "section 3.1").
    """
    # Path separator is a strong signal
    if "/" in subject:
        return [{"file_path": subject}]
    # Check for known file extensions (case-insensitive)
    subject_lower = subject.lower()
    for ext in _FILE_EXTENSIONS:
        if subject_lower.endswith(ext):
            return [{"file_path": subject}]
    return []


def _merge_event_metadata(
    group_events: List[Dict[str, Any]],
) -> tuple[set, List[int], List[Dict[str, Any]], set]:
    """Extract and deduplicate tags, event IDs, citations, and branches from a group of events.

    Returns (tags_set, event_ids, citations, branches_set).
    """
    all_tags: set = set()
    all_event_ids: List[int] = []
    all_citations: List[Dict[str, Any]] = []
    all_branches: set = set()

    for e in group_events:
        if e.get("tags"):
            all_tags.update(t.strip() for t in e["tags"].split(",") if t.strip())
        all_event_ids.append(e["id"])
        all_citations.extend(_extract_citations(e["subject"]))
        branch = e.get("branch", "")
        if branch:
            all_branches.add(branch)

    # Deduplicate citations by file_path
    seen_paths: set = set()
    unique_citations: List[Dict[str, Any]] = []
    for c in all_citations:
        if c["file_path"] not in seen_paths:
            seen_paths.add(c["file_path"])
            unique_citations.append(c)

    return all_tags, all_event_ids, unique_citations, all_branches


def _strategy_content_hash_dedup(
    events: List[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Strategy 1: Exact-match dedup using SHA-256 of normalized content.

    Returns (memories, unconsumed_events).
    Each group of identical events produces one memory from the first event.
    """
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for event in events:
        text = _event_text(event)
        h = _content_hash(text)
        groups.setdefault(h, []).append(event)

    memories = []
    unconsumed = []
    for h, group in groups.items():
        if len(group) > 1:
            # Duplicate group: produce one memory from first event
            first = group[0]
            all_tags, all_event_ids, all_citations, all_branches = _merge_event_metadata(group)
            memories.append({
                "content": f"[{first['tool_name']}] {_event_text(first)}",
                "memory_type": "fact",
                "tags": sorted(all_tags),
                "citations": all_citations,
                "event_ids": all_event_ids,
                "strategy": "content_hash",
                "branches": sorted(all_branches),
            })
        else:
            unconsumed.append(group[0])

    return memories, unconsumed


def _strategy_jaccard_similarity(
    events: List[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Strategy 2: Near-duplicate detection using Jaccard similarity with union-find.

    Returns (memories, unconsumed_events).
    """
    if len(events) < 2:
        return [], events

    # Extract keyword sets, skipping events with too few meaningful words
    event_keywords: Dict[int, set] = {}
    too_short = []
    for i, event in enumerate(events):
        keywords = _extract_keywords(_event_text(event))
        if len(keywords) < MIN_MEANINGFUL_WORDS:
            too_short.append(event)
        else:
            event_keywords[i] = keywords

    if len(event_keywords) < 2:
        return [], events

    # Parse tags for tag-overlap boost
    event_tags: Dict[int, set] = {}
    for i in event_keywords:
        tags_str = events[i].get("tags", "")
        event_tags[i] = {t.strip() for t in tags_str.split(",") if t.strip()} if tags_str else set()

    # Union-find
    parent = {i: i for i in event_keywords}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    # Pairwise comparison
    indices = sorted(event_keywords.keys())
    for a_idx in range(len(indices)):
        for b_idx in range(a_idx + 1, len(indices)):
            i, j = indices[a_idx], indices[b_idx]
            kw_i, kw_j = event_keywords[i], event_keywords[j]
            intersection = len(kw_i & kw_j)
            union_size = len(kw_i | kw_j)
            sim = intersection / union_size if union_size else 0.0

            # Tag overlap boost
            tags_i, tags_j = event_tags[i], event_tags[j]
            if tags_i and tags_j:
                tag_overlap = len(tags_i & tags_j) / min(len(tags_i), len(tags_j))
                if tag_overlap >= 0.5:
                    sim += TAG_OVERLAP_BOOST

            if sim >= SIMILARITY_THRESHOLD:
                union(i, j)

    # Group by root
    groups: Dict[int, List[int]] = {}
    for i in event_keywords:
        root = find(i)
        groups.setdefault(root, []).append(i)

    memories = []
    unconsumed = list(too_short)
    for root, member_indices in groups.items():
        if len(member_indices) > 1:
            group_events = [events[i] for i in member_indices]
            # Merge: concatenate unique sentences, union tags
            seen_texts = set()
            content_parts = []
            for e in group_events:
                text = _event_text(e)
                if text not in seen_texts:
                    seen_texts.add(text)
                    content_parts.append(f"[{e['tool_name']}] {text}")

            all_tags, all_event_ids, all_citations, all_branches = _merge_event_metadata(group_events)

            memories.append({
                "content": "; ".join(content_parts),
                "memory_type": "fact",
                "tags": sorted(all_tags),
                "citations": all_citations,
                "event_ids": all_event_ids,
                "strategy": "jaccard_similarity",
                "branches": sorted(all_branches),
            })
        else:
            unconsumed.append(events[member_indices[0]])

    return memories, unconsumed


def _strategy_tag_grouping(
    events: List[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Strategy 3: Group events sharing significant tag overlap.

    Returns (memories, unconsumed_events).
    """
    # Parse tags for each event
    event_tag_sets: List[tuple[int, set]] = []
    no_tags = []
    for i, event in enumerate(events):
        tags_str = event.get("tags", "")
        tags = {t.strip() for t in tags_str.split(",") if t.strip()} if tags_str else set()
        if tags:
            event_tag_sets.append((i, tags))
        else:
            no_tags.append(event)

    if len(event_tag_sets) < 2:
        return [], events

    # Union-find for tag grouping
    parent = {i: i for i, _ in event_tag_sets}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    # Check pairwise tag overlap
    for a_idx in range(len(event_tag_sets)):
        for b_idx in range(a_idx + 1, len(event_tag_sets)):
            i, tags_i = event_tag_sets[a_idx]
            j, tags_j = event_tag_sets[b_idx]
            shared = len(tags_i & tags_j)
            if shared >= MIN_SHARED_TAGS:
                union(i, j)

    # Group by root
    groups: Dict[int, List[int]] = {}
    for i, _ in event_tag_sets:
        root = find(i)
        groups.setdefault(root, []).append(i)

    memories = []
    unconsumed = list(no_tags)
    for root, member_indices in groups.items():
        if len(member_indices) > 1:
            group_events = [events[i] for i in member_indices]
            # Bullet list of unique subjects
            seen_subjects = set()
            bullet_lines = []
            for e in group_events:
                if e["subject"] not in seen_subjects:
                    seen_subjects.add(e["subject"])
                    bullet_lines.append(f"- {e['subject']}: {e['summary']}")

            all_tags, all_event_ids, all_citations, all_branches = _merge_event_metadata(group_events)

            memories.append({
                "content": "Related activities:\n" + "\n".join(bullet_lines),
                "memory_type": "fact",
                "tags": sorted(all_tags),
                "citations": all_citations,
                "event_ids": all_event_ids,
                "strategy": "tag_grouping",
                "branches": sorted(all_branches),
            })
        else:
            unconsumed.append(events[member_indices[0]])

    return memories, unconsumed


def _strategy_temporal_clustering(
    events: List[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Strategy 4: Group events by session + subject within time windows.

    Returns (memories, unconsumed_events).
    Single-event clusters produce a memory from the single event (fallback).
    """
    # Group by (session_id, subject)
    groups: Dict[tuple, List[Dict[str, Any]]] = {}
    for event in events:
        key = (event.get("session_id", ""), event["subject"])
        groups.setdefault(key, []).append(event)

    memories = []
    for key, group in groups.items():
        # Sort by timestamp
        group.sort(key=lambda e: e.get("timestamp", ""))

        # Split into temporal clusters
        clusters: List[List[Dict[str, Any]]] = [[group[0]]]
        for event in group[1:]:
            prev_ts = clusters[-1][-1].get("timestamp", "")
            curr_ts = event.get("timestamp", "")
            try:
                # Parse ISO timestamps
                prev_dt = datetime.fromisoformat(prev_ts)
                curr_dt = datetime.fromisoformat(curr_ts)
                gap_minutes = (curr_dt - prev_dt).total_seconds() / 60
            except (ValueError, TypeError):
                gap_minutes = 0  # Can't parse, assume same cluster

            if gap_minutes > TEMPORAL_GAP_MINUTES:
                clusters.append([event])
            else:
                clusters[-1].append(event)

        for cluster in clusters:
            all_tags = set()
            all_event_ids = []
            all_branches = set()
            summaries = []
            for e in cluster:
                summaries.append(e["summary"])
                if e.get("tags"):
                    all_tags.update(t.strip() for t in e["tags"].split(",") if t.strip())
                all_event_ids.append(e["id"])
                branch = e.get("branch", "")
                if branch:
                    all_branches.add(branch)

            first = cluster[0]
            if len(cluster) == 1:
                content = f"[{first['tool_name']}] {_event_text(first)}"
            else:
                unique_summaries = list(dict.fromkeys(summaries))
                content = (
                    f"Session activity on {first['subject']}: "
                    + "; ".join(unique_summaries)
                )

            memories.append({
                "content": content,
                "memory_type": "fact",
                "tags": sorted(all_tags),
                "citations": _extract_citations(first["subject"]),
                "event_ids": all_event_ids,
                "strategy": "temporal_clustering",
                "branches": sorted(all_branches),
            })

    return memories, []  # Temporal clustering consumes all remaining events


def should_consolidate(db_path: str) -> bool:
    """Check if there are enough unconsolidated events to trigger consolidation."""
    with get_sync_session(db_path) as session:
        count = session.scalar(
            select(func.count()).select_from(RawEvent).where(RawEvent.consolidated == 0)
        )
        return count >= EVENT_THRESHOLD


def build_consolidation_prompt(events: List[Dict[str, Any]]) -> str:
    """Build a consolidation prompt from raw events for client-side LLM synthesis."""
    observations = []
    for e in events:
        line = f"- [{e['tool_name']}] {e['subject']}: {e['summary']}"
        if e.get("tags"):
            line += f" (tags: {e['tags']})"
        if e.get("branch"):
            line += f" [branch: {e['branch']}]"
        observations.append(line)

    return (
        "Given these tool observations from a coding session, extract structured memories.\n"
        "For each distinct fact, rule, pattern, or decision observed:\n"
        "- content: the memory as a clear, standalone statement\n"
        "- memory_type: one of fact/rule/antipattern/preference/decision\n"
        "- tags: 3-5 keywords for retrieval\n"
        "- citations: file paths referenced, with line ranges and 1-3 line snippets\n\n"
        'Return JSON: {"memories": [{"content": "...", "memory_type": "...", '
        '"tags": [...], "citations": [{"file_path": "...", "line_range": "...", '
        '"snippet": "..."}]}]}\n\n'
        "Observations:\n" + "\n".join(observations)
    )


def parse_llm_response(response: str) -> List[Dict[str, Any]]:
    """Parse and validate a JSON response into memory dicts. Returns empty list on failure.

    Used by memory_store_memories to validate client input.
    """
    try:
        data = json.loads(response)
    except (json.JSONDecodeError, TypeError):
        return []

    memories = data.get("memories", [])
    result = []
    for mem in memories:
        if not isinstance(mem, dict) or not mem.get("content"):
            continue
        result.append({
            "content": mem["content"],
            "memory_type": mem.get("memory_type", "fact"),
            "tags": mem.get("tags", []),
            "citations": mem.get("citations", []),
        })
    return result


def compute_bibliographic_coupling(
    db_path: str, memory_id: str
) -> List[Dict[str, Any]]:
    """Find other memories sharing file citations with this memory.

    Returns list of {other_id, weight} where weight is Jaccard similarity
    of cited file paths.
    """
    with get_sync_session(db_path) as session:
        # Get file paths cited by this memory
        my_files_rows = session.execute(
            select(MemoryCitation.file_path).where(
                MemoryCitation.memory_id == memory_id
            )
        ).scalars().all()
        my_files = set(my_files_rows)
        if not my_files:
            return []

        # Find other memories citing any of the same files
        stmt = (
            select(MemoryCitation.memory_id, MemoryCitation.file_path)
            .join(Memory, Memory.id == MemoryCitation.memory_id)
            .where(
                MemoryCitation.file_path.in_(my_files),
                MemoryCitation.memory_id != memory_id,
                Memory.status == "active",
            )
            .distinct()
        )
        rows = session.execute(stmt).all()

        # Group by other memory
        other_files: Dict[str, set] = {}
        for row in rows:
            other_files.setdefault(row[0], set()).add(row[1])

        links = []
        for other_id, _their_shared_files in other_files.items():
            # Get ALL files for the other memory (not just shared)
            all_their_files_rows = session.execute(
                select(MemoryCitation.file_path).where(
                    MemoryCitation.memory_id == other_id
                )
            ).scalars().all()
            all_their_files = set(all_their_files_rows)
            union = my_files | all_their_files
            intersection = my_files & all_their_files
            weight = len(intersection) / len(union) if union else 0
            if weight > 0:
                links.append({"other_id": other_id, "weight": weight})

        return links


def consolidate_batch(
    db_path: str,
    namespace: str,
    event_limit: int = 50,
) -> Dict[str, Any]:
    """Run one consolidation batch using heuristic strategies.

    Intentionally synchronous: this is a background batch operation,
    not an MCP request handler. The MCP server calls this via
    asyncio.to_thread() to avoid blocking the event loop.

    Pipeline ordering (cheapest/most-certain first):
    1. Content-hash dedup (O(n), zero false positives)
    2. Jaccard similarity (O(n^2), near-duplicate detection)
    3. Tag grouping (topical clustering by shared tags)
    4. Temporal clustering (session + time window + subject)

    Returns dict with status, counts, and any errors.
    """
    events = get_unconsolidated_events(db_path, limit=event_limit, namespace=namespace)
    if not events:
        return {"status": "no_events", "events_consolidated": 0, "memories_created": 0}

    batch_id = str(uuid.uuid4())
    event_ids = [e["id"] for e in events]

    # CRITICAL: Wrap the entire heuristic pipeline in try/except to mirror the
    # error handling of the old LLM-based consolidate_batch(). On failure:
    # 1. Log error via log_audit() for observability
    # 2. Mark events as consolidated even on failure (prevents infinite retry loop)
    # 3. Return error status dict so callers can detect and handle failures
    try:
        all_memories: List[StrategyMemory] = []

        # Strategy 1: Content-hash dedup
        memories_1, remaining = _strategy_content_hash_dedup(events)
        all_memories.extend(memories_1)

        # Strategy 2: Jaccard similarity
        if remaining:
            memories_2, remaining = _strategy_jaccard_similarity(remaining)
            all_memories.extend(memories_2)

        # Strategy 3: Tag grouping
        if remaining:
            memories_3, remaining = _strategy_tag_grouping(remaining)
            all_memories.extend(memories_3)

        # Strategy 4: Temporal clustering (consumes all remaining)
        if remaining:
            memories_4, remaining = _strategy_temporal_clustering(remaining)
            all_memories.extend(memories_4)

        # Insert memories and compute bibliographic coupling
        created_ids = []
        for mem in all_memories:
            branches = mem.get("branches", [])
            origin_branch = branches[0] if branches else ""

            mem_id = insert_memory(
                db_path=db_path,
                content=mem["content"],
                memory_type=mem["memory_type"],
                namespace=namespace,
                tags=mem["tags"],
                citations=mem["citations"],
                extra_meta={
                    "source": "heuristic",
                    "strategy": mem["strategy"],
                    "event_count": len(mem["event_ids"]),
                    "batch_id": batch_id,
                },
                branch=origin_branch,
            )
            created_ids.append(mem_id)

            # Add all contributing branches to junction table
            for branch_name in branches:
                if branch_name != origin_branch:
                    insert_branch_association(db_path, mem_id, branch_name, "origin")


        # Compute bibliographic coupling for new memories
        for mem_id in created_ids:
            links = compute_bibliographic_coupling(db_path, mem_id)
            for link in links:
                insert_link(
                    db_path, mem_id, link["other_id"],
                    "bibliographic", link["weight"],
                )

    except Exception as exc:
        # Log the error for debugging
        log_audit(db_path, "consolidation_error", details={
            "batch_id": batch_id,
            "error": str(exc),
            "events_count": len(event_ids),
        })
        # Mark events consolidated even on failure to prevent infinite retry.
        # These events can be re-processed via memory_get_unconsolidated with
        # include_consolidated=True if needed.
        mark_events_consolidated(db_path, event_ids, batch_id, namespace=namespace)
        return {
            "status": "error",
            "batch_id": batch_id,
            "error": str(exc),
            "events_consolidated": len(event_ids),
            "memories_created": 0,
        }

    mark_events_consolidated(db_path, event_ids, batch_id, namespace=namespace)

    # Piggyback GC
    purged = purge_deleted(db_path)

    # Log consolidation metrics
    compression_ratio = len(created_ids) / len(event_ids) if event_ids else 0
    log_audit(db_path, "consolidation_complete", details={
        "batch_id": batch_id,
        "events_consolidated": len(event_ids),
        "memories_created": len(created_ids),
        "compression_ratio": round(compression_ratio, 3),
        "strategies_used": list({m["strategy"] for m in all_memories}),
    })

    return {
        "status": "success",
        "batch_id": batch_id,
        "events_consolidated": len(event_ids),
        "memories_created": len(created_ids),
        "purged": purged,
    }
