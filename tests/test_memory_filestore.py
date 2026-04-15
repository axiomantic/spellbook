"""Tests for the file-based memory system.

Covers: models, frontmatter parsing/writing, secret scanning, access log,
audit trail, scoring (temporal decay, branch multiplier), grep search,
filestore CRUD (store, recall, forget, verify, read, list), slug generation,
content-hash dedup, and atomic writes.

TDD RED phase: all tests written before implementation.
"""

import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import threading
import time

import pytest
import yaml

from tests._memory_marker import requires_memory_tools


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class TestModels:
    """Test data model construction and defaults."""

    def test_citation_defaults(self):
        from spellbook.memory.models import Citation

        c = Citation(file="src/main.py")
        assert c == Citation(file="src/main.py", symbol=None, symbol_type=None)

    def test_citation_with_symbol(self):
        from spellbook.memory.models import Citation

        c = Citation(file="src/main.py", symbol="main", symbol_type="function")
        assert c.file == "src/main.py"
        assert c.symbol == "main"
        assert c.symbol_type == "function"

    def test_memory_frontmatter_defaults(self):
        from spellbook.memory.models import MemoryFrontmatter

        fm = MemoryFrontmatter(
            type="project",
            created=datetime.date(2026, 4, 14),
        )
        assert fm.type == "project"
        assert fm.kind is None
        assert fm.citations == []
        assert fm.tags == []
        assert fm.scope == "project"
        assert fm.branch is None
        assert fm.last_verified is None
        assert fm.confidence is None
        assert fm.content_hash is None

    def test_memory_frontmatter_full(self):
        from spellbook.memory.models import Citation, MemoryFrontmatter

        fm = MemoryFrontmatter(
            type="feedback",
            created=datetime.date(2026, 4, 14),
            kind="decision",
            citations=[Citation(file="a.py", symbol="foo", symbol_type="function")],
            tags=["api", "retry"],
            scope="global",
            branch="feature/x",
            last_verified=datetime.date(2026, 4, 14),
            confidence="high",
            content_hash="sha256:abc123",
        )
        assert fm.type == "feedback"
        assert fm.kind == "decision"
        assert fm.citations == [
            Citation(file="a.py", symbol="foo", symbol_type="function")
        ]
        assert fm.tags == ["api", "retry"]
        assert fm.scope == "global"
        assert fm.branch == "feature/x"
        assert fm.last_verified == datetime.date(2026, 4, 14)
        assert fm.confidence == "high"
        assert fm.content_hash == "sha256:abc123"

    def test_memory_file_dataclass(self):
        from spellbook.memory.models import MemoryFile, MemoryFrontmatter

        fm = MemoryFrontmatter(
            type="project", created=datetime.date(2026, 4, 14)
        )
        mf = MemoryFile(path="/tmp/test.md", frontmatter=fm, content="body text")
        assert mf.path == "/tmp/test.md"
        assert mf.frontmatter is fm
        assert mf.content == "body text"

    def test_memory_result_dataclass(self):
        from spellbook.memory.models import (
            MemoryFile,
            MemoryFrontmatter,
            MemoryResult,
        )

        fm = MemoryFrontmatter(
            type="project", created=datetime.date(2026, 4, 14)
        )
        mf = MemoryFile(path="/tmp/test.md", frontmatter=fm, content="body")
        mr = MemoryResult(memory=mf, score=0.85, match_context="matched line")
        assert mr.memory is mf
        assert mr.score == 0.85
        assert mr.match_context == "matched line"

    def test_memory_result_default_match_context(self):
        from spellbook.memory.models import (
            MemoryFile,
            MemoryFrontmatter,
            MemoryResult,
        )

        fm = MemoryFrontmatter(
            type="project", created=datetime.date(2026, 4, 14)
        )
        mf = MemoryFile(path="/tmp/test.md", frontmatter=fm, content="body")
        mr = MemoryResult(memory=mf, score=1.0)
        assert mr.match_context is None

    def test_verify_context_dataclass(self):
        from spellbook.memory.models import (
            MemoryFile,
            MemoryFrontmatter,
            VerifyContext,
        )

        fm = MemoryFrontmatter(
            type="project", created=datetime.date(2026, 4, 14)
        )
        mf = MemoryFile(path="/tmp/test.md", frontmatter=fm, content="body")
        vc = VerifyContext(
            memory=mf,
            cited_files_exist={"a.py": True},
            cited_symbols_exist={"a.py::foo": False},
            relevant_diffs="diff output",
        )
        assert vc.cited_files_exist == {"a.py": True}
        assert vc.cited_symbols_exist == {"a.py::foo": False}
        assert vc.relevant_diffs == "diff output"

    def test_verify_context_default_diffs(self):
        from spellbook.memory.models import (
            MemoryFile,
            MemoryFrontmatter,
            VerifyContext,
        )

        fm = MemoryFrontmatter(
            type="project", created=datetime.date(2026, 4, 14)
        )
        mf = MemoryFile(path="/tmp/test.md", frontmatter=fm, content="body")
        vc = VerifyContext(
            memory=mf,
            cited_files_exist={},
            cited_symbols_exist={},
        )
        assert vc.relevant_diffs is None


# ---------------------------------------------------------------------------
# Frontmatter parsing and writing
# ---------------------------------------------------------------------------


