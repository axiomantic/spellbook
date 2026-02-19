"""Tests for trust registry MCP tools: do_set_trust() and do_check_trust().

Validates:
- Registration stores trust level for a content hash
- Retrieval returns stored trust level
- Trust hierarchy enforcement (system > verified > user > untrusted > hostile)
- TTL expiration causes entry to be treated as expired
- Unregistered content returns null trust level and meets_requirement=False
- Re-registration overwrites previous entry
"""

import sqlite3
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from spellbook_mcp.db import get_connection, init_db


def _setup_db(tmp_path):
    """Initialize a fresh test database and return its path."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    return db_path


# =============================================================================
# do_set_trust tests
# =============================================================================


class TestDoSetTrustBasicRegistration:
    """Tests for do_set_trust() registering trust entries."""

    def test_returns_registered_true(self, tmp_path):
        from spellbook_mcp.security.tools import do_set_trust

        db_path = _setup_db(tmp_path)
        result = do_set_trust(
            content_hash="abc123def456",
            source="test-source",
            trust_level="user",
            db_path=db_path,
        )
        assert result["registered"] is True

    def test_returns_content_hash(self, tmp_path):
        from spellbook_mcp.security.tools import do_set_trust

        db_path = _setup_db(tmp_path)
        result = do_set_trust(
            content_hash="abc123def456",
            source="test-source",
            trust_level="user",
            db_path=db_path,
        )
        assert result["content_hash"] == "abc123def456"

    def test_returns_trust_level(self, tmp_path):
        from spellbook_mcp.security.tools import do_set_trust

        db_path = _setup_db(tmp_path)
        result = do_set_trust(
            content_hash="abc123def456",
            source="test-source",
            trust_level="verified",
            db_path=db_path,
        )
        assert result["trust_level"] == "verified"

    def test_returns_expires_at_null_when_no_ttl(self, tmp_path):
        from spellbook_mcp.security.tools import do_set_trust

        db_path = _setup_db(tmp_path)
        result = do_set_trust(
            content_hash="abc123def456",
            source="test-source",
            trust_level="user",
            db_path=db_path,
        )
        assert result["expires_at"] is None

    def test_stores_entry_in_database(self, tmp_path):
        from spellbook_mcp.security.tools import do_set_trust

        db_path = _setup_db(tmp_path)
        do_set_trust(
            content_hash="abc123def456",
            source="test-source",
            trust_level="system",
            db_path=db_path,
        )
        conn = get_connection(db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT content_hash, source, trust_level FROM trust_registry WHERE content_hash = ?",
            ("abc123def456",),
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "abc123def456"
        assert row[1] == "test-source"
        assert row[2] == "system"

    def test_all_trust_levels_accepted(self, tmp_path):
        from spellbook_mcp.security.tools import do_set_trust

        db_path = _setup_db(tmp_path)
        for level in ("system", "verified", "user", "untrusted", "hostile"):
            result = do_set_trust(
                content_hash=f"hash-{level}",
                source="test",
                trust_level=level,
                db_path=db_path,
            )
            assert result["registered"] is True
            assert result["trust_level"] == level


class TestDoSetTrustWithTTL:
    """Tests for do_set_trust() with TTL (time-to-live)."""

    def test_returns_expires_at_when_ttl_set(self, tmp_path):
        from spellbook_mcp.security.tools import do_set_trust

        db_path = _setup_db(tmp_path)
        result = do_set_trust(
            content_hash="abc123",
            source="test",
            trust_level="user",
            ttl_hours=24,
            db_path=db_path,
        )
        assert result["expires_at"] is not None

    def test_expires_at_is_in_the_future(self, tmp_path):
        from spellbook_mcp.security.tools import do_set_trust

        db_path = _setup_db(tmp_path)
        result = do_set_trust(
            content_hash="abc123",
            source="test",
            trust_level="user",
            ttl_hours=24,
            db_path=db_path,
        )
        expires = datetime.fromisoformat(result["expires_at"])
        now = datetime.now(timezone.utc)
        assert expires > now

    def test_expires_at_approximately_correct(self, tmp_path):
        from spellbook_mcp.security.tools import do_set_trust

        db_path = _setup_db(tmp_path)
        before = datetime.now(timezone.utc)
        result = do_set_trust(
            content_hash="abc123",
            source="test",
            trust_level="user",
            ttl_hours=48,
            db_path=db_path,
        )
        after = datetime.now(timezone.utc)

        expires = datetime.fromisoformat(result["expires_at"])
        expected_min = before + timedelta(hours=48)
        expected_max = after + timedelta(hours=48)
        assert expected_min <= expires <= expected_max


class TestDoSetTrustReRegistration:
    """Tests for do_set_trust() overwriting existing entries."""

    def test_reregistration_overwrites_trust_level(self, tmp_path):
        from spellbook_mcp.security.tools import do_set_trust

        db_path = _setup_db(tmp_path)
        do_set_trust(
            content_hash="abc123",
            source="test",
            trust_level="user",
            db_path=db_path,
        )
        result = do_set_trust(
            content_hash="abc123",
            source="test-updated",
            trust_level="verified",
            db_path=db_path,
        )
        assert result["trust_level"] == "verified"

    def test_reregistration_leaves_single_entry(self, tmp_path):
        from spellbook_mcp.security.tools import do_set_trust

        db_path = _setup_db(tmp_path)
        do_set_trust(
            content_hash="abc123",
            source="test",
            trust_level="user",
            db_path=db_path,
        )
        do_set_trust(
            content_hash="abc123",
            source="test-updated",
            trust_level="verified",
            db_path=db_path,
        )
        conn = get_connection(db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM trust_registry WHERE content_hash = ?",
            ("abc123",),
        )
        count = cur.fetchone()[0]
        assert count == 1

    def test_reregistration_updates_source(self, tmp_path):
        from spellbook_mcp.security.tools import do_set_trust

        db_path = _setup_db(tmp_path)
        do_set_trust(
            content_hash="abc123",
            source="original",
            trust_level="user",
            db_path=db_path,
        )
        do_set_trust(
            content_hash="abc123",
            source="updated",
            trust_level="user",
            db_path=db_path,
        )
        conn = get_connection(db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT source FROM trust_registry WHERE content_hash = ?",
            ("abc123",),
        )
        assert cur.fetchone()[0] == "updated"


class TestDoSetTrustValidation:
    """Tests for do_set_trust() input validation."""

    def test_rejects_invalid_trust_level(self, tmp_path):
        from spellbook_mcp.security.tools import do_set_trust

        db_path = _setup_db(tmp_path)
        with pytest.raises(ValueError, match="Invalid trust_level"):
            do_set_trust(
                content_hash="abc123",
                source="test",
                trust_level="invalid",
                db_path=db_path,
            )


# =============================================================================
# do_check_trust tests
# =============================================================================


class TestDoCheckTrustRegisteredContent:
    """Tests for do_check_trust() with registered content."""

    def test_returns_stored_trust_level(self, tmp_path):
        from spellbook_mcp.security.tools import do_check_trust, do_set_trust

        db_path = _setup_db(tmp_path)
        do_set_trust(
            content_hash="abc123",
            source="test",
            trust_level="verified",
            db_path=db_path,
        )
        result = do_check_trust(
            content_hash="abc123",
            required_level="user",
            db_path=db_path,
        )
        assert result["trust_level"] == "verified"

    def test_returns_content_hash(self, tmp_path):
        from spellbook_mcp.security.tools import do_check_trust, do_set_trust

        db_path = _setup_db(tmp_path)
        do_set_trust(
            content_hash="abc123",
            source="test",
            trust_level="user",
            db_path=db_path,
        )
        result = do_check_trust(
            content_hash="abc123",
            required_level="user",
            db_path=db_path,
        )
        assert result["content_hash"] == "abc123"

    def test_returns_required_level(self, tmp_path):
        from spellbook_mcp.security.tools import do_check_trust, do_set_trust

        db_path = _setup_db(tmp_path)
        do_set_trust(
            content_hash="abc123",
            source="test",
            trust_level="user",
            db_path=db_path,
        )
        result = do_check_trust(
            content_hash="abc123",
            required_level="verified",
            db_path=db_path,
        )
        assert result["required_level"] == "verified"

    def test_returns_expired_false_for_non_expired(self, tmp_path):
        from spellbook_mcp.security.tools import do_check_trust, do_set_trust

        db_path = _setup_db(tmp_path)
        do_set_trust(
            content_hash="abc123",
            source="test",
            trust_level="user",
            db_path=db_path,
        )
        result = do_check_trust(
            content_hash="abc123",
            required_level="user",
            db_path=db_path,
        )
        assert result["expired"] is False

    def test_all_required_keys_present(self, tmp_path):
        from spellbook_mcp.security.tools import do_check_trust, do_set_trust

        db_path = _setup_db(tmp_path)
        do_set_trust(
            content_hash="abc123",
            source="test",
            trust_level="user",
            db_path=db_path,
        )
        result = do_check_trust(
            content_hash="abc123",
            required_level="user",
            db_path=db_path,
        )
        expected_keys = {
            "content_hash",
            "trust_level",
            "required_level",
            "meets_requirement",
            "expired",
        }
        assert set(result.keys()) == expected_keys


class TestDoCheckTrustUnregisteredContent:
    """Tests for do_check_trust() with unregistered content."""

    def test_returns_null_trust_level(self, tmp_path):
        from spellbook_mcp.security.tools import do_check_trust

        db_path = _setup_db(tmp_path)
        result = do_check_trust(
            content_hash="nonexistent",
            required_level="user",
            db_path=db_path,
        )
        assert result["trust_level"] is None

    def test_returns_meets_requirement_false(self, tmp_path):
        from spellbook_mcp.security.tools import do_check_trust

        db_path = _setup_db(tmp_path)
        result = do_check_trust(
            content_hash="nonexistent",
            required_level="user",
            db_path=db_path,
        )
        assert result["meets_requirement"] is False

    def test_returns_expired_false(self, tmp_path):
        from spellbook_mcp.security.tools import do_check_trust

        db_path = _setup_db(tmp_path)
        result = do_check_trust(
            content_hash="nonexistent",
            required_level="user",
            db_path=db_path,
        )
        assert result["expired"] is False


class TestDoCheckTrustHierarchy:
    """Tests for trust hierarchy enforcement.

    Hierarchy: system(5) > verified(4) > user(3) > untrusted(2) > hostile(1)
    meets_requirement is True when stored level >= required level.
    """

    @pytest.mark.parametrize(
        "stored,required,expected",
        [
            # Same level always meets
            ("system", "system", True),
            ("verified", "verified", True),
            ("user", "user", True),
            ("untrusted", "untrusted", True),
            ("hostile", "hostile", True),
            # Higher stored meets lower required
            ("system", "verified", True),
            ("system", "user", True),
            ("system", "untrusted", True),
            ("system", "hostile", True),
            ("verified", "user", True),
            ("verified", "untrusted", True),
            ("verified", "hostile", True),
            ("user", "untrusted", True),
            ("user", "hostile", True),
            ("untrusted", "hostile", True),
            # Lower stored does NOT meet higher required
            ("hostile", "untrusted", False),
            ("hostile", "user", False),
            ("hostile", "verified", False),
            ("hostile", "system", False),
            ("untrusted", "user", False),
            ("untrusted", "verified", False),
            ("untrusted", "system", False),
            ("user", "verified", False),
            ("user", "system", False),
            ("verified", "system", False),
        ],
    )
    def test_hierarchy_enforcement(self, tmp_path, stored, required, expected):
        from spellbook_mcp.security.tools import do_check_trust, do_set_trust

        db_path = _setup_db(tmp_path)
        do_set_trust(
            content_hash="test-hash",
            source="test",
            trust_level=stored,
            db_path=db_path,
        )
        result = do_check_trust(
            content_hash="test-hash",
            required_level=required,
            db_path=db_path,
        )
        assert result["meets_requirement"] is expected, (
            f"stored={stored}, required={required}: "
            f"expected meets_requirement={expected}, got {result['meets_requirement']}"
        )


class TestDoCheckTrustExpiration:
    """Tests for TTL expiration behavior."""

    def test_expired_entry_returns_null_trust_level(self, tmp_path):
        from spellbook_mcp.security.tools import do_check_trust, do_set_trust

        db_path = _setup_db(tmp_path)
        # Register with TTL
        do_set_trust(
            content_hash="abc123",
            source="test",
            trust_level="verified",
            ttl_hours=1,
            db_path=db_path,
        )
        # Manually set expires_at to the past
        conn = get_connection(db_path)
        past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        conn.execute(
            "UPDATE trust_registry SET expires_at = ? WHERE content_hash = ?",
            (past, "abc123"),
        )
        conn.commit()

        result = do_check_trust(
            content_hash="abc123",
            required_level="user",
            db_path=db_path,
        )
        assert result["trust_level"] is None

    def test_expired_entry_returns_meets_requirement_false(self, tmp_path):
        from spellbook_mcp.security.tools import do_check_trust, do_set_trust

        db_path = _setup_db(tmp_path)
        do_set_trust(
            content_hash="abc123",
            source="test",
            trust_level="system",
            ttl_hours=1,
            db_path=db_path,
        )
        conn = get_connection(db_path)
        past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        conn.execute(
            "UPDATE trust_registry SET expires_at = ? WHERE content_hash = ?",
            (past, "abc123"),
        )
        conn.commit()

        result = do_check_trust(
            content_hash="abc123",
            required_level="hostile",
            db_path=db_path,
        )
        assert result["meets_requirement"] is False

    def test_expired_entry_returns_expired_true(self, tmp_path):
        from spellbook_mcp.security.tools import do_check_trust, do_set_trust

        db_path = _setup_db(tmp_path)
        do_set_trust(
            content_hash="abc123",
            source="test",
            trust_level="verified",
            ttl_hours=1,
            db_path=db_path,
        )
        conn = get_connection(db_path)
        past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        conn.execute(
            "UPDATE trust_registry SET expires_at = ? WHERE content_hash = ?",
            (past, "abc123"),
        )
        conn.commit()

        result = do_check_trust(
            content_hash="abc123",
            required_level="user",
            db_path=db_path,
        )
        assert result["expired"] is True

    def test_non_expired_entry_returns_stored_level(self, tmp_path):
        from spellbook_mcp.security.tools import do_check_trust, do_set_trust

        db_path = _setup_db(tmp_path)
        do_set_trust(
            content_hash="abc123",
            source="test",
            trust_level="verified",
            ttl_hours=24,
            db_path=db_path,
        )
        result = do_check_trust(
            content_hash="abc123",
            required_level="user",
            db_path=db_path,
        )
        assert result["trust_level"] == "verified"
        assert result["expired"] is False

    def test_no_ttl_entry_never_expires(self, tmp_path):
        from spellbook_mcp.security.tools import do_check_trust, do_set_trust

        db_path = _setup_db(tmp_path)
        do_set_trust(
            content_hash="abc123",
            source="test",
            trust_level="user",
            db_path=db_path,
        )
        result = do_check_trust(
            content_hash="abc123",
            required_level="user",
            db_path=db_path,
        )
        assert result["trust_level"] == "user"
        assert result["expired"] is False
        assert result["meets_requirement"] is True


class TestDoCheckTrustValidation:
    """Tests for do_check_trust() input validation."""

    def test_rejects_invalid_required_level(self, tmp_path):
        from spellbook_mcp.security.tools import do_check_trust

        db_path = _setup_db(tmp_path)
        with pytest.raises(ValueError, match="Invalid required_level"):
            do_check_trust(
                content_hash="abc123",
                required_level="invalid",
                db_path=db_path,
            )
