"""Tests for canary token MCP tools: do_canary_create and do_canary_check.

Validates:
- Token format: CANARY-{12 hex chars}-{type_code}
- Type codes: prompt->P, file->F, config->C, output->O
- Token uniqueness across multiple creates
- Exact-match detection (no false triggers on prefix or partial match)
- Trigger logging and DB marking
- Graceful handling when event logging is unavailable
"""

import re
import sqlite3

import pytest

from spellbook_mcp.db import get_connection, init_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path):
    """Initialize a fresh test database and return its path."""
    path = str(tmp_path / "canary_test.db")
    init_db(path)
    return path


# ---------------------------------------------------------------------------
# do_canary_create
# ---------------------------------------------------------------------------


class TestCanaryCreateTokenFormat:
    """Token format must be CANARY-{12 hex chars}-{type_code}."""

    def test_prompt_token_format(self, db_path):
        from spellbook_mcp.security.tools import do_canary_create

        result = do_canary_create("prompt", db_path=db_path)
        token = result["token"]
        assert re.fullmatch(r"CANARY-[0-9a-f]{12}-P", token)

    def test_file_token_format(self, db_path):
        from spellbook_mcp.security.tools import do_canary_create

        result = do_canary_create("file", db_path=db_path)
        token = result["token"]
        assert re.fullmatch(r"CANARY-[0-9a-f]{12}-F", token)

    def test_config_token_format(self, db_path):
        from spellbook_mcp.security.tools import do_canary_create

        result = do_canary_create("config", db_path=db_path)
        token = result["token"]
        assert re.fullmatch(r"CANARY-[0-9a-f]{12}-C", token)

    def test_output_token_format(self, db_path):
        from spellbook_mcp.security.tools import do_canary_create

        result = do_canary_create("output", db_path=db_path)
        token = result["token"]
        assert re.fullmatch(r"CANARY-[0-9a-f]{12}-O", token)


class TestCanaryCreateReturnShape:
    """Return dict must have token, token_type, and created keys."""

    def test_returns_token_key(self, db_path):
        from spellbook_mcp.security.tools import do_canary_create

        result = do_canary_create("prompt", db_path=db_path)
        assert "token" in result

    def test_returns_token_type_key(self, db_path):
        from spellbook_mcp.security.tools import do_canary_create

        result = do_canary_create("prompt", db_path=db_path)
        assert result["token_type"] == "prompt"

    def test_returns_created_true(self, db_path):
        from spellbook_mcp.security.tools import do_canary_create

        result = do_canary_create("prompt", db_path=db_path)
        assert result["created"] is True

    def test_return_shape_exact_keys(self, db_path):
        from spellbook_mcp.security.tools import do_canary_create

        result = do_canary_create("prompt", db_path=db_path)
        assert set(result.keys()) == {"token", "token_type", "created"}


class TestCanaryCreateTypeCodes:
    """Type code mapping: prompt->P, file->F, config->C, output->O."""

    def test_prompt_type_code_is_P(self, db_path):
        from spellbook_mcp.security.tools import do_canary_create

        result = do_canary_create("prompt", db_path=db_path)
        assert result["token"].endswith("-P")

    def test_file_type_code_is_F(self, db_path):
        from spellbook_mcp.security.tools import do_canary_create

        result = do_canary_create("file", db_path=db_path)
        assert result["token"].endswith("-F")

    def test_config_type_code_is_C(self, db_path):
        from spellbook_mcp.security.tools import do_canary_create

        result = do_canary_create("config", db_path=db_path)
        assert result["token"].endswith("-C")

    def test_output_type_code_is_O(self, db_path):
        from spellbook_mcp.security.tools import do_canary_create

        result = do_canary_create("output", db_path=db_path)
        assert result["token"].endswith("-O")


class TestCanaryCreateUniqueness:
    """Multiple creates must produce distinct tokens."""

    def test_two_tokens_are_different(self, db_path):
        from spellbook_mcp.security.tools import do_canary_create

        r1 = do_canary_create("prompt", db_path=db_path)
        r2 = do_canary_create("prompt", db_path=db_path)
        assert r1["token"] != r2["token"]

    def test_ten_tokens_all_unique(self, db_path):
        from spellbook_mcp.security.tools import do_canary_create

        tokens = {do_canary_create("prompt", db_path=db_path)["token"] for _ in range(10)}
        assert len(tokens) == 10