class TestFrontmatter:
    """Test YAML frontmatter parse/write/slug generation."""

    def test_parse_full_frontmatter(self, tmp_path):
        from spellbook.memory.frontmatter import parse_frontmatter
        from spellbook.memory.models import MemoryFrontmatter

        content = """\
---
type: project
kind: decision
citations:
  - file: src/api/client.py
    symbol: APIClient.retry
    symbol_type: method
tags:
  - retry
  - api
scope: project
branch: feature/retry
created: 2026-04-14
last_verified: 2026-04-14
confidence: high
content_hash: "sha256:abc123"
---

We use exponential backoff with jitter.
"""
        p = tmp_path / "test.md"
        p.write_text(content)
        fm, body = parse_frontmatter(str(p))
        assert isinstance(fm, MemoryFrontmatter)
        assert fm.type == "project"
        assert fm.kind == "decision"
        assert len(fm.citations) == 1
        assert fm.citations[0].file == "src/api/client.py"
        assert fm.citations[0].symbol == "APIClient.retry"
        assert fm.citations[0].symbol_type == "method"
        assert fm.tags == ["retry", "api"]
        assert fm.scope == "project"
        assert fm.branch == "feature/retry"
        assert fm.created == datetime.date(2026, 4, 14)
        assert fm.last_verified == datetime.date(2026, 4, 14)
        assert fm.confidence == "high"
        assert fm.content_hash == "sha256:abc123"
        assert body.strip() == "We use exponential backoff with jitter."

    def test_parse_minimal_frontmatter(self, tmp_path):
        from spellbook.memory.frontmatter import parse_frontmatter

        content = """\
---
type: user
created: 2026-04-14
content_hash: "sha256:def456"
---

User prefers single PRs.
"""
        p = tmp_path / "test.md"
        p.write_text(content)
        fm, body = parse_frontmatter(str(p))
        assert fm.type == "user"
        assert fm.kind is None
        assert fm.citations == []
        assert fm.tags == []
        assert fm.scope == "project"
        assert fm.branch is None
        assert body.strip() == "User prefers single PRs."

    def test_write_and_roundtrip(self, tmp_path):
        from spellbook.memory.frontmatter import parse_frontmatter, write_memory_file
        from spellbook.memory.models import Citation, MemoryFrontmatter

        fm = MemoryFrontmatter(
            type="project",
            kind="rule",
            citations=[
                Citation(file="src/main.py", symbol="main", symbol_type="function")
            ],
            tags=["entrypoint"],
            scope="project",
            branch="main",
            created=datetime.date(2026, 4, 14),
            last_verified=datetime.date(2026, 4, 14),
            confidence="high",
            content_hash="sha256:abc",
        )
        body = "The main function is the entrypoint."
        p = tmp_path / "test.md"
        write_memory_file(str(p), fm, body)

        assert p.exists()
        fm2, body2 = parse_frontmatter(str(p))
        assert fm2.type == "project"
        assert fm2.kind == "rule"
        assert fm2.citations[0].file == "src/main.py"
        assert fm2.citations[0].symbol == "main"
        assert fm2.citations[0].symbol_type == "function"
        assert fm2.tags == ["entrypoint"]
        assert fm2.scope == "project"
        assert fm2.branch == "main"
        assert fm2.created == datetime.date(2026, 4, 14)
        assert fm2.last_verified == datetime.date(2026, 4, 14)
        assert fm2.confidence == "high"
        assert fm2.content_hash == "sha256:abc"
        assert body2.strip() == body

    def test_atomic_write_no_partial(self, tmp_path):
        """Verify write uses atomic rename (no torn reads)."""
        from spellbook.memory.frontmatter import parse_frontmatter, write_memory_file
        from spellbook.memory.models import MemoryFrontmatter

        fm = MemoryFrontmatter(
            type="project",
            created=datetime.date(2026, 4, 14),
            content_hash="sha256:x",
        )
        p = tmp_path / "atomic.md"
        # Write initial content
        write_memory_file(str(p), fm, "initial content")
        assert p.exists()
        initial = p.read_text()

        # Overwrite -- if atomic, either old or new content, never partial
        write_memory_file(str(p), fm, "updated content")
        result = p.read_text()
        # Verify file is a valid memory file with correct frontmatter and body
        assert result.startswith("---\n")
        assert "updated content" in result
        assert "initial content" not in result
        # Parse to verify structural integrity
        fm2, body2 = parse_frontmatter(str(p))
        assert fm2.type == "project"
        assert fm2.content_hash == "sha256:x"
        assert body2.strip() == "updated content"
        # No temp files left behind
        temp_files = [f for f in tmp_path.iterdir() if f.name.startswith(".tmp_")]
        assert temp_files == []

    def test_generate_slug_basic(self):
        from spellbook.memory.frontmatter import generate_slug

        slug = generate_slug(
            "We use exponential backoff with jitter for API retries",
            existing_slugs=set(),
        )
        # Should be kebab-case, max 6 significant words, no stopwords
        assert slug == "exponential-backoff-jitter-api-retries"

    def test_generate_slug_collision(self):
        from spellbook.memory.frontmatter import generate_slug

        existing = {"exponential-backoff-jitter-api-retries"}
        slug = generate_slug(
            "We use exponential backoff with jitter for API retries",
            existing_slugs=existing,
        )
        assert slug == "exponential-backoff-jitter-api-retries-2"

    def test_generate_slug_multiple_collisions(self):
        from spellbook.memory.frontmatter import generate_slug

        existing = {
            "exponential-backoff-jitter-api-retries",
            "exponential-backoff-jitter-api-retries-2",
        }
        slug = generate_slug(
            "We use exponential backoff with jitter for API retries",
            existing_slugs=existing,
        )
        assert slug == "exponential-backoff-jitter-api-retries-3"

    def test_generate_slug_short_content(self):
        from spellbook.memory.frontmatter import generate_slug

        slug = generate_slug("Fix bug", existing_slugs=set())
        assert slug == "fix-bug"

    def test_generate_slug_strips_punctuation(self):
        from spellbook.memory.frontmatter import generate_slug

        slug = generate_slug(
            "Don't use retry! It's broken.",
            existing_slugs=set(),
        )
        # Should produce a valid kebab-case slug with no punctuation
        # "its" is filtered as a stopword
        assert slug == "dont-retry-broken"


