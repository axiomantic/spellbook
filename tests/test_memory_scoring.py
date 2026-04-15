"""Tests for confidence decay and its multiplier contribution in scoring.

Gap 1: time-based confidence decay.

- New memories default to confidence="high" when stored.
- At query time, decay is applied lazily based on last_verified (or created
  as a fallback):
    <= 30 days -> high  (multiplier 1.0)
    30 < days <= 90 -> medium (multiplier 0.7)
    > 90 days -> low (multiplier 0.4)
- Frontmatter is NOT rewritten; decay is purely computed at score time.
- Missing confidence is treated as "high" (safety net).
- STILL_TRUE verdict in the sync pipeline refreshes last_verified to today.

TDD RED phase: all tests written before implementation.
"""

import datetime
import os

from spellbook.memory.filestore import store_memory, read_memory
from spellbook.memory.frontmatter import write_memory_file
from spellbook.memory.models import Citation, MemoryFile, MemoryFrontmatter
from spellbook.memory.scoring import (
    compute_confidence_multiplier,
    compute_score,
    effective_confidence,
)
from spellbook.memory.sync_pipeline import apply_sync_results
from spellbook.memory.utils import content_hash as _content_hash


# ---------------------------------------------------------------------------
# effective_confidence + compute_confidence_multiplier
# ---------------------------------------------------------------------------


def test_confidence_multiplier_high_recent():
    """Recent memory with confidence=high keeps a full 1.0 multiplier."""
    today = datetime.date.today()
    fm = MemoryFrontmatter(
        type="project",
        created=today - datetime.timedelta(days=120),  # old, but verified recently
        last_verified=today,
        confidence="high",
    )
    assert effective_confidence(fm, today=today) == "high"
    assert compute_confidence_multiplier(fm, today=today) == 1.0


def test_confidence_decay_30_days():
    """At 31 days since last_verified, confidence degrades to medium."""
    today = datetime.date.today()
    fm = MemoryFrontmatter(
        type="project",
        created=today - datetime.timedelta(days=200),
        last_verified=today - datetime.timedelta(days=31),
        confidence="high",
    )
    assert effective_confidence(fm, today=today) == "medium"
    assert compute_confidence_multiplier(fm, today=today) == 0.7


def test_confidence_decay_90_days():
    """At 91 days since last_verified, confidence degrades to low."""
    today = datetime.date.today()
    fm = MemoryFrontmatter(
        type="project",
        created=today - datetime.timedelta(days=400),
        last_verified=today - datetime.timedelta(days=91),
        confidence="high",
    )
    assert effective_confidence(fm, today=today) == "low"
    assert compute_confidence_multiplier(fm, today=today) == 0.4


def test_confidence_missing_defaults_high():
    """A memory with confidence=None, recently verified, is treated as high."""
    today = datetime.date.today()
    fm = MemoryFrontmatter(
        type="project",
        created=today - datetime.timedelta(days=10),
        last_verified=today,
        confidence=None,
    )
    assert effective_confidence(fm, today=today) == "high"
    assert compute_confidence_multiplier(fm, today=today) == 1.0


def test_fallback_to_created_when_unverified():
    """When last_verified is None, decay uses created date."""
    today = datetime.date.today()
    fm = MemoryFrontmatter(
        type="project",
        created=today - datetime.timedelta(days=31),
        last_verified=None,
        confidence="high",
    )
    assert effective_confidence(fm, today=today) == "medium"
    assert compute_confidence_multiplier(fm, today=today) == 0.7


# ---------------------------------------------------------------------------
# compute_score integration: multiplier composes with temporal + branch
# ---------------------------------------------------------------------------


def test_compute_score_applies_confidence_multiplier():
    """Final score = temporal_score(existing) * confidence_mult * branch_mult.

    Holding temporal and branch factors equal, a memory with a degraded
    effective confidence must score exactly 0.4x a recent-verified equivalent.
    """
    today = datetime.date.today()
    # Both memories have the same created date so temporal decay is identical.
    created = today - datetime.timedelta(days=400)

    fm_fresh = MemoryFrontmatter(
        type="project",
        created=created,
        last_verified=today,
        confidence="high",
        tags=["alpha"],
    )
    fm_stale = MemoryFrontmatter(
        type="project",
        created=created,
        last_verified=today - datetime.timedelta(days=91),
        confidence="high",
        tags=["alpha"],
    )
    mf_fresh = MemoryFile(
        path="fresh.md", frontmatter=fm_fresh, content="retry retry strategy"
    )
    mf_stale = MemoryFile(
        path="stale.md", frontmatter=fm_stale, content="retry retry strategy"
    )

    score_fresh = compute_score(mf_fresh, ["retry"], current_branch=None)
    score_stale = compute_score(mf_stale, ["retry"], current_branch=None)

    # Fresh: multiplier 1.0; stale: 0.4. Ratio must be exactly 0.4.
    assert score_fresh > 0.0
    assert score_stale == score_fresh * 0.4