class TestCanaryCreateDatabaseRegistration:
    """Token must be persisted in canary_tokens table."""

    def test_token_exists_in_db(self, db_path):
        from spellbook_mcp.security.tools import do_canary_create

        result = do_canary_create("prompt", db_path=db_path)
        conn = get_connection(db_path)
        cur = conn.cursor()
        cur.execute("SELECT token, token_type FROM canary_tokens WHERE token = ?", (result["token"],))
        row = cur.fetchone()
        assert row is not None
        assert row[0] == result["token"]
        assert row[1] == "prompt"

    def test_context_stored_in_db(self, db_path):
        from spellbook_mcp.security.tools import do_canary_create

        result = do_canary_create("config", context="protect API keys", db_path=db_path)
        conn = get_connection(db_path)
        cur = conn.cursor()
        cur.execute("SELECT context FROM canary_tokens WHERE token = ?", (result["token"],))
        row = cur.fetchone()
        assert row[0] == "protect API keys"

    def test_context_defaults_to_none(self, db_path):
        from spellbook_mcp.security.tools import do_canary_create

        result = do_canary_create("prompt", db_path=db_path)
        conn = get_connection(db_path)
        cur = conn.cursor()
        cur.execute("SELECT context FROM canary_tokens WHERE token = ?", (result["token"],))
        row = cur.fetchone()
        assert row[0] is None

    def test_triggered_at_null_on_create(self, db_path):
        from spellbook_mcp.security.tools import do_canary_create

        result = do_canary_create("prompt", db_path=db_path)
        conn = get_connection(db_path)
        cur = conn.cursor()
        cur.execute("SELECT triggered_at FROM canary_tokens WHERE token = ?", (result["token"],))
        row = cur.fetchone()
        assert row[0] is None


class TestCanaryCreateInvalidType:
    """Invalid token_type must raise ValueError."""

    def test_invalid_type_raises(self, db_path):
        from spellbook_mcp.security.tools import do_canary_create

        with pytest.raises(ValueError, match="token_type"):
            do_canary_create("invalid", db_path=db_path)

    def test_empty_type_raises(self, db_path):
        from spellbook_mcp.security.tools import do_canary_create

        with pytest.raises(ValueError, match="token_type"):
            do_canary_create("", db_path=db_path)


# ---------------------------------------------------------------------------
# do_canary_check
# ---------------------------------------------------------------------------


class TestCanaryCheckCleanContent:
    """Content without any canary tokens should be clean."""

    def test_clean_content_returns_clean_true(self, db_path):
        from spellbook_mcp.security.tools import do_canary_check, do_canary_create

        # Create a canary so there's something to check against
        do_canary_create("prompt", db_path=db_path)
        result = do_canary_check("This is normal content", db_path=db_path)
        assert result["clean"] is True

    def test_clean_content_no_triggered_canaries(self, db_path):
        from spellbook_mcp.security.tools import do_canary_check, do_canary_create

        do_canary_create("prompt", db_path=db_path)
        result = do_canary_check("This is normal content", db_path=db_path)
        assert result["triggered_canaries"] == []

    def test_return_shape_exact_keys(self, db_path):
        from spellbook_mcp.security.tools import do_canary_check

        result = do_canary_check("anything", db_path=db_path)
        assert set(result.keys()) == {"clean", "triggered_canaries"}


class TestCanaryCheckNoFalseTriggers:
    """Prefix 'CANARY-' alone and partial matches must NOT trigger."""

    def test_canary_prefix_alone_does_not_trigger(self, db_path):
        from spellbook_mcp.security.tools import do_canary_check, do_canary_create

        do_canary_create("prompt", db_path=db_path)
        result = do_canary_check("Found CANARY- prefix in text", db_path=db_path)
        assert result["clean"] is True

    def test_partial_token_does_not_trigger(self, db_path):
        from spellbook_mcp.security.tools import do_canary_check, do_canary_create

        created = do_canary_create("prompt", db_path=db_path)
        # Use only first 10 chars of the token (partial match)
        partial = created["token"][:10]
        result = do_canary_check(f"Content with {partial} in it", db_path=db_path)
        assert result["clean"] is True

    def test_random_canary_format_does_not_trigger(self, db_path):
        from spellbook_mcp.security.tools import do_canary_check, do_canary_create

        do_canary_create("prompt", db_path=db_path)
        # A properly formatted but unregistered token should NOT trigger
        result = do_canary_check("CANARY-000000000000-P", db_path=db_path)
        assert result["clean"] is True

    def test_different_type_suffix_does_not_trigger(self, db_path):
        from spellbook_mcp.security.tools import do_canary_check, do_canary_create

        created = do_canary_create("prompt", db_path=db_path)
        # Alter the type code: replace -P with -F
        fake_token = created["token"][:-1] + "F"
        result = do_canary_check(f"Content: {fake_token}", db_path=db_path)
        assert result["clean"] is True