# ---------------------------------------------------------------------------
# Secret scanner
# ---------------------------------------------------------------------------


class TestSecretScanner:
    """Test secret detection (flag, don't reject)."""

    def test_detects_github_token(self):
        from spellbook.memory.secret_scanner import scan_for_secrets

        findings = scan_for_secrets(
            "Token: ghp_ABC123DEF456GHI789JKL012MNO345P"
        )
        assert len(findings) >= 1
        assert findings[0].pattern_name == "GitHub Token (classic)"
        assert findings[0].redacted_preview.startswith("ghp_")
        assert "..." in findings[0].redacted_preview

    def test_detects_aws_key(self):
        from spellbook.memory.secret_scanner import scan_for_secrets

        findings = scan_for_secrets("Key: AKIAIOSFODNN7EXAMPLE")
        assert len(findings) >= 1
        assert "AWS" in findings[0].pattern_name

    def test_detects_private_key_header(self):
        from spellbook.memory.secret_scanner import scan_for_secrets

        findings = scan_for_secrets(
            "-----BEGIN RSA PRIVATE KEY-----\nMIIE..."
        )
        assert len(findings) >= 1
        assert "Private Key" in findings[0].pattern_name

    def test_clean_content_returns_empty(self):
        from spellbook.memory.secret_scanner import scan_for_secrets

        findings = scan_for_secrets(
            "This is a normal memory about retry strategy."
        )
        assert findings == []

    def test_finding_has_position(self):
        from spellbook.memory.secret_scanner import scan_for_secrets

        content = "prefix AKIAIOSFODNN7EXAMPLE suffix"
        findings = scan_for_secrets(content)
        assert len(findings) >= 1
        f = findings[0]
        assert f.position_start == content.index("AKIA")
        assert f.position_end > f.position_start

    def test_multiple_secrets_in_one_content(self):
        from spellbook.memory.secret_scanner import scan_for_secrets

        content = (
            "AWS: AKIAIOSFODNN7EXAMPLE\n"
            "GitHub: ghp_ABC123DEF456GHI789JKL012MNO345P"
        )
        findings = scan_for_secrets(content)
        assert len(findings) >= 2
        pattern_names = {f.pattern_name for f in findings}
        assert "AWS Access Key" in pattern_names
        assert "GitHub Token (classic)" in pattern_names


# ---------------------------------------------------------------------------
# Access log
# ---------------------------------------------------------------------------


class TestAccessLog:
    """Test access tracking and importance computation."""

    def test_record_access_creates_log(self, tmp_path):
        from spellbook.memory.access_log import record_access

        record_access("project/test-memory.md", str(tmp_path))
        log_path = tmp_path / ".access-log.json"
        assert log_path.exists()
        data = json.loads(log_path.read_text())
        assert "project/test-memory.md" in data
        assert data["project/test-memory.md"]["count"] == 1
        assert "last_accessed" in data["project/test-memory.md"]

    def test_record_access_increments(self, tmp_path):
        from spellbook.memory.access_log import record_access

        record_access("project/test.md", str(tmp_path))
        record_access("project/test.md", str(tmp_path))
        record_access("project/test.md", str(tmp_path))
        data = json.loads((tmp_path / ".access-log.json").read_text())
        assert data["project/test.md"]["count"] == 3

    def test_get_importance_default(self, tmp_path):
        from spellbook.memory.access_log import get_importance

        # No access log exists yet
        importance = get_importance("project/nonexistent.md", str(tmp_path))
        assert importance == 1.0

    def test_get_importance_scales_with_access(self, tmp_path):
        from spellbook.memory.access_log import get_importance, record_access

        for _ in range(5):
            record_access("project/popular.md", str(tmp_path))
        importance = get_importance("project/popular.md", str(tmp_path))
        # 1.0 + 0.1 * 5 = 1.5
        assert importance == 1.5

    def test_get_importance_capped_at_10(self, tmp_path):
        from spellbook.memory.access_log import get_importance, record_access

        for _ in range(200):
            record_access("project/mega-popular.md", str(tmp_path))
        importance = get_importance("project/mega-popular.md", str(tmp_path))
        assert importance == 10.0

    def test_record_audit_creates_log(self, tmp_path):
        from spellbook.memory.access_log import record_audit

        record_audit(
            action="create",
            memory_path="project/test.md",
            details={"source": "test"},
            memory_dir=str(tmp_path),
        )
        log_path = tmp_path / ".audit-log.jsonl"
        assert log_path.exists()
        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["action"] == "create"
        assert entry["memory_path"] == "project/test.md"
        assert entry["details"] == {"source": "test"}
        assert "timestamp" in entry

    def test_record_audit_appends(self, tmp_path):
        from spellbook.memory.access_log import record_audit

        record_audit("create", "a.md", {}, str(tmp_path))
        record_audit("recall", "a.md", {"query": "test"}, str(tmp_path))
        record_audit("delete", "b.md", {}, str(tmp_path))
        lines = (tmp_path / ".audit-log.jsonl").read_text().strip().split("\n")
        assert len(lines) == 3
        assert json.loads(lines[0])["action"] == "create"
        assert json.loads(lines[1])["action"] == "recall"
        assert json.loads(lines[2])["action"] == "delete"


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


