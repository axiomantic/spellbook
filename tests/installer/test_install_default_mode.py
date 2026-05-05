"""Tests for installer/components/default_mode.py: install_default_mode().

Covers WI-0 default mode installation:
- Idempotent: re-running produces no diff in settings.json
- Atomic write via atomic_write_json
- HookResult return contract (component="default_mode")
- State-file tracking: managed defaultMode value is recorded per config_dir
- Conflict handling: user-set defaultMode that's NOT in state file is preserved
  with a warning
- Error wrapping: ValueError, json.JSONDecodeError, OSError -> HookResult(success=False)
"""

import json



# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_install_default_mode_writes_mode_to_empty_settings(tmp_path, monkeypatch):
    """install_default_mode writes defaultMode into a missing settings.json."""
    from installer.components import default_mode as dm
    from installer.components import managed_permissions_state as mps

    state_path = tmp_path / "state" / "managed_permissions.json"
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    config_dir = tmp_path / ".claude"
    config_dir.mkdir()
    settings_path = config_dir / "settings.json"

    result = dm.install_default_mode(
        settings_path=settings_path,
        mode="acceptEdits",
        spellbook_dir=tmp_path / "spellbook",
        dry_run=False,
    )

    assert result.component == "default_mode"
    assert result.success is True
    assert result.action == "installed"
    written = json.loads(settings_path.read_text(encoding="utf-8"))
    assert written == {"defaultMode": "acceptEdits"}


def test_install_default_mode_preserves_other_settings_keys(tmp_path, monkeypatch):
    """install_default_mode only touches defaultMode; other keys are untouched."""
    from installer.components import default_mode as dm
    from installer.components import managed_permissions_state as mps

    state_path = tmp_path / "state" / "managed_permissions.json"
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    config_dir = tmp_path / ".claude"
    config_dir.mkdir()
    settings_path = config_dir / "settings.json"
    settings_path.write_text(
        json.dumps({"hooks": {"PreToolUse": []}, "model": "claude-sonnet-4"}),
        encoding="utf-8",
    )

    dm.install_default_mode(
        settings_path=settings_path,
        mode="acceptEdits",
        spellbook_dir=tmp_path / "spellbook",
        dry_run=False,
    )

    written = json.loads(settings_path.read_text(encoding="utf-8"))
    assert written == {
        "hooks": {"PreToolUse": []},
        "model": "claude-sonnet-4",
        "defaultMode": "acceptEdits",
    }


def test_install_default_mode_records_managed_value_in_state_file(tmp_path, monkeypatch):
    """The installed mode is recorded in the managed-permissions state file."""
    from installer.components import default_mode as dm
    from installer.components import managed_permissions_state as mps

    state_path = tmp_path / "state" / "managed_permissions.json"
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    config_dir = tmp_path / ".claude"
    config_dir.mkdir()
    settings_path = config_dir / "settings.json"

    dm.install_default_mode(
        settings_path=settings_path,
        mode="acceptEdits",
        spellbook_dir=tmp_path / "spellbook",
        dry_run=False,
    )

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state == {
        "version": 1,
        "config_dirs": {
            str(config_dir): {
                "allow": [],
                "deny": [],
                "ask": [],
                "default_mode": "acceptEdits",
            }
        },
    }


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def test_install_default_mode_is_idempotent(tmp_path, monkeypatch):
    """Running install_default_mode twice produces unchanged settings.json."""
    from installer.components import default_mode as dm
    from installer.components import managed_permissions_state as mps

    state_path = tmp_path / "state" / "managed_permissions.json"
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    config_dir = tmp_path / ".claude"
    config_dir.mkdir()
    settings_path = config_dir / "settings.json"

    dm.install_default_mode(
        settings_path=settings_path,
        mode="acceptEdits",
        spellbook_dir=tmp_path / "spellbook",
        dry_run=False,
    )
    after_first = settings_path.read_text(encoding="utf-8")

    result = dm.install_default_mode(
        settings_path=settings_path,
        mode="acceptEdits",
        spellbook_dir=tmp_path / "spellbook",
        dry_run=False,
    )
    after_second = settings_path.read_text(encoding="utf-8")

    assert after_first == after_second
    assert result.action == "unchanged"
    assert result.success is True


# ---------------------------------------------------------------------------
# Conflict handling
# ---------------------------------------------------------------------------


