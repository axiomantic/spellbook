"""Tests for the 4-phase sync pipeline.

Covers: Phase 1 (diff-to-citation mapping), Phase 2 (fact-check context),
Phase 3 (discovery context), Phase 4 (quality gate), memory_sync orchestrator,
and apply_sync_results.

TDD RED phase: all tests written before implementation.
"""

import datetime
import hashlib
import os

import pytest
import yaml

from spellbook.memory.diff_symbols import SymbolChange
from spellbook.memory.frontmatter import write_memory_file
from spellbook.memory.models import Citation, MemoryFrontmatter
from spellbook.memory.sync_pipeline import (
    FactCheckItem,
    SyncPhase1Result,
    SyncPhase2Result,
    SyncPhase3Result,
    SyncPhase4Result,
    SyncPlan,
    SyncReport,
    apply_sync_results,
    memory_sync,
    phase1_find_at_risk,
    phase2_prepare_factcheck,
    phase3_prepare_discovery,
    phase4_quality_gate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _content_hash(content: str) -> str:
    """Compute content hash the same way filestore does."""
    normalized = " ".join(content.lower().split())
    return "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _write_test_memory(
    memory_dir: str,
    type_dir: str,
    slug: str,
    content: str,
    citations: list[dict] | None = None,
    tags: list[str] | None = None,
    kind: str | None = None,
    branch: str | None = None,
) -> str:
    """Write a test memory file and return its path."""
    fm = MemoryFrontmatter(
        type=type_dir,
        created=datetime.date(2026, 4, 14),
        kind=kind or "fact",
        citations=[
            Citation(
                file=c["file"],
                symbol=c.get("symbol"),
                symbol_type=c.get("symbol_type"),
            )
            for c in (citations or [])
        ],
        tags=tags or [],
        scope="project",
        branch=branch,
        content_hash=_content_hash(content),
    )
    path = os.path.join(memory_dir, type_dir, f"{slug}.md")
    write_memory_file(path, fm, content)
    return path


