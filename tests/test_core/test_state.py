"""Tests for ``spellbook.core.state``.

Covers the read/write/atomic-replace semantics of the state module, plus the
one-shot config->state migration that session_init invokes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def state_paths(tmp_path, monkeypatch):
    """Redirect both config_dir and data_dir at temp paths for each test.

    The state module reads/writes ``get_data_dir()/state.json``; the migration
    reads ``get_config_dir()/spellbook.json``. Both helpers live on
    ``spellbook.core.paths`` / ``spellbook.core.compat`` and are imported
    locally inside the target functions, so a monkeypatch of the factory
    function on the source module reaches every caller.
    """
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    config_dir.mkdir()
    data_dir.mkdir()

    # state.py uses spellbook.core.paths.get_data_dir directly
    monkeypatch.setattr(
        "spellbook.core.paths.get_data_dir",
        lambda app_name="spellbook": data_dir,
    )
    monkeypatch.setattr(
        "spellbook.core.state.get_data_dir",
        lambda app_name="spellbook": data_dir,
    )
    # config.py imports get_config_dir from compat at module load time, so
    # the patch has to land on config's copy of the name.
    monkeypatch.setattr(
        "spellbook.core.config.get_config_dir",
        lambda app_name="spellbook": config_dir,
    )
    monkeypatch.setattr(
        "spellbook.core.compat.get_config_dir",
        lambda app_name="spellbook": config_dir,
    )

    return {"config_dir": config_dir, "data_dir": data_dir}


# ---------------------------------------------------------------------------
# Basic read/write
# ---------------------------------------------------------------------------


class TestReadState:
    def test_missing_file_returns_empty_dict(self, state_paths):
        from spellbook.core.state import read_state

        assert read_state() == {}

    def test_returns_parsed_contents(self, state_paths):
        from spellbook.core.state import read_state

        state_path = state_paths["data_dir"] / "state.json"
        state_path.write_text(json.dumps({"foo": 1, "bar": "baz"}))

        assert read_state() == {"foo": 1, "bar": "baz"}

    def test_malformed_json_returns_empty_dict(self, state_paths, caplog):
        from spellbook.core.state import read_state

        (state_paths["data_dir"] / "state.json").write_text("{not json")

        with caplog.at_level("WARNING"):
            assert read_state() == {}
        # A warning should be emitted so the operator can spot the corruption.
        assert any("state file" in r.message for r in caplog.records)


class TestWriteState:
    def test_creates_file_on_first_write(self, state_paths):
        from spellbook.core.state import write_state

        state_path = state_paths["data_dir"] / "state.json"
        assert not state_path.exists()

        write_state({"hello": "world"})

        assert state_path.exists()
        assert json.loads(state_path.read_text()) == {"hello": "world"}

    def test_creates_parent_dir(self, tmp_path, monkeypatch):
        """write_state should mkdir -p the parent if it is missing."""
        target_dir = tmp_path / "nonexistent"
        monkeypatch.setattr(
            "spellbook.core.state.get_data_dir",
            lambda app_name="spellbook": target_dir,
        )

        from spellbook.core.state import write_state

        write_state({"a": 1})

        assert (target_dir / "state.json").exists()

    def test_overwrites_existing_file(self, state_paths):
        from spellbook.core.state import write_state

        state_path = state_paths["data_dir"] / "state.json"
        state_path.write_text(json.dumps({"old": True}))

        write_state({"new": True})

        assert json.loads(state_path.read_text()) == {"new": True}

    def test_atomic_write_leaves_no_temp_on_success(self, state_paths):
        """After a clean write, no .tmp siblings remain."""
        from spellbook.core.state import write_state

        write_state({"k": "v"})

        leftovers = list(state_paths["data_dir"].glob("*.tmp"))
        assert leftovers == []


class TestGetSetState:
    def test_get_returns_default_when_missing(self, state_paths):
        from spellbook.core.state import get_state

        assert get_state("never_set", "fallback") == "fallback"
        assert get_state("never_set") is None

    def test_set_preserves_other_keys(self, state_paths):
        from spellbook.core.state import get_state, set_state, write_state

        write_state({"alpha": 1, "beta": 2})
        set_state("gamma", 3)

        assert get_state("alpha") == 1
        assert get_state("beta") == 2
        assert get_state("gamma") == 3

    def test_set_overwrites(self, state_paths):
        from spellbook.core.state import get_state, set_state

        set_state("k", "v1")
        set_state("k", "v2")

        assert get_state("k") == "v2"


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


class TestMigration:
    def test_noop_when_config_missing(self, state_paths):
        from spellbook.core.state import migrate_config_to_state

        result = migrate_config_to_state()
        assert result["migrated"] is False
        # No side-effects on state file either.
        assert not (state_paths["data_dir"] / "state.json").exists()

    def test_noop_when_config_is_clean(self, state_paths):
        from spellbook.core.state import migrate_config_to_state

        cfg = state_paths["config_dir"] / "spellbook.json"
        cfg.write_text(json.dumps({"notify_enabled": True, "auto_update": True}))
        original = cfg.read_text()

        result = migrate_config_to_state()

        assert result["migrated"] is False
        # Config file untouched
        assert cfg.read_text() == original
        # No state file either
        assert not (state_paths["data_dir"] / "state.json").exists()

    def test_dirty_config_migrates_fully(self, state_paths):
        """Start with a dirty spellbook.json, verify the end state."""
        from spellbook.core.state import migrate_config_to_state, read_state

        cfg = state_paths["config_dir"] / "spellbook.json"
        dirty = {
            # User-facing keys that must survive
            "notify_enabled": True,
            "auto_update": True,
            "session_mode": "fun",
            # Dead keys that must be stripped
            "tts_enabled": False,
            "tts_volume": 0.3,
            "telemetry_enabled": False,
            # State keys that must be moved
            "update_check_failures": 2,
            "auto_update_branch": "main",
        }
        cfg.write_text(json.dumps(dirty, indent=2))

        result = migrate_config_to_state()

        assert result["migrated"] is True
        assert set(result["removed"]) == {
            "tts_enabled",
            "tts_volume",
            "telemetry_enabled",
        }
        assert result["moved"] == {
            "update_check_failures": 2,
            "auto_update_branch": "main",
        }

        # spellbook.json keeps only user-facing keys
        post_config = json.loads(cfg.read_text())
        assert post_config == {
            "notify_enabled": True,
            "auto_update": True,
            "session_mode": "fun",
        }

        # state.json has the moved values
        assert read_state() == {
            "update_check_failures": 2,
            "auto_update_branch": "main",
        }

    def test_migration_is_idempotent(self, state_paths):
        from spellbook.core.state import migrate_config_to_state

        cfg = state_paths["config_dir"] / "spellbook.json"
        cfg.write_text(
            json.dumps({"tts_enabled": True, "update_check_failures": 1})
        )

        first = migrate_config_to_state()
        assert first["migrated"] is True

        second = migrate_config_to_state()
        assert second["migrated"] is False
        assert second["removed"] == []
        assert second["moved"] == {}

    def test_state_json_values_not_clobbered(self, state_paths):
        """If state.json already has a key, the config.json value must not overwrite it."""
        from spellbook.core.state import (
            migrate_config_to_state,
            read_state,
            write_state,
        )

        write_state({"update_check_failures": 99, "auto_update_branch": "dev"})

        cfg = state_paths["config_dir"] / "spellbook.json"
        cfg.write_text(
            json.dumps(
                {
                    "update_check_failures": 0,
                    "auto_update_branch": "main",
                }
            )
        )

        migrate_config_to_state()

        # state.json wins where it already had a value
        assert read_state() == {
            "update_check_failures": 99,
            "auto_update_branch": "dev",
        }

    def test_only_dead_keys_present(self, state_paths):
        from spellbook.core.state import migrate_config_to_state, read_state

        cfg = state_paths["config_dir"] / "spellbook.json"
        cfg.write_text(json.dumps({"tts_enabled": True, "notify_enabled": True}))

        result = migrate_config_to_state()

        assert result["migrated"] is True
        assert set(result["removed"]) == {"tts_enabled"}
        assert result["moved"] == {}
        assert json.loads(cfg.read_text()) == {"notify_enabled": True}
        # No state file was created because no state keys moved.
        state_path = state_paths["data_dir"] / "state.json"
        # An empty migration should not touch state.json.
        assert not state_path.exists()

    def test_malformed_config_is_skipped(self, state_paths, caplog):
        from spellbook.core.state import migrate_config_to_state

        cfg = state_paths["config_dir"] / "spellbook.json"
        cfg.write_text("{not json")

        with caplog.at_level("WARNING"):
            result = migrate_config_to_state()

        assert result["migrated"] is False
        # File left alone for the user to fix.
        assert cfg.read_text() == "{not json"