class TestScoring:
    """Test search scoring: temporal decay, branch multiplier, composite score."""

    def test_temporal_decay_today(self):
        from spellbook.memory.scoring import compute_score
        from spellbook.memory.models import MemoryFile, MemoryFrontmatter

        fm = MemoryFrontmatter(
            type="project",
            created=datetime.date.today(),
            tags=["test"],
        )
        mf = MemoryFile(path="test.md", frontmatter=fm, content="test query content")
        score = compute_score(mf, ["test"], current_branch=None)
        # Today: decay factor ~1.0, term match present
        assert score > 0.0

    def test_temporal_decay_90_days(self):
        from spellbook.memory.scoring import compute_score
        from spellbook.memory.models import MemoryFile, MemoryFrontmatter

        today = datetime.date.today()
        old_date = today - datetime.timedelta(days=90)
        # Pin last_verified=today on both so confidence decay is neutralized
        # and this test isolates the exp(-lambda * age) temporal decay term.
        fm_new = MemoryFrontmatter(
            type="project",
            created=today,
            last_verified=today,
            confidence="high",
            tags=["test"],
        )
        fm_old = MemoryFrontmatter(
            type="project",
            created=old_date,
            last_verified=today,
            confidence="high",
            tags=["test"],
        )
        mf_new = MemoryFile(path="new.md", frontmatter=fm_new, content="test content")
        mf_old = MemoryFile(path="old.md", frontmatter=fm_old, content="test content")

        score_new = compute_score(mf_new, ["test"], current_branch=None)
        score_old = compute_score(mf_old, ["test"], current_branch=None)

        # 90-day half-life: old score should be roughly half of new
        ratio = score_old / score_new
        assert 0.4 < ratio < 0.6

    def test_branch_multiplier_same(self):
        from spellbook.memory.scoring import get_branch_multiplier

        mult = get_branch_multiplier(
            memory_branch="feature/x",
            current_branch="feature/x",
            project_root=None,
        )
        assert mult == 2.0

    def test_branch_multiplier_unrelated(self):
        from spellbook.memory.scoring import get_branch_multiplier

        mult = get_branch_multiplier(
            memory_branch="feature/x",
            current_branch="feature/y",
            project_root=None,
        )
        assert mult == 1.0

    def test_branch_multiplier_no_branch(self):
        from spellbook.memory.scoring import get_branch_multiplier

        mult = get_branch_multiplier(
            memory_branch=None,
            current_branch="feature/x",
            project_root=None,
        )
        assert mult == 1.0

    def test_term_frequency_affects_score(self):
        from spellbook.memory.scoring import compute_score
        from spellbook.memory.models import MemoryFile, MemoryFrontmatter

        today = datetime.date.today()
        fm = MemoryFrontmatter(type="project", created=today)
        mf_many = MemoryFile(
            path="many.md",
            frontmatter=fm,
            content="retry retry retry strategy",
        )
        mf_few = MemoryFile(
            path="few.md",
            frontmatter=fm,
            content="retry strategy is documented",
        )
        score_many = compute_score(mf_many, ["retry"], current_branch=None)
        score_few = compute_score(mf_few, ["retry"], current_branch=None)
        assert score_many > score_few

    def test_tag_match_boosts_score(self):
        from spellbook.memory.scoring import compute_score
        from spellbook.memory.models import MemoryFile, MemoryFrontmatter

        today = datetime.date.today()
        fm_tagged = MemoryFrontmatter(
            type="project", created=today, tags=["retry", "api"]
        )
        fm_untagged = MemoryFrontmatter(type="project", created=today, tags=[])
        mf_tagged = MemoryFile(
            path="tagged.md", frontmatter=fm_tagged, content="some content"
        )
        mf_untagged = MemoryFile(
            path="untagged.md", frontmatter=fm_untagged, content="some content"
        )
        score_tagged = compute_score(mf_tagged, ["retry"], current_branch=None)
        score_untagged = compute_score(mf_untagged, ["retry"], current_branch=None)
        assert score_tagged > score_untagged


# ---------------------------------------------------------------------------
# Filestore CRUD
# ---------------------------------------------------------------------------


