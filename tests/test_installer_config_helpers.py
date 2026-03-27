"""Tests for config_is_explicitly_set and get_unset_config_keys in spellbook/core/config.py."""

import json

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_config(path, data):
    """Write a JSON config file at the given path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# config_is_explicitly_set
# ---------------------------------------------------------------------------


class TestConfigIsExplicitlySet:
    def test_key_present(self, tmp_path, monkeypatch):
        """Returns True when the key exists in the flat JSON file."""
        from spellbook.core.compat import get_config_dir

        config_dir = tmp_path / "spellbook_cfg"
        config_dir.mkdir()
        _write_config(config_dir / "spellbook.json", {"security.spotlighting.enabled": True})

        monkeypatch.setattr(
            "spellbook.core.config.get_config_dir", lambda: config_dir
        )

        from spellbook.core.config import config_is_explicitly_set

        assert config_is_explicitly_set("security.spotlighting.enabled") is True

    def test_key_absent(self, tmp_path, monkeypatch):
        """Returns False when the key is not in the file."""
        config_dir = tmp_path / "spellbook_cfg"
        config_dir.mkdir()
        _write_config(config_dir / "spellbook.json", {"other.key": "value"})

        monkeypatch.setattr(
            "spellbook.core.config.get_config_dir", lambda: config_dir
        )

        from spellbook.core.config import config_is_explicitly_set

        assert config_is_explicitly_set("security.spotlighting.enabled") is False

    def test_file_missing(self, tmp_path, monkeypatch):
        """Returns False when spellbook.json does not exist."""
        config_dir = tmp_path / "spellbook_cfg"
        config_dir.mkdir()
        # No spellbook.json written

        monkeypatch.setattr(
            "spellbook.core.config.get_config_dir", lambda: config_dir
        )

        from spellbook.core.config import config_is_explicitly_set

        assert config_is_explicitly_set("security.spotlighting.enabled") is False

    def test_invalid_json(self, tmp_path, monkeypatch):
        """Returns False when spellbook.json contains malformed JSON."""
        config_dir = tmp_path / "spellbook_cfg"
        config_dir.mkdir()
        (config_dir / "spellbook.json").write_text("{not valid json}", encoding="utf-8")

        monkeypatch.setattr(
            "spellbook.core.config.get_config_dir", lambda: config_dir
        )

        from spellbook.core.config import config_is_explicitly_set

        assert config_is_explicitly_set("security.spotlighting.enabled") is False

    def test_nested_key_not_found(self, tmp_path, monkeypatch):
        """Returns False for a top-level key that is absent, even if a related dotted key exists.

        Config storage is flat: "security.spotlighting.enabled" is stored as a literal
        string key, not as a nested dict. Looking up "security" returns False because
        there is no literal key named "security" in the file.
        """
        config_dir = tmp_path / "spellbook_cfg"
        config_dir.mkdir()
        _write_config(
            config_dir / "spellbook.json",
            {"security.spotlighting.enabled": True},
        )

        monkeypatch.setattr(
            "spellbook.core.config.get_config_dir", lambda: config_dir
        )

        from spellbook.core.config import config_is_explicitly_set

        assert config_is_explicitly_set("security") is False


# ---------------------------------------------------------------------------
# get_unset_config_keys
# ---------------------------------------------------------------------------


class TestGetUnsetConfigKeys:
    def test_all_unset(self, tmp_path, monkeypatch):
        """Returns all keys when none are set in the config file."""
        config_dir = tmp_path / "spellbook_cfg"
        config_dir.mkdir()
        # Empty config file -- no keys set
        _write_config(config_dir / "spellbook.json", {})

        monkeypatch.setattr(
            "spellbook.core.config.get_config_dir", lambda: config_dir
        )

        from spellbook.core.config import get_unset_config_keys

        keys = ["alpha", "beta", "gamma"]
        result = get_unset_config_keys(keys)
        assert result == keys

    def test_some_set(self, tmp_path, monkeypatch):
        """Returns only the unset keys, preserving input order."""
        config_dir = tmp_path / "spellbook_cfg"
        config_dir.mkdir()
        _write_config(config_dir / "spellbook.json", {"alpha": True, "gamma": False})

        monkeypatch.setattr(
            "spellbook.core.config.get_config_dir", lambda: config_dir
        )

        from spellbook.core.config import get_unset_config_keys

        keys = ["alpha", "beta", "gamma"]
        result = get_unset_config_keys(keys)
        assert result == ["beta"]

    def test_all_set(self, tmp_path, monkeypatch):
        """Returns an empty list when all keys are explicitly set."""
        config_dir = tmp_path / "spellbook_cfg"
        config_dir.mkdir()
        _write_config(
            config_dir / "spellbook.json",
            {"alpha": True, "beta": "value", "gamma": 0},
        )

        monkeypatch.setattr(
            "spellbook.core.config.get_config_dir", lambda: config_dir
        )

        from spellbook.core.config import get_unset_config_keys

        keys = ["alpha", "beta", "gamma"]
        result = get_unset_config_keys(keys)
        assert result == []