def test_install_default_mode_preserves_user_set_mode_not_in_state(tmp_path, monkeypatch):
    """User manually set defaultMode AND it is not in our state -> leave alone, warn."""
    from installer.components import default_mode as dm
    from installer.components import managed_permissions_state as mps

    state_path = tmp_path / "state" / "managed_permissions.json"
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    config_dir = tmp_path / ".claude"
    config_dir.mkdir()
    settings_path = config_dir / "settings.json"
    settings_path.write_text(
        json.dumps({"defaultMode": "default"}),
        encoding="utf-8",
    )

    result = dm.install_default_mode(
        settings_path=settings_path,
        mode="acceptEdits",
        spellbook_dir=tmp_path / "spellbook",
        dry_run=False,
    )

    written = json.loads(settings_path.read_text(encoding="utf-8"))
    assert written == {"defaultMode": "default"}
    assert result.component == "default_mode"
    assert result.success is True
    assert result.action == "skipped"
    assert "user-set defaultMode" in result.message


def test_install_default_mode_overwrites_managed_value(tmp_path, monkeypatch):
    """If state file says we own the current mode, install overwrites it."""
    from installer.components import default_mode as dm
    from installer.components import managed_permissions_state as mps

    state_path = tmp_path / "state" / "managed_permissions.json"
    state_path.parent.mkdir(parents=True)
    config_dir = tmp_path / ".claude"
    config_dir.mkdir()
    state_path.write_text(
        json.dumps(
            {
                "version": 1,
                "config_dirs": {
                    str(config_dir): {
                        "allow": [],
                        "deny": [],
                        "ask": [],
                        "default_mode": "plan",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    settings_path = config_dir / "settings.json"
    settings_path.write_text(json.dumps({"defaultMode": "plan"}), encoding="utf-8")

    result = dm.install_default_mode(
        settings_path=settings_path,
        mode="acceptEdits",
        spellbook_dir=tmp_path / "spellbook",
        dry_run=False,
    )

    written = json.loads(settings_path.read_text(encoding="utf-8"))
    assert written == {"defaultMode": "acceptEdits"}
    assert result.action == "installed"
    assert result.success is True


# ---------------------------------------------------------------------------
# Dry run
# ---------------------------------------------------------------------------


def test_install_default_mode_dry_run_makes_no_changes(tmp_path, monkeypatch):
    """dry_run=True writes nothing to settings.json or the state file."""
    from installer.components import default_mode as dm
    from installer.components import managed_permissions_state as mps

    state_path = tmp_path / "state" / "managed_permissions.json"
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    config_dir = tmp_path / ".claude"
    config_dir.mkdir()
    settings_path = config_dir / "settings.json"

    result = dm.install_default_mode(
        settings_path=settings_path,
        mode="acceptEdits",
        spellbook_dir=tmp_path / "spellbook",
        dry_run=True,
    )

    assert settings_path.exists() is False
    assert state_path.exists() is False
    assert result.component == "default_mode"
    assert result.success is True
    assert result.action == "installed"
    assert "dry run" in result.message


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_install_default_mode_returns_failed_result_on_corrupt_settings(tmp_path, monkeypatch):
    """Corrupt settings.json -> HookResult(success=False, action='failed')."""
    from installer.components import default_mode as dm
    from installer.components import managed_permissions_state as mps

    state_path = tmp_path / "state" / "managed_permissions.json"
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    config_dir = tmp_path / ".claude"
    config_dir.mkdir()
    settings_path = config_dir / "settings.json"
    settings_path.write_text("{not valid json", encoding="utf-8")

    result = dm.install_default_mode(
        settings_path=settings_path,
        mode="acceptEdits",
        spellbook_dir=tmp_path / "spellbook",
        dry_run=False,
    )

    assert result.component == "default_mode"
    assert result.success is False
    assert result.action == "failed"
    assert "JSON" in result.message or "decode" in result.message.lower()


def test_install_default_mode_returns_failed_result_on_oserror(tmp_path, monkeypatch):
    """An OSError during the write -> HookResult(success=False)."""
    from installer.components import default_mode as dm
    from installer.components import managed_permissions_state as mps

    state_path = tmp_path / "state" / "managed_permissions.json"
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    config_dir = tmp_path / ".claude"
    config_dir.mkdir()
    settings_path = config_dir / "settings.json"

    def boom(*args, **kwargs):
        raise OSError("disk full simulation")

    monkeypatch.setattr(dm, "atomic_write_json", boom)

    result = dm.install_default_mode(
        settings_path=settings_path,
        mode="acceptEdits",
        spellbook_dir=tmp_path / "spellbook",
        dry_run=False,
    )

    assert result.component == "default_mode"
    assert result.success is False
    assert result.action == "failed"
    assert "disk full simulation" in result.message
