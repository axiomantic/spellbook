"""Tests for spellbook-managed hook deduplication.

When the installer is re-run from a different worktree, existing hook
entries managed by spellbook (identified by ``spellbook_managed: True``)
must be removed before new entries are appended, regardless of the path
baked into the existing entries. This prevents settings.json from
accumulating multiple hook entries over time.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    cfg = tmp_path / "spellbook-config"
    cfg.mkdir()
    import installer.config as config_mod
    import installer.components.hooks as hooks_mod
    import installer.components.source_link as source_link_mod
    monkeypatch.setattr(config_mod, "get_spellbook_config_dir", lambda: cfg)
    # hooks now resolve via installer.config at call time, patched above
    # source_link now resolves via installer.config at call time, patched above
    return cfg


def _stale_spellbook_hook(path: str) -> dict:
    """A hook entry that older spellbook versions wrote (no managed marker)."""
    return {"type": "command", "command": path, "timeout": 15}


def test_existing_spellbook_managed_entries_are_removed_before_merge(
    tmp_path, config_dir
):
    """Re-installing must delete any prior spellbook_managed entries even
    when their baked-in paths differ from the new ones.
    """
    from installer.components.hooks import _merge_hooks_for_phase, HOOK_DEFINITIONS

    spellbook_dir = tmp_path / "worktree-new"
    spellbook_dir.mkdir()

    # settings.json has a stale spellbook-managed entry pointing at an
    # old worktree path (entirely different from the new one).
    old_hook_cmd = (
        "/old/worktree/.venv/bin/python /old/worktree/hooks/spellbook_hook.py"
    )
    phase_entries = [
        {
            "hooks": [
                {
                    "type": "command",
                    "command": old_hook_cmd,
                    "timeout": 15,
                    "spellbook_managed": True,
                    "spellbook_hook_id": "PreToolUse",
                }
            ]
        }
    ]

    _merge_hooks_for_phase(
        phase_entries,
        HOOK_DEFINITIONS["PreToolUse"],
        spellbook_dir,
    )

    # Exactly one catch-all entry, exactly one hook, pointing at the new path,
    # with the managed marker.
    assert len(phase_entries) == 1
    entry = phase_entries[0]
    assert "matcher" not in entry
    assert len(entry["hooks"]) == 1
    hook = entry["hooks"][0]
    assert hook["spellbook_managed"] is True
    assert hook["spellbook_hook_id"] == "PreToolUse"
    assert hook["type"] == "command"
    assert hook["timeout"] == 15
    # The new command references the stable symlink path, not the worktree.
    from installer.components.source_link import get_source_link_path
    expected_cmd = (
        f"{config_dir}/daemon-venv/bin/python "
        f"{get_source_link_path()}/hooks/spellbook_hook.py"
    )
    assert hook["command"] == expected_cmd


def test_legacy_path_based_entries_still_removed(tmp_path, config_dir):
    """Older spellbook versions wrote hooks without the managed marker,
    identifying them only by path. Those legacy entries must still be
    recognized and removed.
    """
    from installer.components.hooks import _merge_hooks_for_phase, HOOK_DEFINITIONS

    spellbook_dir = tmp_path / "worktree-new"
    spellbook_dir.mkdir()

    legacy_cmd = (
        f"{spellbook_dir}/.venv/bin/python {spellbook_dir}/hooks/spellbook_hook.py"
    )
    phase_entries = [
        {"hooks": [_stale_spellbook_hook(legacy_cmd)]},
    ]

    _merge_hooks_for_phase(
        phase_entries,
        HOOK_DEFINITIONS["PreToolUse"],
        spellbook_dir,
    )

    # Legacy entry replaced by a single managed entry.
    assert len(phase_entries) == 1
    hooks = phase_entries[0]["hooks"]
    assert len(hooks) == 1
    assert hooks[0]["spellbook_managed"] is True
    assert hooks[0]["command"] != legacy_cmd  # path is different (symlink)


def test_new_entries_have_spellbook_managed_field(tmp_path, config_dir):
    """Every hook entry the installer writes carries the managed marker
    and a stable hook id so future installs can identify them
    unambiguously.
    """
    from installer.components.hooks import _merge_hooks_for_phase, HOOK_DEFINITIONS

    spellbook_dir = tmp_path / "worktree-new"
    spellbook_dir.mkdir()

    for phase, hook_defs in HOOK_DEFINITIONS.items():
        phase_entries: list = []
        _merge_hooks_for_phase(phase_entries, hook_defs, spellbook_dir)

        assert len(phase_entries) == 1, f"phase={phase}"
        hooks = phase_entries[0]["hooks"]
        assert len(hooks) == 1, f"phase={phase}"
        hook = hooks[0]
        assert hook["spellbook_managed"] is True, f"phase={phase}"
        assert hook["spellbook_hook_id"] == phase, f"phase={phase}"


def test_user_hooks_preserved_when_spellbook_entries_replaced(tmp_path, config_dir):
    """User-authored hook entries must never be removed, only spellbook
    ones. They coexist with the new managed entry.
    """
    from installer.components.hooks import _merge_hooks_for_phase, HOOK_DEFINITIONS

    spellbook_dir = tmp_path / "worktree-new"
    spellbook_dir.mkdir()

    user_hook = {"type": "command", "command": "/user/script.sh"}
    phase_entries = [
        {
            "hooks": [
                user_hook,
                {
                    "type": "command",
                    "command": "/old/path/spellbook_hook.py",
                    "spellbook_managed": True,
                    "spellbook_hook_id": "PreToolUse",
                },
            ]
        }
    ]

    _merge_hooks_for_phase(
        phase_entries,
        HOOK_DEFINITIONS["PreToolUse"],
        spellbook_dir,
    )

    hooks = phase_entries[0]["hooks"]
    assert len(hooks) == 2
    # User hook first, managed hook second (appended).
    assert hooks[0] == user_hook
    assert hooks[1]["spellbook_managed"] is True
    assert hooks[1]["spellbook_hook_id"] == "PreToolUse"
