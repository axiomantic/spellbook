"""Verify injection defense database schema exists after init_db."""
import os
import sqlite3

import pytest


@pytest.fixture
def db_path(tmp_path):
    """Create a temp DB and run init_db."""
    path = str(tmp_path / "test_spellbook.db")
    os.environ["SPELLBOOK_DB_PATH"] = path
    from spellbook.core.db import init_db
    init_db(path)
    yield path
    os.environ.pop("SPELLBOOK_DB_PATH", None)


def _get_table_columns(db_path: str, table: str) -> set[str]:
    conn = sqlite3.connect(db_path)
    cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    conn.close()
    return cols


def _table_exists(db_path: str, table: str) -> bool:
    conn = sqlite3.connect(db_path)
    result = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    conn.close()
    return result is not None


def test_intent_checks_table_exists(db_path):
    assert _table_exists(db_path, "intent_checks")


def test_intent_checks_columns(db_path):
    cols = _get_table_columns(db_path, "intent_checks")
    required = {"id", "session_id", "content_hash", "source_tool",
                "classification", "confidence", "evidence",
                "checked_at", "latency_ms", "cached"}
    missing = required - cols
    assert not missing, f"Missing columns in intent_checks: {missing}"


def test_session_content_accumulator_table_exists(db_path):
    assert _table_exists(db_path, "session_content_accumulator")


def test_session_content_accumulator_columns(db_path):
    cols = _get_table_columns(db_path, "session_content_accumulator")
    required = {"id", "session_id", "content_hash", "source_tool",
                "content_summary", "content_size", "received_at", "expires_at"}
    missing = required - cols
    assert not missing, f"Missing columns in session_content_accumulator: {missing}"


def test_sleuth_budget_table_exists(db_path):
    assert _table_exists(db_path, "sleuth_budget")


def test_sleuth_budget_columns(db_path):
    cols = _get_table_columns(db_path, "sleuth_budget")
    required = {"id", "session_id", "calls_remaining", "reset_at"}
    missing = required - cols
    assert not missing, f"Missing columns in sleuth_budget: {missing}"


def test_sleuth_cache_table_exists(db_path):
    assert _table_exists(db_path, "sleuth_cache")


def test_sleuth_cache_columns(db_path):
    cols = _get_table_columns(db_path, "sleuth_cache")
    required = {"id", "content_hash", "classification", "confidence",
                "cached_at", "expires_at"}
    missing = required - cols
    assert not missing, f"Missing columns in sleuth_cache: {missing}"


def test_trust_registry_has_signature_columns(db_path):
    cols = _get_table_columns(db_path, "trust_registry")
    required = {"signature", "signing_key_id", "analysis_status", "analysis_at"}
    missing = required - cols
    assert not missing, f"Missing signature columns in trust_registry: {missing}"
