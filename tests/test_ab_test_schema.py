"""Tests for A/B test database schema."""

import sqlite3
import pytest
from spellbook_mcp.db import init_db, get_connection


class TestABTestSchema:
    """Test A/B test tables are created correctly."""

    def test_experiments_table_exists(self, tmp_path):
        """Test experiments table is created with correct columns."""
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        conn = get_connection(db_path)
        cursor = conn.cursor()

        # Check table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='experiments'
        """)
        assert cursor.fetchone() is not None

        # Check columns
        cursor.execute("PRAGMA table_info(experiments)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        assert "id" in columns
        assert "name" in columns
        assert "skill_name" in columns
        assert "status" in columns
        assert "description" in columns
        assert "created_at" in columns
        assert "started_at" in columns
        assert "completed_at" in columns

    def test_experiment_variants_table_exists(self, tmp_path):
        """Test experiment_variants table is created with correct columns."""
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        conn = get_connection(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='experiment_variants'
        """)
        assert cursor.fetchone() is not None

        cursor.execute("PRAGMA table_info(experiment_variants)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        assert "id" in columns
        assert "experiment_id" in columns
        assert "variant_name" in columns
        assert "skill_version" in columns
        assert "weight" in columns
        assert "created_at" in columns

    def test_variant_assignments_table_exists(self, tmp_path):
        """Test variant_assignments table is created with correct columns."""
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        conn = get_connection(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='variant_assignments'
        """)
        assert cursor.fetchone() is not None

        cursor.execute("PRAGMA table_info(variant_assignments)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        assert "id" in columns
        assert "experiment_id" in columns
        assert "session_id" in columns
        assert "variant_id" in columns
        assert "assigned_at" in columns

    def test_skill_outcomes_has_experiment_variant_id_column(self, tmp_path):
        """Test skill_outcomes table has experiment_variant_id column."""
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        conn = get_connection(db_path)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(skill_outcomes)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        assert "experiment_variant_id" in columns

    def test_experiments_indices_exist(self, tmp_path):
        """Test experiments table has required indices."""
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        conn = get_connection(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND tbl_name='experiments'
        """)
        indices = {row[0] for row in cursor.fetchall()}

        assert "idx_experiments_skill_name" in indices
        assert "idx_experiments_status" in indices
