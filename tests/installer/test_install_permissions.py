"""Tests for installer/components/permissions.py: install_permissions().

Covers WI-0 permissions installation:
- Deep-merges spellbook-managed entries into permissions.allow/deny/ask
- Preserves user-added entries in those arrays
- Reconciles via state file: managed entries from previous run that are no
  longer in the desired set are removed
- Atomic writes via atomic_write_json
- HookResult return contract (component="permissions")
- Error wrapping mirrors install_hooks
"""

import json



# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_install_permissions_writes_managed_entries_to_empty_settings(tmp_path, monkeypatch):
    """First-run install populates permissions arrays from None settings."""
    from installer.components import permissions as perms
    from installer.components import managed_permissions_state as mps

    state_path = tmp_path / "state" / "managed_permissions.json"
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    config_dir = tmp_path / ".claude"
    config_dir.mkdir()
    settings_path = config_dir / "settings.json"

    result = perms.install_permissions(
        settings_path=settings_path,
        allow=["Bash(git status:*)", "Bash(ls:*)"],
        deny=["Bash(rm -rf /:*)"],
        ask=["Bash(curl:*)"],
        spellbook_dir=tmp_path / "spellbook",
        dry_run=False,
    )

    written = json.loads(settings_path.read_text(encoding="utf-8"))
    assert written == {
        "permissions": {
            "allow": ["Bash(git status:*)", "Bash(ls:*)"],
            "deny": ["Bash(rm -rf /:*)"],
            "ask": ["Bash(curl:*)"],
        }
    }
    assert result.component == "permissions"
    assert result.success is True
    assert result.action == "installed"


def test_install_permissions_with_none_args_is_inert(tmp_path, monkeypatch):
    """allow=None, deny=None, ask=None -> no permissions written."""
    from installer.components import permissions as perms
    from installer.components import managed_permissions_state as mps

    state_path = tmp_path / "state" / "managed_permissions.json"
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    config_dir = tmp_path / ".claude"
    config_dir.mkdir()
    settings_path = config_dir / "settings.json"

    result = perms.install_permissions(
        settings_path=settings_path,
        spellbook_dir=tmp_path / "spellbook",
        dry_run=False,
    )

    # When there's nothing to install AND no prior managed state, the file
    # need not be written at all -- but a permissions key with empty arrays
    # is also acceptable. Assert the contract: no managed entries present.
    if settings_path.exists():
        written = json.loads(settings_path.read_text(encoding="utf-8"))
        perms_section = written.get("permissions", {})
        assert perms_section.get("allow", []) == []
        assert perms_section.get("deny", []) == []
        assert perms_section.get("ask", []) == []
    assert result.component == "permissions"
    assert result.success is True


def test_install_permissions_preserves_user_added_entries(tmp_path, monkeypatch):
    """Existing user-added permissions are preserved; managed ones are added alongside."""
    from installer.components import permissions as perms
    from installer.components import managed_permissions_state as mps

    state_path = tmp_path / "state" / "managed_permissions.json"
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    config_dir = tmp_path / ".claude"
    config_dir.mkdir()
    settings_path = config_dir / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "permissions": {
                    "allow": ["Bash(my-custom:*)"],
                    "deny": ["Bash(user-blocked:*)"],
                }
            }
        ),
        encoding="utf-8",
    )

    perms.install_permissions(
        settings_path=settings_path,
        allow=["Bash(git status:*)"],
        deny=["Bash(rm -rf:*)"],
        ask=["Bash(curl:*)"],
        spellbook_dir=tmp_path / "spellbook",
        dry_run=False,
    )

    written = json.loads(settings_path.read_text(encoding="utf-8"))
    assert written == {
        "permissions": {
            "allow": ["Bash(my-custom:*)", "Bash(git status:*)"],
            "deny": ["Bash(user-blocked:*)", "Bash(rm -rf:*)"],
            "ask": ["Bash(curl:*)"],
        }
    }


