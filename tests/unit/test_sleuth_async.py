"""Tests for PromptSleuth async classification and caching."""
import os
import sqlite3
import bigfoot  # noqa: F401 (canonical mocking framework)
import pytest


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    os.environ["SPELLBOOK_DB_PATH"] = path
    from spellbook.core.db import init_db
    init_db(path)
    yield path
    os.environ.pop("SPELLBOOK_DB_PATH", None)


@pytest.mark.asyncio
async def test_get_sleuth_cache_miss(db_path):
    from spellbook.security.sleuth import get_sleuth_cache
    result = await get_sleuth_cache("nonexistent-hash", db_path=db_path)
    assert result is None


@pytest.mark.asyncio
async def test_write_and_read_sleuth_cache(db_path):
    from spellbook.security.sleuth import write_sleuth_cache, get_sleuth_cache
    await write_sleuth_cache(
        "test-hash", {"classification": "DATA", "confidence": 0.9}, db_path=db_path
    )
    result = await get_sleuth_cache("test-hash", db_path=db_path)
    assert result is not None
    assert result["classification"] == "DATA"


@pytest.mark.asyncio
async def test_write_intent_check(db_path):
    from spellbook.security.sleuth import write_intent_check
    await write_intent_check(
        content_hash_val="hash-1",
        source_tool="WebFetch",
        result={"classification": "DIRECTIVE", "confidence": 0.85, "evidence": "override"},
        session_id="sess-1",
        latency_ms=150,
        db_path=db_path,
    )
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT * FROM intent_checks WHERE content_hash='hash-1'").fetchone()
    conn.close()
    assert row is not None


@pytest.mark.asyncio
async def test_get_session_budget_creates_default(db_path):
    from spellbook.security.sleuth import get_session_budget
    budget = await get_session_budget("test-session", db_path=db_path)
    assert budget["calls_remaining"] == 50


@pytest.mark.asyncio
async def test_get_session_budget_returns_existing(db_path):
    from spellbook.security.sleuth import get_session_budget
    # First call creates
    await get_session_budget("test-session", db_path=db_path)
    # Second call retrieves
    budget = await get_session_budget("test-session", db_path=db_path)
    assert budget["calls_remaining"] == 50


@pytest.mark.asyncio
async def test_decrement_budget(db_path):
    from spellbook.security.sleuth import get_session_budget, decrement_budget
    await get_session_budget("test-session", db_path=db_path)
    remaining = await decrement_budget("test-session", db_path=db_path)
    assert remaining == 49


@pytest.mark.asyncio
async def test_reset_session_budget(db_path):
    from spellbook.security.sleuth import get_session_budget, decrement_budget, reset_session_budget
    await get_session_budget("test-session", db_path=db_path)
    await decrement_budget("test-session", db_path=db_path)
    result = await reset_session_budget("test-session", calls=100, db_path=db_path)
    assert result["calls_remaining"] == 100


@pytest.mark.asyncio
async def test_sleuth_cache_cleanup_expired(db_path):
    """Expired cache entries are cleaned up on write."""
    from spellbook.security.sleuth import write_sleuth_cache, get_sleuth_cache
    # Write a valid entry
    await write_sleuth_cache(
        "valid-hash", {"classification": "DATA", "confidence": 0.9}, db_path=db_path
    )
    # Manually expire it
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE sleuth_cache SET expires_at = datetime('now', '-1 hour') WHERE content_hash = 'valid-hash'"
    )
    conn.commit()
    conn.close()
    # Read should return None (expired)
    result = await get_sleuth_cache("valid-hash", db_path=db_path)
    assert result is None
