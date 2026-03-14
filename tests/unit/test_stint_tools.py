"""Unit tests for Zeigarnik stint stack MCP tools."""

import json
import os
import sqlite3
import tempfile
from datetime import datetime, timezone

import pytest

# Ensure spellbook_mcp is importable
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from spellbook_mcp.db import init_db, get_connection, close_all_connections


@pytest.fixture(autouse=True)
def isolated_db(tmp_path):
    """Use a temporary database for each test."""
    db_path = str(tmp_path / "test_spellbook.db")
    init_db(db_path)
    yield db_path
    close_all_connections()


class TestStintDatabaseSchema:
    """Verify stint_stack and stint_correction_events tables are created."""

    def test_stint_stack_table_exists(self, isolated_db):
        conn = get_connection(isolated_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='stint_stack'"
        )
        assert cursor.fetchone() is not None, "stint_stack table not created"

    def test_stint_stack_has_correct_columns(self, isolated_db):
        conn = get_connection(isolated_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(stint_stack)")
        columns = {row[1] for row in cursor.fetchall()}
        expected = {"id", "project_path", "session_id", "stack_json", "updated_at"}
        assert expected.issubset(columns), f"Missing columns: {expected - columns}"

    def test_stint_stack_project_path_unique(self, isolated_db):
        conn = get_connection(isolated_db)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO stint_stack (project_path, stack_json) VALUES (?, ?)",
            ("/test/project", "[]"),
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute(
                "INSERT INTO stint_stack (project_path, stack_json) VALUES (?, ?)",
                ("/test/project", "[]"),
            )
            conn.commit()

    def test_stint_correction_events_table_exists(self, isolated_db):
        conn = get_connection(isolated_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='stint_correction_events'"
        )
        assert cursor.fetchone() is not None, "stint_correction_events table not created"

    def test_stint_correction_events_has_correct_columns(self, isolated_db):
        conn = get_connection(isolated_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(stint_correction_events)")
        columns = {row[1] for row in cursor.fetchall()}
        expected = {
            "id", "project_path", "session_id", "correction_type",
            "old_stack_json", "new_stack_json", "diff_summary", "created_at",
        }
        assert expected.issubset(columns), f"Missing columns: {expected - columns}"

    def test_stint_stack_index_exists(self, isolated_db):
        conn = get_connection(isolated_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_stint_stack_project'"
        )
        assert cursor.fetchone() is not None, "idx_stint_stack_project index not created"

    def test_stint_corrections_indexes_exist(self, isolated_db):
        conn = get_connection(isolated_db)
        cursor = conn.cursor()
        for index_name in ("idx_stint_corrections_project", "idx_stint_corrections_type"):
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                (index_name,),
            )
            assert cursor.fetchone() is not None, f"{index_name} index not created"