# ---------------------------------------------------------------------------
# store_memory default + preservation
# ---------------------------------------------------------------------------


def test_store_memory_defaults_confidence_high(tmp_path):
    """store_memory() with no confidence kw stores frontmatter.confidence='high'."""
    result = store_memory(
        content="We always emit a correlation id on outbound HTTP calls.",
        type="project",
        kind="convention",
        citations=[Citation(file="src/http.py")],
        tags=["http", "observability"],
        scope="project",
        branch="main",
        memory_dir=str(tmp_path),
    )
    assert result.frontmatter.confidence == "high"
    # Re-read from disk to confirm it was persisted, not just in-memory.
    reloaded = read_memory(result.path)
    assert reloaded.frontmatter.confidence == "high"


def test_store_memory_preserves_caller_confidence(tmp_path):
    """Caller-supplied confidence='low' is preserved exactly."""
    result = store_memory(
        content="The legacy payout retry loop may be wrong; verify before trusting.",
        type="project",
        kind="fact",
        citations=[Citation(file="src/legacy.py")],
        tags=["legacy"],
        scope="project",
        branch="main",
        memory_dir=str(tmp_path),
        confidence="low",
    )
    assert result.frontmatter.confidence == "low"
    reloaded = read_memory(result.path)
    assert reloaded.frontmatter.confidence == "low"


# ---------------------------------------------------------------------------
# sync_pipeline STILL_TRUE updates last_verified
# ---------------------------------------------------------------------------


def _seed_memory(memory_dir: str, slug: str, content: str) -> str:
    """Write a memory file with last_verified unset; return its abs path."""
    fm = MemoryFrontmatter(
        type="project",
        created=datetime.date(2026, 1, 1),
        kind="fact",
        citations=[Citation(file="src/db.py")],
        tags=["db"],
        scope="project",
        branch=None,
        last_verified=None,
        confidence="high",
        content_hash=_content_hash(content),
    )
    path = os.path.join(memory_dir, "project", f"{slug}.md")
    write_memory_file(path, fm, content)
    return path


def test_still_true_updates_last_verified(tmp_path):
    """A STILL_TRUE verdict stamps last_verified to today's date."""
    memory_dir = str(tmp_path / "memories")
    project_root = str(tmp_path / "project")
    os.makedirs(project_root)

    content = "The database connection pool uses a maximum of 10 connections."
    mem_path = _seed_memory(memory_dir, "db-pool", content)

    # Sanity: last_verified is not set before the sync.
    before = read_memory(mem_path)
    assert before.frontmatter.last_verified is None

    results = {
        "verdicts": [
            {
                "memory_path": mem_path,
                "verdict": "STILL_TRUE",
                "reason": "Pool config unchanged.",
            }
        ],
        "new_memories": [],
    }

    report = apply_sync_results(
        results=results,
        memory_dir=memory_dir,
        project_root=project_root,
    )
    assert report.memories_unchanged == 1
    assert report.memories_updated == 0
    assert report.memories_archived == 0
    assert report.errors == []

    after = read_memory(mem_path)
    assert after.frontmatter.last_verified == datetime.date.today()
    # created must NOT be touched.
    assert after.frontmatter.created == datetime.date(2026, 1, 1)
    # Content must NOT be touched.
    assert after.content.strip() == content


def test_still_true_no_op_when_already_verified_today(tmp_path):
    """STILL_TRUE skips the rewrite when last_verified is already today."""
    memory_dir = str(tmp_path / "memories")
    project_root = str(tmp_path / "project")
    os.makedirs(project_root)

    content = "The database connection pool uses a maximum of 10 connections."
    today = datetime.date.today()

    # Seed a memory whose last_verified is already today.
    fm = MemoryFrontmatter(
        type="project",
        created=datetime.date(2026, 1, 1),
        kind="fact",
        citations=[Citation(file="src/db.py")],
        tags=["db"],
        scope="project",
        branch=None,
        last_verified=today,
        confidence="high",
        content_hash=_content_hash(content),
    )
    mem_path = os.path.join(memory_dir, "project", "db-pool.md")
    write_memory_file(mem_path, fm, content)

    # Capture mtime and bytes before the sync.
    mtime_before = os.stat(mem_path).st_mtime_ns
    with open(mem_path, "rb") as f:
        bytes_before = f.read()

    results = {
        "verdicts": [
            {
                "memory_path": mem_path,
                "verdict": "STILL_TRUE",
                "reason": "Pool config unchanged.",
            }
        ],
        "new_memories": [],
    }

    report = apply_sync_results(
        results=results,
        memory_dir=memory_dir,
        project_root=project_root,
    )

    # Counted as unchanged, not updated.
    assert report.memories_unchanged == 1
    assert report.memories_updated == 0
    assert report.memories_archived == 0
    assert report.errors == []

    # File must not have been rewritten: mtime and content identical.
    mtime_after = os.stat(mem_path).st_mtime_ns
    with open(mem_path, "rb") as f:
        bytes_after = f.read()
    assert mtime_after == mtime_before
    assert bytes_after == bytes_before