class TestFilestore:
    """Test top-level filestore operations."""

    def test_store_creates_file(self, tmp_path):
        from spellbook.memory.filestore import store_memory

        result = store_memory(
            content="We use retry backoff for API calls.",
            type="project",
            kind="fact",
            citations=[],
            tags=["api", "retry"],
            scope="project",
            branch="main",
            memory_dir=str(tmp_path),
        )
        assert os.path.exists(result.path)
        assert result.frontmatter.type == "project"
        assert result.frontmatter.kind == "fact"
        assert result.frontmatter.tags == ["api", "retry"]
        assert result.frontmatter.branch == "main"
        assert result.frontmatter.scope == "project"
        assert result.frontmatter.content_hash is not None
        assert result.content == "We use retry backoff for API calls."
        # File should be in type subdirectory
        assert Path(result.path).parent.name == "project"

    def test_store_creates_subdirectory(self, tmp_path):
        from spellbook.memory.filestore import store_memory

        result = store_memory(
            content="User prefers explicit PRs.",
            type="feedback",
            kind="preference",
            citations=[],
            tags=[],
            scope="global",
            branch=None,
            memory_dir=str(tmp_path),
        )
        assert Path(result.path).parent.name == "feedback"
        assert (tmp_path / "feedback").is_dir()

    def test_store_dedup_by_content_hash(self, tmp_path):
        from spellbook.memory.filestore import store_memory

        r1 = store_memory(
            content="Exact same content.",
            type="project",
            kind="fact",
            citations=[],
            tags=[],
            scope="project",
            branch=None,
            memory_dir=str(tmp_path),
        )
        r2 = store_memory(
            content="Exact same content.",
            type="project",
            kind="fact",
            citations=[],
            tags=[],
            scope="project",
            branch=None,
            memory_dir=str(tmp_path),
        )
        # Should return the same file (dedup)
        assert r1.path == r2.path
        # Only one file on disk
        md_files = list((tmp_path / "project").glob("*.md"))
        assert len(md_files) == 1

    def test_store_flags_secrets(self, tmp_path, caplog):
        import logging

        from spellbook.memory.filestore import store_memory

        with caplog.at_level(logging.WARNING, logger="spellbook.memory.filestore"):
            result = store_memory(
                content="Token: ghp_ABC123DEF456GHI789JKL012MNO345P is used.",
                type="project",
                kind="fact",
                citations=[],
                tags=[],
                scope="project",
                branch=None,
                memory_dir=str(tmp_path),
            )
        # Flags but does not reject (backward compat)
        assert os.path.exists(result.path)
        # Verify the secret scanner logged a warning
        secret_warnings = [
            r for r in caplog.records
            if r.levelno == logging.WARNING
            and "Secret scanner found" in r.message
            and "GitHub Token" in r.message
        ]
        assert len(secret_warnings) == 1

    def test_store_appends_audit_log(self, tmp_path):
        from spellbook.memory.filestore import store_memory

        store_memory(
            content="Audited memory.",
            type="project",
            kind="fact",
            citations=[],
            tags=[],
            scope="project",
            branch=None,
            memory_dir=str(tmp_path),
        )
        audit_path = tmp_path / ".audit-log.jsonl"
        assert audit_path.exists()
        entry = json.loads(audit_path.read_text().strip().split("\n")[0])
        assert entry["action"] == "create"

    def test_store_with_citations(self, tmp_path):
        from spellbook.memory.filestore import store_memory
        from spellbook.memory.models import Citation

        result = store_memory(
            content="Client uses retry backoff.",
            type="project",
            kind="fact",
            citations=[
                Citation(
                    file="src/api/client.py",
                    symbol="APIClient.retry",
                    symbol_type="method",
                )
            ],
            tags=["api"],
            scope="project",
            branch="main",
            memory_dir=str(tmp_path),
        )
        assert len(result.frontmatter.citations) == 1
        assert result.frontmatter.citations[0].file == "src/api/client.py"
        assert result.frontmatter.citations[0].symbol == "APIClient.retry"
        assert result.frontmatter.citations[0].symbol_type == "method"

    @requires_memory_tools
    def test_recall_by_query(self, tmp_path):
        from spellbook.memory.filestore import recall_memories, store_memory

        store_memory(
            content="We use exponential backoff for retries.",
            type="project",
            kind="fact",
            citations=[],
            tags=["retry"],
            scope="project",
            branch="main",
            memory_dir=str(tmp_path),
        )
        store_memory(
            content="Deploy process requires staging.",
            type="project",
            kind="fact",
            citations=[],
            tags=["deploy"],
            scope="project",
            branch="main",
            memory_dir=str(tmp_path),
        )
        results = recall_memories(
            query="backoff retry",
            memory_dir=str(tmp_path),
        )
        assert len(results) == 1
        assert results[0].memory.content.strip() == "We use exponential backoff for retries."
        assert results[0].score > 0.0

    @requires_memory_tools
    def test_recall_respects_limit(self, tmp_path):
        from spellbook.memory.filestore import recall_memories, store_memory

        for i in range(5):
            store_memory(
                content=f"Memory number {i} about testing limits.",
                type="project",
                kind="fact",
                citations=[],
                tags=["test"],
                scope="project",
                branch=None,
                memory_dir=str(tmp_path),
            )
        results = recall_memories(
            query="testing limits",
            memory_dir=str(tmp_path),
            limit=2,
        )
        assert len(results) == 2
        # Verify results are actual memories with expected content pattern
        for r in results:
            assert "Memory number" in r.memory.content
            assert "testing limits" in r.memory.content
            assert r.score > 0.0

    @requires_memory_tools
    def test_recall_by_file_path(self, tmp_path):
        from spellbook.memory.filestore import recall_memories, store_memory
        from spellbook.memory.models import Citation

        store_memory(
            content="Client logic details.",
            type="project",
            kind="fact",
            citations=[Citation(file="src/client.py")],
            tags=[],
            scope="project",
            branch=None,
            memory_dir=str(tmp_path),
        )
        results = recall_memories(
            query="",
            memory_dir=str(tmp_path),
            file_path="src/client.py",
        )
        assert len(results) == 1
        assert results[0].memory.content.strip() == "Client logic details."
        assert results[0].memory.frontmatter.citations[0].file == "src/client.py"

    @requires_memory_tools
    def test_recall_updates_access_log(self, tmp_path):
        from spellbook.memory.filestore import recall_memories, store_memory

        store_memory(
            content="Recall access tracking test.",
            type="project",
            kind="fact",
            citations=[],
            tags=["tracking"],
            scope="project",
            branch=None,
            memory_dir=str(tmp_path),
        )
        results = recall_memories(query="tracking", memory_dir=str(tmp_path))
        assert len(results) == 1
        log_path = tmp_path / ".access-log.json"
        assert log_path.exists()
        data = json.loads(log_path.read_text())
        # Verify the specific recalled memory had its access logged
        recalled_rel_path = os.path.relpath(results[0].memory.path, str(tmp_path))
        assert recalled_rel_path in data
        assert data[recalled_rel_path]["count"] == 1

    def test_forget_archive(self, tmp_path):
        from spellbook.memory.filestore import forget_memory, store_memory

        result = store_memory(
            content="Will be archived.",
            type="project",
            kind="fact",
            citations=[],
            tags=[],
            scope="project",
            branch=None,
            memory_dir=str(tmp_path),
        )
        original_path = result.path
        success = forget_memory(original_path, str(tmp_path), archive=True)
        assert success is True
        assert not os.path.exists(original_path)
        # Should be in .archive/
        archive_dir = tmp_path / ".archive"
        assert archive_dir.exists()
        archived_files = list(archive_dir.rglob("*.md"))
        assert len(archived_files) == 1

    def test_forget_delete(self, tmp_path):
        from spellbook.memory.filestore import forget_memory, store_memory

        result = store_memory(
            content="Will be permanently deleted.",
            type="project",
            kind="fact",
            citations=[],
            tags=[],
            scope="project",
            branch=None,
            memory_dir=str(tmp_path),
        )
        success = forget_memory(result.path, str(tmp_path), archive=False)
        assert success is True
        assert not os.path.exists(result.path)
        # Should NOT be in .archive/
        archive_dir = tmp_path / ".archive"
        archived_files = list(archive_dir.rglob("*.md")) if archive_dir.exists() else []
        assert archived_files == []

    def test_forget_appends_audit_log(self, tmp_path):
        from spellbook.memory.filestore import forget_memory, store_memory

        result = store_memory(
            content="Will be forgotten.",
            type="project",
            kind="fact",
            citations=[],
            tags=[],
            scope="project",
            branch=None,
            memory_dir=str(tmp_path),
        )
        forget_memory(result.path, str(tmp_path), archive=True)
        lines = (tmp_path / ".audit-log.jsonl").read_text().strip().split("\n")
        actions = [json.loads(line)["action"] for line in lines]
        assert "create" in actions
        assert "archive" in actions

    def test_forget_nonexistent_returns_false(self, tmp_path):
        from spellbook.memory.filestore import forget_memory

        success = forget_memory(
            str(tmp_path / "nonexistent.md"),
            str(tmp_path),
            archive=True,
        )
        assert success is False

    def test_read_memory(self, tmp_path):
        from spellbook.memory.filestore import read_memory, store_memory

        stored = store_memory(
            content="Read test content.",
            type="project",
            kind="rule",
            citations=[],
            tags=["read"],
            scope="project",
            branch="main",
            memory_dir=str(tmp_path),
        )
        result = read_memory(stored.path)
        assert result.path == stored.path
        assert result.frontmatter.type == "project"
        assert result.frontmatter.kind == "rule"
        assert result.frontmatter.tags == ["read"]
        assert result.content.strip() == "Read test content."

    def test_list_memories_all(self, tmp_path):
        from spellbook.memory.filestore import list_memories, store_memory

        store_memory(
            content="Project memory.",
            type="project",
            kind="fact",
            citations=[],
            tags=[],
            scope="project",
            branch=None,
            memory_dir=str(tmp_path),
        )
        store_memory(
            content="Feedback memory.",
            type="feedback",
            kind="preference",
            citations=[],
            tags=[],
            scope="project",
            branch=None,
            memory_dir=str(tmp_path),
        )
        all_memories = list_memories(str(tmp_path))
        assert len(all_memories) == 2
        types = {m.frontmatter.type for m in all_memories}
        assert types == {"project", "feedback"}

    def test_list_memories_filtered_by_type(self, tmp_path):
        from spellbook.memory.filestore import list_memories, store_memory

        store_memory(
            content="Project memory.",
            type="project",
            kind="fact",
            citations=[],
            tags=[],
            scope="project",
            branch=None,
            memory_dir=str(tmp_path),
        )
        store_memory(
            content="Feedback memory.",
            type="feedback",
            kind="preference",
            citations=[],
            tags=[],
            scope="project",
            branch=None,
            memory_dir=str(tmp_path),
        )
        filtered = list_memories(str(tmp_path), type_filter="project")
        assert len(filtered) == 1
        assert filtered[0].frontmatter.type == "project"

    def test_verify_memory_cited_files(self, tmp_path):
        from spellbook.memory.filestore import store_memory, verify_memory
        from spellbook.memory.models import Citation

        # Create a real file that the citation references
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "real_file.py").write_text("def foo(): pass\n")

        result = store_memory(
            content="Real file exists, fake does not.",
            type="project",
            kind="fact",
            citations=[
                Citation(file="real_file.py"),
                Citation(file="nonexistent.py"),
            ],
            tags=[],
            scope="project",
            branch=None,
            memory_dir=str(tmp_path),
        )
        ctx = verify_memory(result.path, str(project_root))
        assert ctx.cited_files_exist["real_file.py"] is True
        assert ctx.cited_files_exist["nonexistent.py"] is False

    def test_content_hash_computed_correctly(self, tmp_path):
        from spellbook.memory.filestore import store_memory

        content = "Hash verification test."
        result = store_memory(
            content=content,
            type="project",
            kind="fact",
            citations=[],
            tags=[],
            scope="project",
            branch=None,
            memory_dir=str(tmp_path),
        )
        # Compute expected hash: sha256 of normalized content
        normalized = " ".join(content.lower().split())
        expected_hash = (
            "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        )
        assert result.frontmatter.content_hash == expected_hash


# ---------------------------------------------------------------------------
# Security: path traversal prevention
# ---------------------------------------------------------------------------


class TestPathTraversalPrevention:
    """Test that path traversal attacks are rejected."""

    def test_store_memory_rejects_invalid_type(self, tmp_path):
        from spellbook.memory.filestore import store_memory

        with pytest.raises(ValueError, match="Invalid memory type"):
            store_memory(
                content="This should not be stored anywhere.",
                type="../../../etc",
                kind="fact",
                citations=[],
                tags=[],
                scope="project",
                branch=None,
                memory_dir=str(tmp_path),
            )

    def test_store_memory_rejects_dotdot_type(self, tmp_path):
        from spellbook.memory.filestore import store_memory

        with pytest.raises(ValueError, match="Invalid memory type"):
            store_memory(
                content="Path traversal attempt with enough words to pass slug generation.",
                type="../../sensitive",
                kind="fact",
                citations=[],
                tags=[],
                scope="project",
                branch=None,
                memory_dir=str(tmp_path),
            )

    def test_store_memory_accepts_valid_types(self, tmp_path):
        from spellbook.memory.filestore import store_memory

        for valid_type in ("project", "user", "feedback", "reference"):
            result = store_memory(
                content=f"Valid {valid_type} memory with enough words for slug generation test.",
                type=valid_type,
                kind="fact",
                citations=[],
                tags=[],
                scope="project",
                branch=None,
                memory_dir=str(tmp_path),
            )
            assert os.path.exists(result.path)
            assert Path(result.path).parent.name == valid_type

    def test_forget_memory_rejects_path_outside_memories_root(self, tmp_path):
        from spellbook.memory.filestore import forget_memory

        # Create a file outside the memories root
        outside_file = tmp_path / "outside" / "secret.md"
        outside_file.parent.mkdir(parents=True, exist_ok=True)
        outside_file.write_text("sensitive data")

        # memory_dir is a subdirectory; parent is memories root
        memory_dir = str(tmp_path / "memories" / "project-abc")
        os.makedirs(memory_dir, exist_ok=True)

        with pytest.raises(ValueError, match="resolves outside memory directory"):
            forget_memory(str(outside_file), memory_dir, archive=True)

    def test_forget_memory_allows_sibling_memory_dir(self, tmp_path):
        """Forget should work for paths in sibling dirs (global scope)."""
        from spellbook.memory.filestore import forget_memory

        # Simulate project and global dirs sharing a parent
        memories_root = tmp_path / "memories"
        project_dir = memories_root / "project-abc"
        global_dir = memories_root / "_global" / "project"
        global_dir.mkdir(parents=True, exist_ok=True)
        project_dir.mkdir(parents=True, exist_ok=True)

        # Create a file in global dir
        global_file = global_dir / "test-memory.md"
        global_file.write_text("---\ntype: project\ncreated: 2026-04-14\n---\n\nContent.\n")

        # Forgetting from project_dir should work because global_dir
        # is within the same memories root
        result = forget_memory(str(global_file), str(project_dir), archive=False)
        assert result is True
        assert not global_file.exists()

    def test_list_memories_rejects_invalid_type_filter(self, tmp_path):
        from spellbook.memory.filestore import list_memories

        with pytest.raises(ValueError, match="Invalid memory type"):
            list_memories(str(tmp_path), type_filter="../secrets")

    def test_list_memories_accepts_valid_type_filter(self, tmp_path):
        from spellbook.memory.filestore import list_memories

        # Should not raise for valid types (returns empty list for empty dir)
        for valid_type in ("project", "user", "feedback", "reference"):
            result = list_memories(str(tmp_path), type_filter=valid_type)
            assert isinstance(result, list)


class TestFrontmatterValidation:
    """Test that required frontmatter fields are validated."""

    def test_missing_type_raises(self, tmp_path):
        from spellbook.memory.frontmatter import parse_frontmatter

        content = """\
---
created: 2026-04-14
---

Body text.
"""
        p = tmp_path / "no-type.md"
        p.write_text(content)
        with pytest.raises(ValueError, match="missing required field 'type'"):
            parse_frontmatter(str(p))

    def test_missing_created_raises(self, tmp_path):
        from spellbook.memory.frontmatter import parse_frontmatter

        content = """\
---
type: project
---

Body text.
"""
        p = tmp_path / "no-created.md"
        p.write_text(content)
        with pytest.raises(ValueError, match="missing required field 'created'"):
            parse_frontmatter(str(p))

    def test_invalid_created_type_raises(self, tmp_path):
        from spellbook.memory.frontmatter import parse_frontmatter

        content = """\
---
type: project
created: 12345
---

Body text.
"""
        p = tmp_path / "bad-created.md"
        p.write_text(content)
        with pytest.raises(ValueError, match="must be a date"):
            parse_frontmatter(str(p))


# ---------------------------------------------------------------------------
# I6: recall_memories over-fetches when scope filter is active
# ---------------------------------------------------------------------------


class TestRecallOverfetchWithScope:
    """When `scope` is set, post-filter can drop results below `limit`.

    The fix is for recall_memories to request `limit * 3` from QMD when a
    scope filter is active, then truncate after filtering.
    """

    def test_recall_overfetches_when_scope_filter_active(self, tmp_path, monkeypatch):
        import datetime as _dt

        from spellbook.memory import filestore as _fs
        from spellbook.memory.models import (
            MemoryFile,
            MemoryFrontmatter,
            MemoryResult,
        )

        # Build 30 fake QMD results: 10 with scope="project", 20 with
        # scope="global". Descending scores -> truncation well-defined.
        fake_results: list[MemoryResult] = []
        for i in range(30):
            scope = "project" if i % 3 == 0 else "global"
            path = tmp_path / f"fake_{i}.md"
            path.write_text(f"body {i}")
            fm = MemoryFrontmatter(
                type="project",
                created=_dt.date(2026, 4, 14),
                scope=scope,
            )
            mf = MemoryFile(path=str(path), frontmatter=fm, content=f"body {i}")
            fake_results.append(MemoryResult(memory=mf, score=1.0 - i * 0.01))

        captured_limits: list[int] = []

        def fake_qmd_search(*, query, memory_dirs, tags, file_path, limit, branch):
            captured_limits.append(limit)
            return fake_results[:limit]

        monkeypatch.setattr(_fs, "_qmd_search_memories", fake_qmd_search)

        results = _fs.recall_memories(
            query="ignored",
            memory_dir=str(tmp_path),
            scope="project",
            limit=10,
        )

        assert captured_limits == [30], (
            f"Expected recall_memories to over-fetch (limit*3=30) when a "
            f"scope filter is active; actual limits: {captured_limits}"
        )
        assert len(results) == 10, (
            f"Expected post-filter to return `limit` (10) matching results; "
            f"got {len(results)}."
        )
        for r in results:
            assert r.memory.frontmatter.scope == "project"

    def test_recall_uses_exact_limit_when_no_scope_filter(self, tmp_path, monkeypatch):
        """Backwards-compat: no scope filter -> no over-fetch."""
        import datetime as _dt

        from spellbook.memory import filestore as _fs
        from spellbook.memory.models import (
            MemoryFile,
            MemoryFrontmatter,
            MemoryResult,
        )

        fake_results: list[MemoryResult] = []
        for i in range(5):
            path = tmp_path / f"fake_{i}.md"
            path.write_text(f"body {i}")
            fm = MemoryFrontmatter(
                type="project",
                created=_dt.date(2026, 4, 14),
                scope="project",
            )
            mf = MemoryFile(path=str(path), frontmatter=fm, content=f"body {i}")
            fake_results.append(MemoryResult(memory=mf, score=1.0 - i * 0.1))

        captured_limits: list[int] = []

        def fake_qmd_search(*, query, memory_dirs, tags, file_path, limit, branch):
            captured_limits.append(limit)
            return fake_results[:limit]

        monkeypatch.setattr(_fs, "_qmd_search_memories", fake_qmd_search)

        results = _fs.recall_memories(
            query="ignored",
            memory_dir=str(tmp_path),
            scope=None,
            limit=5,
        )

        assert captured_limits == [5]
        assert len(results) == 5


# ---------------------------------------------------------------------------
# F1: recall_memories must update the access log in a single batched write
# ---------------------------------------------------------------------------


class TestRecallAccessLogBatchedWrite:
    """recall_memories should write the access log exactly once per call.

    Previously, the function called record_access in a per-result loop,
    which performed one read-modify-write cycle per returned memory. That
    is O(N) writes for an N-result call; gemini flagged this as redundant
    I/O. The fix loads the access log once at the top of the function and
    flushes a single batched update at the end.
    """

    @requires_memory_tools
    def test_writes_access_log_exactly_once_for_n_results(
        self, tmp_path, monkeypatch
    ):
        from spellbook.memory import access_log as _alog
        from spellbook.memory import filestore as _fs

        # Seed several real memories so QMD has something to score against.
        for i in range(5):
            _fs.store_memory(
                content=f"Batched access log probe {i}: tracking redundant I/O.",
                type="project",
                kind="fact",
                citations=[],
                tags=["batch-probe"],
                scope="project",
                branch=None,
                memory_dir=str(tmp_path),
            )

        # Count writes to the access log atomic-write helper. We patch on
        # the access_log module so any call site (including recall_memories
        # via the batched helper) is observed.
        write_calls: list[tuple] = []
        original_write = _alog._write_access_log

        def counting_write(log_path, data):
            write_calls.append((log_path, dict(data)))
            return original_write(log_path, data)

        monkeypatch.setattr(_alog, "_write_access_log", counting_write)

        results = _fs.recall_memories(
            query="batched access log probe tracking",
            memory_dir=str(tmp_path),
            limit=5,
        )

        # Sanity: we got multiple results back so we are exercising the
        # batched-write code path, not the trivial single-result case.
        assert len(results) >= 2, (
            "Test setup failure: needed multiple results to detect "
            f"redundant per-result writes, got {len(results)}"
        )

        # The fix: exactly one write call, regardless of result count.
        assert len(write_calls) == 1, (
            f"recall_memories wrote the access log {len(write_calls)} times "
            f"for {len(results)} results; expected exactly 1 batched write"
        )

        # And that single write must contain an entry for every returned
        # memory, proving the batch covered all of them rather than the
        # last one only.
        _log_path, written = write_calls[0]
        for r in results:
            rel = os.path.relpath(r.memory.path, str(tmp_path))
            assert rel in written, (
                f"batched access-log write missing entry for {rel}"
            )
            assert written[rel]["count"] >= 1