# ---------------------------------------------------------------------------
# Reconciliation: stale managed entries removed
# ---------------------------------------------------------------------------


def test_install_permissions_removes_previously_managed_entries_no_longer_desired(
    tmp_path, monkeypatch
):
    """Entries that WERE managed but aren't in the new set are removed from settings.json."""
    from installer.components import permissions as perms
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
                        "allow": ["Bash(stale:*)", "Bash(git status:*)"],
                        "deny": [],
                        "ask": [],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    settings_path = config_dir / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "permissions": {
                    "allow": ["Bash(my-custom:*)", "Bash(stale:*)", "Bash(git status:*)"]
                }
            }
        ),
        encoding="utf-8",
    )

    perms.install_permissions(
        settings_path=settings_path,
        allow=["Bash(git status:*)"],  # Bash(stale:*) intentionally absent
        deny=[],
        ask=[],
        spellbook_dir=tmp_path / "spellbook",
        dry_run=False,
    )

    written = json.loads(settings_path.read_text(encoding="utf-8"))
    assert written == {
        "permissions": {
            "allow": ["Bash(my-custom:*)", "Bash(git status:*)"],
            "deny": [],
            "ask": [],
        }
    }
    new_state = json.loads(state_path.read_text(encoding="utf-8"))
    assert new_state["config_dirs"][str(config_dir)] == {
        "allow": ["Bash(git status:*)"],
        "deny": [],
        "ask": [],
    }


def test_install_permissions_does_not_remove_entries_not_in_state_file(tmp_path, monkeypatch):
    """An entry the user added that happens to match a managed-pattern is preserved
    if it's not in the state file."""
    from installer.components import permissions as perms
    from installer.components import managed_permissions_state as mps

    state_path = tmp_path / "state" / "managed_permissions.json"
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    config_dir = tmp_path / ".claude"
    config_dir.mkdir()
    settings_path = config_dir / "settings.json"
    # The user pre-existing entry "Bash(git status:*)" looks like a spellbook
    # entry but state file is empty -> we did not place it -> never remove.
    settings_path.write_text(
        json.dumps({"permissions": {"allow": ["Bash(git status:*)"]}}),
        encoding="utf-8",
    )

    perms.install_permissions(
        settings_path=settings_path,
        allow=[],
        deny=[],
        ask=[],
        spellbook_dir=tmp_path / "spellbook",
        dry_run=False,
    )

    written = json.loads(settings_path.read_text(encoding="utf-8"))
    assert written == {
        "permissions": {
            "allow": ["Bash(git status:*)"],
            "deny": [],
            "ask": [],
        }
    }


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def test_install_permissions_is_idempotent(tmp_path, monkeypatch):
    """Re-running install_permissions with the same args yields identical settings.json."""
    from installer.components import permissions as perms
    from installer.components import managed_permissions_state as mps

    state_path = tmp_path / "state" / "managed_permissions.json"
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    config_dir = tmp_path / ".claude"
    config_dir.mkdir()
    settings_path = config_dir / "settings.json"

    args = dict(
        settings_path=settings_path,
        allow=["Bash(git status:*)"],
        deny=["Bash(rm:*)"],
        ask=["Bash(curl:*)"],
        spellbook_dir=tmp_path / "spellbook",
        dry_run=False,
    )

    perms.install_permissions(**args)
    after_first = settings_path.read_text(encoding="utf-8")
    state_after_first = state_path.read_text(encoding="utf-8")

    perms.install_permissions(**args)
    after_second = settings_path.read_text(encoding="utf-8")
    state_after_second = state_path.read_text(encoding="utf-8")

    assert after_first == after_second
    assert state_after_first == state_after_second


# ---------------------------------------------------------------------------
# Mutable default fix
# ---------------------------------------------------------------------------


