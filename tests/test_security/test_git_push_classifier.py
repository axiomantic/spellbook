"""Tests for spellbook.gates.git_push — config loader (Task 2).

The autouse `_reset_git_push_caches` fixture is supplied by
tests/test_security/conftest.py (see Task 2 Step 0a). Do NOT
re-declare it here.
"""

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# load_protected_config — defaults
# ---------------------------------------------------------------------------


def test_defaults_when_no_protected_section(tmp_path, monkeypatch):
    monkeypatch.delenv("SPELLBOOK_PROTECTED_BRANCHES", raising=False)
    monkeypatch.delenv("SPELLBOOK_PROTECTED_REMOTES", raising=False)
    from spellbook.gates.git_push import load_protected_config

    toml_path = tmp_path / "tiers.toml"
    toml_path.write_text(
        '[[tiers]]\n'
        'tool = "Bash"\n'
        'pattern = "ls"\n'
        'tier = "T0"\n'
        'description = "x"\n',
        encoding="utf-8",
    )
    cfg = load_protected_config(toml_path)
    assert cfg.branches == ("master", "main")
    assert cfg.remotes == frozenset({"origin", "upstream"})


def test_toml_protected_section_overrides_defaults(tmp_path, monkeypatch):
    monkeypatch.delenv("SPELLBOOK_PROTECTED_BRANCHES", raising=False)
    monkeypatch.delenv("SPELLBOOK_PROTECTED_REMOTES", raising=False)
    from spellbook.gates.git_push import load_protected_config

    toml_path = tmp_path / "tiers.toml"
    toml_path.write_text(
        '[protected]\n'
        'branches = ["staging", "production"]\n'
        'remotes = ["origin"]\n',
        encoding="utf-8",
    )
    cfg = load_protected_config(toml_path)
    assert cfg.branches == ("staging", "production")
    assert cfg.remotes == frozenset({"origin"})


# ---------------------------------------------------------------------------
# env-var overlay
# ---------------------------------------------------------------------------


def test_env_var_overrides_branches(tmp_path, monkeypatch):
    monkeypatch.setenv("SPELLBOOK_PROTECTED_BRANCHES", "staging,production")
    from spellbook.gates.git_push import load_protected_config

    toml_path = tmp_path / "tiers.toml"
    toml_path.write_text("", encoding="utf-8")
    cfg = load_protected_config(toml_path)
    assert cfg.branches == ("staging", "production")


def test_env_var_overrides_remotes_independently(tmp_path, monkeypatch):
    monkeypatch.delenv("SPELLBOOK_PROTECTED_BRANCHES", raising=False)
    monkeypatch.setenv("SPELLBOOK_PROTECTED_REMOTES", "fork")
    from spellbook.gates.git_push import load_protected_config

    toml_path = tmp_path / "tiers.toml"
    toml_path.write_text("", encoding="utf-8")
    cfg = load_protected_config(toml_path)
    assert cfg.branches == ("master", "main")  # TOML default unchanged
    assert cfg.remotes == frozenset({"fork"})


def test_env_var_empty_string_falls_back_to_toml(tmp_path, monkeypatch):
    monkeypatch.setenv("SPELLBOOK_PROTECTED_BRANCHES", "")
    from spellbook.gates.git_push import load_protected_config

    toml_path = tmp_path / "tiers.toml"
    toml_path.write_text(
        '[protected]\nbranches = ["x"]\n',
        encoding="utf-8",
    )
    cfg = load_protected_config(toml_path)
    assert cfg.branches == ("x",)


def test_env_var_whitespace_elements_dropped(tmp_path, monkeypatch):
    monkeypatch.setenv("SPELLBOOK_PROTECTED_BRANCHES", " main , , master ")
    from spellbook.gates.git_push import load_protected_config

    toml_path = tmp_path / "tiers.toml"
    toml_path.write_text("", encoding="utf-8")
    cfg = load_protected_config(toml_path)
    assert cfg.branches == ("main", "master")


# ---------------------------------------------------------------------------
# __disable__ sentinel
# ---------------------------------------------------------------------------


def test_disable_sentinel_branches(tmp_path, monkeypatch):
    monkeypatch.setenv("SPELLBOOK_PROTECTED_BRANCHES", "__disable__")
    from spellbook.gates.git_push import load_protected_config

    toml_path = tmp_path / "tiers.toml"
    toml_path.write_text("", encoding="utf-8")
    cfg = load_protected_config(toml_path)
    assert cfg.branches == ()  # empty tuple means "no protection"


def test_disable_sentinel_remotes(tmp_path, monkeypatch):
    monkeypatch.setenv("SPELLBOOK_PROTECTED_REMOTES", "__disable__")
    from spellbook.gates.git_push import load_protected_config

    toml_path = tmp_path / "tiers.toml"
    toml_path.write_text("", encoding="utf-8")
    cfg = load_protected_config(toml_path)
    assert cfg.remotes == frozenset()


def test_disable_sentinel_mixed_is_error(tmp_path, monkeypatch):
    monkeypatch.setenv("SPELLBOOK_PROTECTED_BRANCHES", "main,__disable__")
    from spellbook.gates.git_push import load_protected_config

    toml_path = tmp_path / "tiers.toml"
    toml_path.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="__disable__ must be alone"):
        load_protected_config(toml_path)


# ---------------------------------------------------------------------------
# schema hardening
# ---------------------------------------------------------------------------


def test_protected_nested_unknown_key_fails_loud(tmp_path, monkeypatch):
    monkeypatch.delenv("SPELLBOOK_PROTECTED_BRANCHES", raising=False)
    from spellbook.gates.git_push import load_protected_config

    toml_path = tmp_path / "tiers.toml"
    toml_path.write_text(
        '[protected]\nbranches = ["main"]\ntypo_key = "oops"\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"unknown keys.*typo_key"):
        load_protected_config(toml_path)


def test_protected_branches_wrong_type_fails_loud(tmp_path, monkeypatch):
    monkeypatch.delenv("SPELLBOOK_PROTECTED_BRANCHES", raising=False)
    from spellbook.gates.git_push import load_protected_config

    toml_path = tmp_path / "tiers.toml"
    toml_path.write_text(
        '[protected]\nbranches = "main"\n',  # string, not list
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"branches.*list"):
        load_protected_config(toml_path)


def test_protected_remotes_wrong_type_fails_loud(tmp_path, monkeypatch):
    monkeypatch.delenv("SPELLBOOK_PROTECTED_REMOTES", raising=False)
    from spellbook.gates.git_push import load_protected_config

    toml_path = tmp_path / "tiers.toml"
    toml_path.write_text(
        '[protected]\nremotes = "origin"\n',  # string, not list
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"remotes.*list"):
        load_protected_config(toml_path)


def test_protected_non_dict_fails_loud(tmp_path, monkeypatch):
    """A top-level scalar `protected` value (instead of a table) must fail loud."""
    monkeypatch.delenv("SPELLBOOK_PROTECTED_BRANCHES", raising=False)
    monkeypatch.delenv("SPELLBOOK_PROTECTED_REMOTES", raising=False)
    from spellbook.gates.git_push import load_protected_config

    toml_path = tmp_path / "tiers.toml"
    # `protected = "x"` makes the top-level value a string, not a table.
    toml_path.write_text('protected = "x"\n', encoding="utf-8")
    with pytest.raises(ValueError, match=r"\[protected\] must be a table"):
        load_protected_config(toml_path)
