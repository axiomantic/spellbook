"""Schema hardening for tiers.toml top-level allow-list."""

from pathlib import Path

import pytest


def test_top_level_unknown_key_fails_loud(tmp_path):
    """A top-level key outside {'tiers', 'protected'} must raise ValueError."""
    from spellbook.gates.tiers import load_tiers

    toml_path = tmp_path / "tiers.toml"
    toml_path.write_text(
        '[[tiers]]\n'
        'tool = "Bash"\n'
        'pattern = "ls"\n'
        'tier = "T0"\n'
        'description = "list"\n'
        '\n'
        '[bogus]\n'
        'x = 1\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"unknown top-level keys.*bogus"):
        load_tiers(toml_path)


def test_top_level_protected_key_is_allowed(tmp_path):
    """[protected] is a valid top-level section even though load_tiers
    does not parse it (load_protected_config does, separately)."""
    from spellbook.gates.tiers import load_tiers

    toml_path = tmp_path / "tiers.toml"
    toml_path.write_text(
        '[[tiers]]\n'
        'tool = "Bash"\n'
        'pattern = "ls"\n'
        'tier = "T0"\n'
        'description = "list"\n'
        '\n'
        '[protected]\n'
        'branches = ["main"]\n',
        encoding="utf-8",
    )
    # MUST NOT raise.
    records = load_tiers(toml_path)
    assert len(records) == 1
    assert records[0].pattern == "ls"


def test_top_level_only_tiers_still_loads(tmp_path):
    """Pre-existing tiers.toml shape (only [[tiers]]) must still load."""
    from spellbook.gates.tiers import load_tiers

    toml_path = tmp_path / "tiers.toml"
    toml_path.write_text(
        '[[tiers]]\n'
        'tool = "Bash"\n'
        'pattern = "ls"\n'
        'tier = "T0"\n'
        'description = "list"\n',
        encoding="utf-8",
    )
    records = load_tiers(toml_path)
    assert len(records) == 1


def test_top_level_multiple_unknown_keys_sorted_deterministically(tmp_path):
    """Unknown keys must appear in sorted order in the error message."""
    from spellbook.gates.tiers import load_tiers

    toml_path = tmp_path / "tiers.toml"
    toml_path.write_text(
        '[zzz]\n'
        'a = 1\n'
        '\n'
        '[aaa]\n'
        'b = 2\n'
        '\n'
        '[mmm]\n'
        'c = 3\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"\['aaa', 'mmm', 'zzz'\]"):
        load_tiers(toml_path)