def test_install_permissions_uses_safe_default_for_missing_args(tmp_path, monkeypatch):
    """Repeated calls with no allow/deny/ask must not share mutable state."""
    from installer.components import permissions as perms
    from installer.components import managed_permissions_state as mps

    state_path_a = tmp_path / "a" / "state" / "managed_permissions.json"
    state_path_b = tmp_path / "b" / "state" / "managed_permissions.json"

    config_dir_a = tmp_path / "a" / ".claude"
    config_dir_a.mkdir(parents=True)
    config_dir_b = tmp_path / "b" / ".claude"
    config_dir_b.mkdir(parents=True)

    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path_a)
    perms.install_permissions(
        settings_path=config_dir_a / "settings.json",
        allow=["Bash(only-a:*)"],
        spellbook_dir=tmp_path / "spellbook",
        dry_run=False,
    )

    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path_b)
    perms.install_permissions(
        settings_path=config_dir_b / "settings.json",
        spellbook_dir=tmp_path / "spellbook",
        dry_run=False,
    )

    written_b = json.loads((config_dir_b / "settings.json").read_text(encoding="utf-8")) \
        if (config_dir_b / "settings.json").exists() else {}
    perms_b = written_b.get("permissions", {})
    # If config B inherited mutable defaults from config A, "Bash(only-a:*)"
    # would leak in; assert it does NOT.
    assert "Bash(only-a:*)" not in perms_b.get("allow", [])


# ---------------------------------------------------------------------------
# Dry run
# ---------------------------------------------------------------------------


def test_install_permissions_dry_run_makes_no_changes(tmp_path, monkeypatch):
    """dry_run=True writes nothing to settings.json or the state file."""
    from installer.components import permissions as perms
    from installer.components import managed_permissions_state as mps

    state_path = tmp_path / "state" / "managed_permissions.json"
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    config_dir = tmp_path / ".claude"
    config_dir.mkdir()
    settings_path = config_dir / "settings.json"

    result = perms.install_permissions(
        settings_path=settings_path,
        allow=["Bash(git status:*)"],
        spellbook_dir=tmp_path / "spellbook",
        dry_run=True,
    )

    assert settings_path.exists() is False
    assert state_path.exists() is False
    assert result.component == "permissions"
    assert result.success is True
    assert result.action == "installed"
    assert "dry run" in result.message


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_install_permissions_returns_failed_on_corrupt_settings(tmp_path, monkeypatch):
    """Corrupt settings.json -> HookResult(success=False)."""
    from installer.components import permissions as perms
    from installer.components import managed_permissions_state as mps

    state_path = tmp_path / "state" / "managed_permissions.json"
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    config_dir = tmp_path / ".claude"
    config_dir.mkdir()
    settings_path = config_dir / "settings.json"
    settings_path.write_text("{not json", encoding="utf-8")

    result = perms.install_permissions(
        settings_path=settings_path,
        allow=["Bash(ls:*)"],
        spellbook_dir=tmp_path / "spellbook",
        dry_run=False,
    )

    assert result.component == "permissions"
    assert result.success is False
    assert result.action == "failed"
    assert "JSON" in result.message or "decode" in result.message.lower()


def test_install_permissions_returns_failed_on_oserror(tmp_path, monkeypatch):
    """OSError from atomic_write_json -> HookResult(success=False)."""
    from installer.components import permissions as perms
    from installer.components import managed_permissions_state as mps

    state_path = tmp_path / "state" / "managed_permissions.json"
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    config_dir = tmp_path / ".claude"
    config_dir.mkdir()
    settings_path = config_dir / "settings.json"

    def boom(*args, **kwargs):
        raise OSError("disk full simulation")

    monkeypatch.setattr(perms, "atomic_write_json", boom)

    result = perms.install_permissions(
        settings_path=settings_path,
        allow=["Bash(ls:*)"],
        spellbook_dir=tmp_path / "spellbook",
        dry_run=False,
    )

    assert result.component == "permissions"
    assert result.success is False
    assert result.action == "failed"
    assert "disk full simulation" in result.message