class TestCanaryCheckExactMatch:
    """Exact registered tokens in content must trigger."""

    def test_exact_token_triggers(self, db_path):
        from spellbook_mcp.security.tools import do_canary_check, do_canary_create

        created = do_canary_create("prompt", db_path=db_path)
        result = do_canary_check(f"Text with {created['token']} embedded", db_path=db_path)
        assert result["clean"] is False

    def test_triggered_canary_has_token(self, db_path):
        from spellbook_mcp.security.tools import do_canary_check, do_canary_create

        created = do_canary_create("prompt", db_path=db_path)
        result = do_canary_check(created["token"], db_path=db_path)
        assert len(result["triggered_canaries"]) == 1
        assert result["triggered_canaries"][0]["token"] == created["token"]

    def test_triggered_canary_has_token_type(self, db_path):
        from spellbook_mcp.security.tools import do_canary_check, do_canary_create

        created = do_canary_create("file", db_path=db_path)
        result = do_canary_check(created["token"], db_path=db_path)
        assert result["triggered_canaries"][0]["token_type"] == "file"

    def test_triggered_canary_has_context(self, db_path):
        from spellbook_mcp.security.tools import do_canary_check, do_canary_create

        created = do_canary_create("config", context="API key protection", db_path=db_path)
        result = do_canary_check(created["token"], db_path=db_path)
        assert result["triggered_canaries"][0]["context"] == "API key protection"

    def test_multiple_canaries_detected(self, db_path):
        from spellbook_mcp.security.tools import do_canary_check, do_canary_create

        c1 = do_canary_create("prompt", db_path=db_path)
        c2 = do_canary_create("file", db_path=db_path)
        content = f"Start {c1['token']} middle {c2['token']} end"
        result = do_canary_check(content, db_path=db_path)
        assert result["clean"] is False
        assert len(result["triggered_canaries"]) == 2

    def test_token_embedded_in_long_text(self, db_path):
        from spellbook_mcp.security.tools import do_canary_check, do_canary_create

        created = do_canary_create("output", db_path=db_path)
        content = "A" * 10000 + created["token"] + "B" * 10000
        result = do_canary_check(content, db_path=db_path)
        assert result["clean"] is False


class TestCanaryCheckMarksTriggered:
    """Triggered canary must be marked in DB (triggered_at set)."""

    def test_triggered_at_set_in_db(self, db_path):
        from spellbook_mcp.security.tools import do_canary_check, do_canary_create

        created = do_canary_create("prompt", db_path=db_path)
        do_canary_check(created["token"], db_path=db_path)

        conn = get_connection(db_path)
        cur = conn.cursor()
        cur.execute("SELECT triggered_at FROM canary_tokens WHERE token = ?", (created["token"],))
        row = cur.fetchone()
        assert row[0] is not None

    def test_triggered_by_set_to_canary_check(self, db_path):
        from spellbook_mcp.security.tools import do_canary_check, do_canary_create

        created = do_canary_create("prompt", db_path=db_path)
        do_canary_check(created["token"], db_path=db_path)

        conn = get_connection(db_path)
        cur = conn.cursor()
        cur.execute("SELECT triggered_by FROM canary_tokens WHERE token = ?", (created["token"],))
        row = cur.fetchone()
        assert row[0] == "security_canary_check"

    def test_non_triggered_canary_not_marked(self, db_path):
        from spellbook_mcp.security.tools import do_canary_check, do_canary_create

        c1 = do_canary_create("prompt", db_path=db_path)
        c2 = do_canary_create("file", db_path=db_path)
        # Only trigger c1
        do_canary_check(c1["token"], db_path=db_path)

        conn = get_connection(db_path)
        cur = conn.cursor()
        cur.execute("SELECT triggered_at FROM canary_tokens WHERE token = ?", (c2["token"],))
        row = cur.fetchone()
        assert row[0] is None


class TestCanaryCheckLogsEvent:
    """Trigger must log a CRITICAL security event."""

    def test_critical_event_logged(self, db_path):
        from spellbook_mcp.security.tools import do_canary_check, do_canary_create

        created = do_canary_create("prompt", db_path=db_path)
        do_canary_check(created["token"], db_path=db_path)

        conn = get_connection(db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT severity, event_type FROM security_events WHERE event_type = 'canary_triggered'"
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "CRITICAL"

    def test_event_detail_contains_token(self, db_path):
        from spellbook_mcp.security.tools import do_canary_check, do_canary_create

        created = do_canary_create("prompt", db_path=db_path)
        do_canary_check(created["token"], db_path=db_path)

        conn = get_connection(db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT detail FROM security_events WHERE event_type = 'canary_triggered'"
        )
        row = cur.fetchone()
        assert created["token"] in row[0]

    def test_no_event_logged_when_clean(self, db_path):
        from spellbook_mcp.security.tools import do_canary_check, do_canary_create

        do_canary_create("prompt", db_path=db_path)
        do_canary_check("clean content", db_path=db_path)

        conn = get_connection(db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM security_events WHERE event_type = 'canary_triggered'")
        count = cur.fetchone()[0]
        assert count == 0


class TestCanaryCheckEmptyDatabase:
    """Check with no registered canaries should be clean."""

    def test_no_canaries_is_clean(self, db_path):
        from spellbook_mcp.security.tools import do_canary_check

        result = do_canary_check("CANARY-anything-P", db_path=db_path)
        assert result["clean"] is True

    def test_no_canaries_empty_triggered(self, db_path):
        from spellbook_mcp.security.tools import do_canary_check

        result = do_canary_check("anything", db_path=db_path)
        assert result["triggered_canaries"] == []