def _write_source_file(project_root: str, rel_path: str, content: str) -> str:
    """Write a source file in the project root and return its abs path."""
    full = os.path.join(project_root, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as f:
        f.write(content)
    return full


# ---------------------------------------------------------------------------
# Phase 1: Diff-to-Citation Mapping
# ---------------------------------------------------------------------------


class TestPhase1FindAtRisk:
    """Phase 1: find at-risk memories based on file/symbol citations."""

    def test_finds_at_risk_memory_by_file_citation(self, tmp_path):
        """A memory citing a changed file is flagged as at-risk."""
        memory_dir = str(tmp_path / "memories")
        project_root = str(tmp_path / "project")
        os.makedirs(project_root)

        # Write a memory citing src/api.py
        _write_test_memory(
            memory_dir,
            "project",
            "api-retry-strategy",
            "We use exponential backoff for retries.",
            citations=[{"file": "src/api.py", "symbol": "retry", "symbol_type": "function"}],
        )

        # Simulate changed files
        changed_files = ["src/api.py", "src/utils.py"]
        symbol_changes = [
            SymbolChange(
                file="src/api.py",
                symbol_name="retry",
                change_type="modified",
                symbol_type="function",
                context="def retry(...):",
            ),
        ]

        result = phase1_find_at_risk(
            project_root=project_root,
            memory_dir=memory_dir,
            changed_files=changed_files,
            symbol_changes=symbol_changes,
        )

        assert isinstance(result, SyncPhase1Result)
        assert len(result.at_risk_memories) == 1
        assert result.at_risk_memories[0].memory.content == "\nWe use exponential backoff for retries.\n"
        assert result.at_risk_memories[0].at_risk_citations == [
            Citation(file="src/api.py", symbol="retry", symbol_type="function"),
        ]
        assert result.changed_files == ["src/api.py", "src/utils.py"]
        assert result.changed_symbols == symbol_changes
        assert result.stats["at_risk_count"] == 1
        assert result.stats["changed_files_count"] == 2
        assert result.stats["changed_symbols_count"] == 1

    def test_returns_empty_when_no_files_match_citations(self, tmp_path):
        """No at-risk memories when changed files don't match any citation."""
        memory_dir = str(tmp_path / "memories")
        project_root = str(tmp_path / "project")
        os.makedirs(project_root)

        _write_test_memory(
            memory_dir,
            "project",
            "unrelated-memory",
            "Something about database migrations.",
            citations=[{"file": "src/db.py"}],
        )

        result = phase1_find_at_risk(
            project_root=project_root,
            memory_dir=memory_dir,
            changed_files=["src/api.py"],
            symbol_changes=[],
        )

        assert isinstance(result, SyncPhase1Result)
        assert result.at_risk_memories == []
        assert result.changed_files == ["src/api.py"]
        assert result.stats["at_risk_count"] == 0

    def test_multiple_memories_at_risk(self, tmp_path):
        """Multiple memories citing the same changed file are all flagged."""
        memory_dir = str(tmp_path / "memories")
        project_root = str(tmp_path / "project")
        os.makedirs(project_root)

        _write_test_memory(
            memory_dir,
            "project",
            "mem-one",
            "First memory about the API.",
            citations=[{"file": "src/api.py"}],
        )
        _write_test_memory(
            memory_dir,
            "project",
            "mem-two",
            "Second memory about the API client.",
            citations=[{"file": "src/api.py", "symbol": "Client", "symbol_type": "class"}],
        )

        result = phase1_find_at_risk(
            project_root=project_root,
            memory_dir=memory_dir,
            changed_files=["src/api.py"],
            symbol_changes=[],
        )

        assert result.stats["at_risk_count"] == 2
        memory_contents = sorted(m.memory.content.strip() for m in result.at_risk_memories)
        assert memory_contents == [
            "First memory about the API.",
            "Second memory about the API client.",
        ]

    def test_skips_archived_memories(self, tmp_path):
        """Memories in .archive/ are not flagged as at-risk."""
        memory_dir = str(tmp_path / "memories")
        project_root = str(tmp_path / "project")
        os.makedirs(project_root)

        # Write a memory in the archive
        archive_dir = os.path.join(memory_dir, ".archive", "project")
        os.makedirs(archive_dir, exist_ok=True)
        fm = MemoryFrontmatter(
            type="project",
            created=datetime.date(2026, 4, 14),
            citations=[Citation(file="src/api.py")],
            content_hash=_content_hash("Archived memory."),
        )
        write_memory_file(
            os.path.join(archive_dir, "archived.md"), fm, "Archived memory."
        )

        # Write a live memory that does NOT cite the changed file
        _write_test_memory(
            memory_dir,
            "project",
            "live-unrelated",
            "Unrelated live memory.",
            citations=[{"file": "src/other.py"}],
        )

        result = phase1_find_at_risk(
            project_root=project_root,
            memory_dir=memory_dir,
            changed_files=["src/api.py"],
            symbol_changes=[],
        )

        assert result.at_risk_memories == []


# ---------------------------------------------------------------------------
# Phase 2: Fact-Check Context Preparation
# ---------------------------------------------------------------------------


class TestPhase2PrepareFactcheck:
    """Phase 2: assemble fact-check context for each at-risk memory."""

    def test_assembles_factcheck_context_with_diff(self, tmp_path):
        """Fact-check item includes memory content, citations, and diff."""
        memory_dir = str(tmp_path / "memories")
        project_root = str(tmp_path / "project")

        mem_path = _write_test_memory(
            memory_dir,
            "project",
            "retry-strategy",
            "We use exponential backoff with jitter.",
            citations=[{"file": "src/api.py", "symbol": "retry", "symbol_type": "function"}],
        )

        # Write the cited source file so snippet can be read
        _write_source_file(
            project_root,
            "src/api.py",
            "def retry(attempt):\n    return 2 ** attempt\n",
        )

        # Build AtRiskMemory
        from spellbook.memory.search_serena import AtRiskMemory
        from spellbook.memory.filestore import read_memory

        mf = read_memory(mem_path)
        at_risk = [
            AtRiskMemory(
                memory=mf,
                at_risk_citations=[Citation(file="src/api.py", symbol="retry", symbol_type="function")],
                reason="cited_file_changed",
                relevant_diff="- def retry(attempt):\n+ def retry(attempt, jitter=True):",
            )
        ]

        result = phase2_prepare_factcheck(
            at_risk=at_risk,
            project_root=project_root,
        )

        assert isinstance(result, SyncPhase2Result)
        assert result.total_at_risk == 1
        assert len(result.factcheck_items) == 1

        item = result.factcheck_items[0]
        assert isinstance(item, FactCheckItem)
        assert item.memory_path == mem_path
        assert item.memory_content == "\nWe use exponential backoff with jitter.\n"
        assert item.citations == [Citation(file="src/api.py", symbol="retry", symbol_type="function")]
        assert item.relevant_diff == "- def retry(attempt):\n+ def retry(attempt, jitter=True):"
        assert "def retry(attempt):" in item.current_code_snippet
        assert "STILL_TRUE" in item.prompt
        assert "NEEDS_UPDATE" in item.prompt

    def test_handles_missing_cited_file(self, tmp_path):
        """When cited file is deleted, snippet is empty and item still generated."""
        memory_dir = str(tmp_path / "memories")
        project_root = str(tmp_path / "project")
        os.makedirs(project_root)

        mem_path = _write_test_memory(
            memory_dir,
            "project",
            "deleted-ref",
            "This references a file that was deleted.",
            citations=[{"file": "src/gone.py", "symbol": "old_func", "symbol_type": "function"}],
        )

        from spellbook.memory.search_serena import AtRiskMemory
        from spellbook.memory.filestore import read_memory

        mf = read_memory(mem_path)
        at_risk = [
            AtRiskMemory(
                memory=mf,
                at_risk_citations=[Citation(file="src/gone.py", symbol="old_func", symbol_type="function")],
                reason="cited_file_changed",
                relevant_diff="- def old_func(): pass",
            )
        ]

        result = phase2_prepare_factcheck(
            at_risk=at_risk,
            project_root=project_root,
        )

        assert len(result.factcheck_items) == 1
        item = result.factcheck_items[0]
        assert item.current_code_snippet == ""
        assert item.relevant_diff == "- def old_func(): pass"

    def test_multiple_at_risk_memories(self, tmp_path):
        """Multiple at-risk memories each get their own fact-check item."""
        memory_dir = str(tmp_path / "memories")
        project_root = str(tmp_path / "project")

        path_a = _write_test_memory(
            memory_dir, "project", "mem-a", "Memory A content.",
            citations=[{"file": "src/a.py"}],
        )
        path_b = _write_test_memory(
            memory_dir, "project", "mem-b", "Memory B content.",
            citations=[{"file": "src/b.py"}],
        )

        _write_source_file(project_root, "src/a.py", "# file a\n")
        _write_source_file(project_root, "src/b.py", "# file b\n")

        from spellbook.memory.search_serena import AtRiskMemory
        from spellbook.memory.filestore import read_memory

        at_risk = [
            AtRiskMemory(
                memory=read_memory(path_a),
                at_risk_citations=[Citation(file="src/a.py")],
                reason="cited_file_changed",
                relevant_diff="diff for a",
            ),
            AtRiskMemory(
                memory=read_memory(path_b),
                at_risk_citations=[Citation(file="src/b.py")],
                reason="cited_file_changed",
                relevant_diff="diff for b",
            ),
        ]

        result = phase2_prepare_factcheck(at_risk=at_risk, project_root=project_root)

        assert result.total_at_risk == 2
        assert len(result.factcheck_items) == 2
        paths = sorted(item.memory_path for item in result.factcheck_items)
        assert paths == sorted([path_a, path_b])


# ---------------------------------------------------------------------------
# Phase 3: Discovery Context Preparation
# ---------------------------------------------------------------------------


class TestPhase3PrepareDiscovery:
    """Phase 3: generate discovery context for the calling LLM."""

    def test_generates_discovery_context_with_symbol_changes(self, tmp_path):
        """Discovery context includes diff summary and symbol changes."""
        memory_dir = str(tmp_path / "memories")
        os.makedirs(memory_dir, exist_ok=True)
        project_root = str(tmp_path / "project")
        os.makedirs(project_root)

        symbol_changes = [
            SymbolChange(
                file="src/api.py",
                symbol_name="new_handler",
                change_type="added",
                symbol_type="function",
                context="def new_handler(request):",
            ),
            SymbolChange(
                file="src/api.py",
                symbol_name="old_handler",
                change_type="removed",
                symbol_type="function",
                context="def old_handler(request):",
            ),
        ]

        result = phase3_prepare_discovery(
            project_root=project_root,
            memory_dir=memory_dir,
            symbol_changes=symbol_changes,
            changed_files=["src/api.py"],
        )

        assert isinstance(result, SyncPhase3Result)
        # Discovery context should mention the changes
        assert "new_handler" in result.discovery_context
        assert "old_handler" in result.discovery_context
        assert "src/api.py" in result.diff_summary

        # Separate new and removed symbols
        new_names = [s.symbol_name for s in result.new_symbols]
        removed_names = [s.symbol_name for s in result.removed_symbols]
        assert "new_handler" in new_names
        assert "old_handler" in removed_names

        # Must include memory type taxonomy guidance
        assert "project" in result.memory_type_guidance
        assert "fact" in result.memory_type_guidance

    def test_includes_memory_type_taxonomy(self, tmp_path):
        """Discovery context includes type and kind taxonomy reference."""
        memory_dir = str(tmp_path / "memories")
        os.makedirs(memory_dir, exist_ok=True)
        project_root = str(tmp_path / "project")
        os.makedirs(project_root)

        result = phase3_prepare_discovery(
            project_root=project_root,
            memory_dir=memory_dir,
            symbol_changes=[],
            changed_files=["README.md"],
        )

        # Taxonomy should cover all types and kinds
        for mem_type in ("project", "user", "feedback", "reference"):
            assert mem_type in result.memory_type_guidance
        for mem_kind in ("fact", "rule", "convention", "preference", "decision", "antipattern"):
            assert mem_kind in result.memory_type_guidance

    def test_empty_symbol_changes(self, tmp_path):
        """Discovery context is still valid when no symbols are identified."""
        memory_dir = str(tmp_path / "memories")
        os.makedirs(memory_dir, exist_ok=True)
        project_root = str(tmp_path / "project")
        os.makedirs(project_root)

        result = phase3_prepare_discovery(
            project_root=project_root,
            memory_dir=memory_dir,
            symbol_changes=[],
            changed_files=["config.yaml"],
        )

        assert isinstance(result, SyncPhase3Result)
        assert result.new_symbols == []
        assert result.removed_symbols == []
        assert "config.yaml" in result.diff_summary


# ---------------------------------------------------------------------------
# Phase 4: Quality Gate
# ---------------------------------------------------------------------------


class TestPhase4QualityGate:
    """Phase 4: validate proposed new memories."""

    def test_accepts_valid_new_memory(self, tmp_path):
        """A well-formed memory with existing citation file passes."""
        memory_dir = str(tmp_path / "memories")
        os.makedirs(os.path.join(memory_dir, "project"), exist_ok=True)
        project_root = str(tmp_path / "project")
        _write_source_file(project_root, "src/api.py", "def handler(): pass\n")

        new_memories = [
            {
                "content": "The API handler uses a custom authentication middleware that validates JWT tokens before routing.",
                "type": "project",
                "kind": "fact",
                "citations": [{"file": "src/api.py", "symbol": "handler", "symbol_type": "function"}],
                "tags": ["api", "auth"],
            }
        ]

        result = phase4_quality_gate(
            new_memories=new_memories,
            memory_dir=memory_dir,
            project_root=project_root,
        )

        assert isinstance(result, SyncPhase4Result)
        assert len(result.accepted) == 1
        assert result.rejected == []
        assert result.accepted[0]["content"] == new_memories[0]["content"]

    def test_rejects_duplicate_content_hash(self, tmp_path):
        """A memory with the same content hash as an existing memory is rejected."""
        memory_dir = str(tmp_path / "memories")
        project_root = str(tmp_path / "project")
        os.makedirs(project_root)

        existing_content = "We use exponential backoff with jitter for API retries because the upstream rate-limits aggressively."
        _write_test_memory(
            memory_dir,
            "project",
            "existing-retry",
            existing_content,
            citations=[{"file": "src/api.py"}],
        )

        new_memories = [
            {
                "content": existing_content,
                "type": "project",
                "kind": "fact",
                "citations": [{"file": "src/api.py"}],
                "tags": ["retry"],
            }
        ]

        result = phase4_quality_gate(
            new_memories=new_memories,
            memory_dir=memory_dir,
            project_root=project_root,
        )

        assert result.accepted == []
        assert len(result.rejected) == 1
        assert result.rejected[0]["reason"] == "duplicate"

    def test_rejects_nonexistent_citation_file(self, tmp_path):
        """A memory citing a file that doesn't exist is rejected."""
        memory_dir = str(tmp_path / "memories")
        os.makedirs(os.path.join(memory_dir, "project"), exist_ok=True)
        project_root = str(tmp_path / "project")
        os.makedirs(project_root)

        new_memories = [
            {
                "content": "This references a file that does not exist in the project.",
                "type": "project",
                "kind": "fact",
                "citations": [{"file": "src/nonexistent.py"}],
                "tags": ["broken"],
            }
        ]

        result = phase4_quality_gate(
            new_memories=new_memories,
            memory_dir=memory_dir,
            project_root=project_root,
        )

        assert result.accepted == []
        assert len(result.rejected) == 1
        assert result.rejected[0]["reason"] == "citation_invalid"

    def test_rejects_too_short_content(self, tmp_path):
        """A memory with fewer than 10 words is rejected."""
        memory_dir = str(tmp_path / "memories")
        os.makedirs(os.path.join(memory_dir, "project"), exist_ok=True)
        project_root = str(tmp_path / "project")
        os.makedirs(project_root)

        new_memories = [
            {
                "content": "Too short.",
                "type": "project",
                "kind": "fact",
                "citations": [],
                "tags": [],
            }
        ]

        result = phase4_quality_gate(
            new_memories=new_memories,
            memory_dir=memory_dir,
            project_root=project_root,
        )

        assert result.accepted == []
        assert len(result.rejected) == 1
        assert result.rejected[0]["reason"] == "too_short"

    def test_rejects_too_long_content(self, tmp_path):
        """A memory with more than 500 words is rejected."""
        memory_dir = str(tmp_path / "memories")
        os.makedirs(os.path.join(memory_dir, "project"), exist_ok=True)
        project_root = str(tmp_path / "project")
        os.makedirs(project_root)

        long_content = " ".join(["word"] * 501)
        new_memories = [
            {
                "content": long_content,
                "type": "project",
                "kind": "fact",
                "citations": [],
                "tags": [],
            }
        ]

        result = phase4_quality_gate(
            new_memories=new_memories,
            memory_dir=memory_dir,
            project_root=project_root,
        )

        assert result.accepted == []
        assert len(result.rejected) == 1
        assert result.rejected[0]["reason"] == "too_long"

    def test_rejects_empty_tags_when_no_citations(self, tmp_path):
        """A memory with no citations AND no tags is rejected (unanchored)."""
        memory_dir = str(tmp_path / "memories")
        os.makedirs(os.path.join(memory_dir, "project"), exist_ok=True)
        project_root = str(tmp_path / "project")
        os.makedirs(project_root)

        new_memories = [
            {
                "content": "This memory has no citations and no tags so it is unanchored and hard to retrieve.",
                "type": "project",
                "kind": "fact",
                "citations": [],
                "tags": [],
            }
        ]

        result = phase4_quality_gate(
            new_memories=new_memories,
            memory_dir=memory_dir,
            project_root=project_root,
        )

        assert result.accepted == []
        assert len(result.rejected) == 1
        assert result.rejected[0]["reason"] == "unanchored"

    def test_accepts_memory_with_tags_but_no_citations(self, tmp_path):
        """A memory with tags but no citations passes (tags anchor it)."""
        memory_dir = str(tmp_path / "memories")
        os.makedirs(os.path.join(memory_dir, "project"), exist_ok=True)
        project_root = str(tmp_path / "project")
        os.makedirs(project_root)

        new_memories = [
            {
                "content": "The team prefers to use single PRs for large refactoring efforts rather than splitting into many small ones.",
                "type": "feedback",
                "kind": "preference",
                "citations": [],
                "tags": ["workflow", "pr-strategy"],
            }
        ]

        result = phase4_quality_gate(
            new_memories=new_memories,
            memory_dir=memory_dir,
            project_root=project_root,
        )

        assert len(result.accepted) == 1
        assert result.rejected == []


# ---------------------------------------------------------------------------
# memory_sync orchestrator
# ---------------------------------------------------------------------------


class TestMemorySync:
    """Top-level orchestrator that combines phases 1-3 into a SyncPlan."""

    def test_returns_complete_sync_plan(self, tmp_path):
        """memory_sync returns SyncPlan with all phases populated."""
        memory_dir = str(tmp_path / "memories")
        project_root = str(tmp_path / "project")

        _write_test_memory(
            memory_dir,
            "project",
            "at-risk-mem",
            "The authentication handler validates JWT tokens on every request.",
            citations=[{"file": "src/auth.py", "symbol": "validate", "symbol_type": "function"}],
        )

        _write_source_file(
            project_root,
            "src/auth.py",
            "def validate(token):\n    return True\n",
        )

        changed_files = ["src/auth.py"]
        symbol_changes = [
            SymbolChange(
                file="src/auth.py",
                symbol_name="validate",
                change_type="modified",
                symbol_type="function",
                context="def validate(token):",
            ),
        ]
        diff_text = "- def validate(token):\n+ def validate(token, strict=False):"

        result = memory_sync(
            project_root=project_root,
            memory_dir=memory_dir,
            changed_files=changed_files,
            symbol_changes=symbol_changes,
            diff_text=diff_text,
        )

        assert isinstance(result, SyncPlan)

        # Phase 1+2: factcheck_items
        assert len(result.factcheck_items) >= 1
        assert all(isinstance(item, FactCheckItem) for item in result.factcheck_items)

        # Phase 3: discovery_context
        assert isinstance(result.discovery_context, SyncPhase3Result)

        # Prompt template instructs the LLM
        assert "STILL_TRUE" in result.prompt_template
        assert "NEEDS_UPDATE" in result.prompt_template
        assert "NOW_FALSE" in result.prompt_template
        assert "UNCERTAIN" in result.prompt_template

        # Phase 4 instructions
        assert "phase4_quality_gate" in result.phase4_instructions

        # Stats
        assert result.stats["at_risk_count"] >= 1

    def test_returns_plan_with_no_at_risk(self, tmp_path):
        """When nothing is at risk, plan has empty factcheck_items but valid discovery."""
        memory_dir = str(tmp_path / "memories")
        project_root = str(tmp_path / "project")
        os.makedirs(memory_dir, exist_ok=True)
        os.makedirs(project_root, exist_ok=True)

        result = memory_sync(
            project_root=project_root,
            memory_dir=memory_dir,
            changed_files=["src/new_file.py"],
            symbol_changes=[],
            diff_text="+ def new_func(): pass",
        )

        assert isinstance(result, SyncPlan)
        assert result.factcheck_items == []
        assert isinstance(result.discovery_context, SyncPhase3Result)
        assert result.stats["at_risk_count"] == 0


# ---------------------------------------------------------------------------
# apply_sync_results
# ---------------------------------------------------------------------------


class TestApplySyncResults:
    """Process LLM verdicts and new memories."""

    def test_updates_memory_on_needs_update(self, tmp_path):
        """NEEDS_UPDATE verdict rewrites the memory content."""
        memory_dir = str(tmp_path / "memories")
        project_root = str(tmp_path / "project")
        os.makedirs(project_root)

        mem_path = _write_test_memory(
            memory_dir,
            "project",
            "old-content",
            "The retry delay is 1 second.",
            citations=[{"file": "src/api.py"}],
        )

        _write_source_file(project_root, "src/api.py", "# updated\n")

        results = {
            "verdicts": [
                {
                    "memory_path": mem_path,
                    "verdict": "NEEDS_UPDATE",
                    "updated_content": "The retry delay is 2 seconds with jitter.",
                    "reason": "Default delay changed from 1s to 2s.",
                }
            ],
            "new_memories": [],
        }

        report = apply_sync_results(
            results=results,
            memory_dir=memory_dir,
            project_root=project_root,
        )

        assert isinstance(report, SyncReport)
        assert report.memories_updated == 1
        assert report.memories_archived == 0
        assert report.memories_unchanged == 0

        # Verify the file was actually updated
        from spellbook.memory.filestore import read_memory

        updated = read_memory(mem_path)
        assert updated.content == "\nThe retry delay is 2 seconds with jitter.\n"

    def test_archives_memory_on_now_false(self, tmp_path):
        """NOW_FALSE verdict moves the memory to .archive/."""
        memory_dir = str(tmp_path / "memories")
        project_root = str(tmp_path / "project")
        os.makedirs(project_root)

        mem_path = _write_test_memory(
            memory_dir,
            "project",
            "stale-memory",
            "The system uses XML for configuration files throughout the project.",
            citations=[{"file": "src/config.py"}],
        )

        results = {
            "verdicts": [
                {
                    "memory_path": mem_path,
                    "verdict": "NOW_FALSE",
                    "reason": "Migrated from XML to YAML.",
                }
            ],
            "new_memories": [],
        }

        report = apply_sync_results(
            results=results,
            memory_dir=memory_dir,
            project_root=project_root,
        )

        assert report.memories_archived == 1
        assert report.memories_updated == 0

        # Original path should no longer exist
        assert not os.path.exists(mem_path)

        # Should exist in archive
        archive_path = os.path.join(
            memory_dir, ".archive", "project", "stale-memory.md"
        )
        assert os.path.exists(archive_path)

    def test_leaves_memory_on_still_true(self, tmp_path):
        """STILL_TRUE verdict leaves memory untouched."""
        memory_dir = str(tmp_path / "memories")
        project_root = str(tmp_path / "project")
        os.makedirs(project_root)

        original_content = "The database connection pool uses a maximum of 10 connections."
        mem_path = _write_test_memory(
            memory_dir,
            "project",
            "still-valid",
            original_content,
            citations=[{"file": "src/db.py"}],
        )

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

        # Content should be unchanged
        from spellbook.memory.filestore import read_memory

        mf = read_memory(mem_path)
        assert mf.content == "\n" + original_content + "\n"

    def test_creates_new_memories_that_pass_quality_gate(self, tmp_path):
        """New memories from LLM that pass phase4 are written to disk."""
        memory_dir = str(tmp_path / "memories")
        project_root = str(tmp_path / "project")
        _write_source_file(project_root, "src/new_module.py", "def important(): pass\n")

        results = {
            "verdicts": [],
            "new_memories": [
                {
                    "content": "The new_module implements a critical authentication flow that must not be modified without security review.",
                    "type": "project",
                    "kind": "rule",
                    "citations": [{"file": "src/new_module.py", "symbol": "important", "symbol_type": "function"}],
                    "tags": ["security", "auth"],
                }
            ],
        }

        report = apply_sync_results(
            results=results,
            memory_dir=memory_dir,
            project_root=project_root,
        )

        assert report.memories_created == 1
        assert report.memories_rejected == 0

        # Verify the memory file was written
        project_dir = os.path.join(memory_dir, "project")
        assert os.path.isdir(project_dir)
        md_files = [f for f in os.listdir(project_dir) if f.endswith(".md")]
        assert len(md_files) == 1

    def test_rejects_new_memories_failing_quality_gate(self, tmp_path):
        """New memories from LLM that fail phase4 are NOT written to disk."""
        memory_dir = str(tmp_path / "memories")
        project_root = str(tmp_path / "project")
        os.makedirs(project_root)

        results = {
            "verdicts": [],
            "new_memories": [
                {
                    "content": "Too short.",
                    "type": "project",
                    "kind": "fact",
                    "citations": [],
                    "tags": [],
                }
            ],
        }

        report = apply_sync_results(
            results=results,
            memory_dir=memory_dir,
            project_root=project_root,
        )

        assert report.memories_created == 0
        assert report.memories_rejected == 1

    def test_handles_uncertain_verdict(self, tmp_path):
        """UNCERTAIN verdict leaves the memory and reports it."""
        memory_dir = str(tmp_path / "memories")
        project_root = str(tmp_path / "project")
        os.makedirs(project_root)

        mem_path = _write_test_memory(
            memory_dir,
            "project",
            "uncertain-mem",
            "The caching layer invalidates entries after exactly five minutes of inactivity.",
            citations=[{"file": "src/cache.py"}],
        )

        results = {
            "verdicts": [
                {
                    "memory_path": mem_path,
                    "verdict": "UNCERTAIN",
                    "reason": "Cannot determine from diff alone.",
                }
            ],
            "new_memories": [],
        }

        report = apply_sync_results(
            results=results,
            memory_dir=memory_dir,
            project_root=project_root,
        )

        # UNCERTAIN is treated like STILL_TRUE (leave in place)
        assert report.memories_unchanged == 1
        assert os.path.exists(mem_path)

    def test_mixed_verdicts_and_new_memories(self, tmp_path):
        """Handles a mix of verdicts and new memories in one call."""
        memory_dir = str(tmp_path / "memories")
        project_root = str(tmp_path / "project")

        path_update = _write_test_memory(
            memory_dir, "project", "to-update",
            "The API rate limit is one hundred requests per minute for all endpoints.",
            citations=[{"file": "src/api.py"}],
        )
        path_archive = _write_test_memory(
            memory_dir, "project", "to-archive",
            "The system uses a deprecated authentication library that was removed in the latest update.",
            citations=[{"file": "src/old_auth.py"}],
        )
        path_keep = _write_test_memory(
            memory_dir, "project", "to-keep",
            "The deployment pipeline requires staging approval before production release.",
            citations=[{"file": "src/deploy.py"}],
        )

        _write_source_file(project_root, "src/api.py", "# rate limit = 200\n")
        _write_source_file(project_root, "src/deploy.py", "# deploy config\n")
        _write_source_file(project_root, "src/new_thing.py", "def new_thing(): pass\n")

        results = {
            "verdicts": [
                {
                    "memory_path": path_update,
                    "verdict": "NEEDS_UPDATE",
                    "updated_content": "The API rate limit is 200 requests per minute.",
                    "reason": "Rate limit increased.",
                },
                {
                    "memory_path": path_archive,
                    "verdict": "NOW_FALSE",
                    "reason": "Old auth library removed.",
                },
                {
                    "memory_path": path_keep,
                    "verdict": "STILL_TRUE",
                    "reason": "Deploy process unchanged.",
                },
            ],
            "new_memories": [
                {
                    "content": "A new service module was added that handles webhook processing for third-party integrations.",
                    "type": "project",
                    "kind": "fact",
                    "citations": [{"file": "src/new_thing.py", "symbol": "new_thing", "symbol_type": "function"}],
                    "tags": ["webhooks"],
                },
            ],
        }

        report = apply_sync_results(
            results=results,
            memory_dir=memory_dir,
            project_root=project_root,
        )

        assert report.memories_updated == 1
        assert report.memories_archived == 1
        assert report.memories_unchanged == 1
        assert report.memories_created == 1
        assert report.memories_rejected == 0
        assert report.errors == []


# ---------------------------------------------------------------------------
# F3: _read_code_snippet must window large source files
# ---------------------------------------------------------------------------


class TestReadCodeSnippetWindow:
    """_read_code_snippet must not return entire large source files.

    Previously the helper read every byte of every cited file and handed
    the result to the fact-check prompt, which can blow LLM context for
    large sources. The fix windows around the citation's line range when
    one is set, around a best-effort symbol match otherwise, and falls
    back to a hard ceiling on the first N lines as a last resort. The
    snippet is always prefixed with a `# path:start-end (windowed)`
    header so prompts can tell they are seeing a window, not the file.
    """

    def test_read_code_snippet_with_line_range_windows_around(self, tmp_path):
        from spellbook.memory.sync_pipeline import (
            _SNIPPET_CONTEXT_LINES,
            _read_code_snippet,
        )

        # Build a 300-line source file, each line uniquely identifiable
        # so we can verify the exact slice that came back.
        rel = "src/big_module.py"
        full = os.path.join(str(tmp_path), rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write("\n".join(f"line_{i}" for i in range(1, 301)))

        cite = Citation(file=rel, line_start=150)
        snippet = _read_code_snippet(str(tmp_path), cite)

        # 25 lines before + the line itself + 25 lines after = 51 lines of
        # body, plus one header line.
        body_lines = snippet.splitlines()
        assert body_lines[0] == f"# {rel}:125-175 (windowed)"
        body = body_lines[1:]
        assert len(body) == 51, (
            f"expected 25+1+25 = 51 windowed lines, got {len(body)}"
        )
        assert body[0] == "line_125"
        assert body[25] == "line_150"
        assert body[-1] == "line_175"
        # Sanity: confirms we're using the configured context width.
        assert _SNIPPET_CONTEXT_LINES == 25

    def test_read_code_snippet_windows_for_symbol_when_no_line_range(
        self, tmp_path
    ):
        from spellbook.memory.sync_pipeline import _read_code_snippet

        rel = "src/findme.py"
        full = os.path.join(str(tmp_path), rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        # 500 lines: padding, then `def my_target():` at line 10, then
        # more padding. Symbol search should anchor on line 10.
        lines = [f"# pad {i}" for i in range(1, 10)]
        lines.append("def my_target():")
        lines += [f"# pad {i}" for i in range(11, 501)]
        with open(full, "w") as f:
            f.write("\n".join(lines))

        cite = Citation(file=rel, symbol="my_target")
        snippet = _read_code_snippet(str(tmp_path), cite)

        body_lines = snippet.splitlines()
        # Symbol matched on line 10. Window is max(1, 10-25)=1 to
        # min(500, 10+25)=35; that's 35 lines. Either way, must be <= 51.
        assert body_lines[0].startswith(f"# {rel}:")
        body = body_lines[1:]
        assert len(body) <= 51, (
            f"symbol-anchored window should be <= 51 lines, got {len(body)}"
        )
        assert "def my_target():" in body

    def test_read_code_snippet_ceiling_when_symbol_not_found(self, tmp_path):
        from spellbook.memory.sync_pipeline import (
            _SNIPPET_HARD_CEILING,
            _read_code_snippet,
        )

        rel = "src/no_match.py"
        full = os.path.join(str(tmp_path), rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        # 600 lines, none of which contain the cited symbol.
        with open(full, "w") as f:
            f.write("\n".join(f"# unrelated_{i}" for i in range(1, 601)))

        cite = Citation(file=rel, symbol="nowhere_to_be_found")
        snippet = _read_code_snippet(str(tmp_path), cite)

        body_lines = snippet.splitlines()
        assert body_lines[0] == f"# {rel}:1-{_SNIPPET_HARD_CEILING} (windowed)"
        body = body_lines[1:]
        assert len(body) == _SNIPPET_HARD_CEILING == 200
        # First and last lines of the windowed slice line up with the cap.
        assert body[0] == "# unrelated_1"
        assert body[-1] == f"# unrelated_{_SNIPPET_HARD_CEILING}"

    def test_read_code_snippet_missing_file_returns_empty(self, tmp_path):
        from spellbook.memory.sync_pipeline import _read_code_snippet

        cite = Citation(file="src/does_not_exist.py", line_start=1)
        assert _read_code_snippet(str(tmp_path), cite) == ""

    def test_read_code_snippet_legacy_string_signature_still_works(
        self, tmp_path
    ):
        """Backwards-compat: passing a bare path (no Citation) hits the ceiling path."""
        from spellbook.memory.sync_pipeline import (
            _SNIPPET_HARD_CEILING,
            _read_code_snippet,
        )

        rel = "src/legacy.py"
        full = os.path.join(str(tmp_path), rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write("\n".join(f"row_{i}" for i in range(1, 301)))

        snippet = _read_code_snippet(str(tmp_path), rel)
        body_lines = snippet.splitlines()
        assert body_lines[0].endswith("(windowed)")
        assert len(body_lines) - 1 <= _SNIPPET_HARD_CEILING
