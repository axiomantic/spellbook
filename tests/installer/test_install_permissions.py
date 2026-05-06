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

    # Contract: with all-None args, install_permissions writes a normalised
    # permissions section with three empty arrays. The file MUST exist and
    # the result MUST be a successful 'installed' (not 'failed').
    assert result.component == "permissions"
    assert result.success is True
    assert result.action == "installed"
    assert settings_path.exists()
    written = json.loads(settings_path.read_text(encoding="utf-8"))
    assert written == {"permissions": {"allow": [], "deny": [], "ask": []}}


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


def test_install_permissions_does_not_steal_ownership_of_user_added_entry(
    tmp_path, monkeypatch
):
    """User-added entries that overlap our desired set are NOT recorded as managed.

    Regression for ownership theft (GEM-M3): if the user has ``Bash(rm:*)`` in
    ``allow`` (NOT recorded in the spellbook state file as managed), and a
    spellbook install runs with ``allow=["Bash(rm:*)"]``, the entry must:

      1. Remain in ``settings.json`` (we don't disturb a user-added entry).
      2. NOT be recorded as managed in the state file (the user owns it).

    Recording it as managed would mean the next ``uninstall`` deletes the
    user's entry -- silent ownership transfer is forbidden.
    """
    from installer.components import permissions as perms
    from installer.components import managed_permissions_state as mps

    state_path = tmp_path / "state" / "managed_permissions.json"
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    config_dir = tmp_path / ".claude"
    config_dir.mkdir()
    settings_path = config_dir / "settings.json"
    # User has Bash(rm:*) in allow already, before we ever run install.
    settings_path.write_text(
        json.dumps({"permissions": {"allow": ["Bash(rm:*)"]}}),
        encoding="utf-8",
    )

    # Spellbook also wants Bash(rm:*) in allow. Pre-fix, this would have
    # silently transferred ownership to spellbook.
    result = perms.install_permissions(
        settings_path=settings_path,
        allow=["Bash(rm:*)"],
        spellbook_dir=tmp_path / "spellbook",
        dry_run=False,
    )

    assert result.success is True

    # settings.json keeps the entry exactly once.
    written = json.loads(settings_path.read_text(encoding="utf-8"))
    assert written["permissions"]["allow"] == ["Bash(rm:*)"]

    # The state file MUST NOT list Bash(rm:*) as managed -- it is the user's
    # entry, not spellbook's.
    state = mps.read_state()
    managed_allow = (
        state.get("config_dirs", {}).get(str(config_dir), {}).get("allow", [])
    )
    assert "Bash(rm:*)" not in managed_allow, (
        f"Ownership theft regression: spellbook recorded user-owned "
        f"Bash(rm:*) as managed. State allow={managed_allow!r}."
    )


def test_install_permissions_keeps_managing_entries_already_owned(tmp_path, monkeypatch):
    """Entries spellbook already managed must STAY managed across re-install.

    The corollary to the ownership-theft fix: if we recorded ``Bash(git:*)``
    as managed in a prior install, and the user has not removed it, the next
    install with the same desired set must continue to track it as managed
    (it's still ours, even though it's already in the bucket from a prior run).
    """
    from installer.components import permissions as perms
    from installer.components import managed_permissions_state as mps

    state_path = tmp_path / "state" / "managed_permissions.json"
    state_path.parent.mkdir(parents=True)
    config_dir = tmp_path / ".claude"
    config_dir.mkdir()

    # Prior managed state: spellbook already owns Bash(git:*) in allow.
    state_path.write_text(
        json.dumps(
            {
                "version": 1,
                "config_dirs": {
                    str(config_dir): {
                        "allow": ["Bash(git:*)"],
                        "deny": [],
                        "ask": [],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    # Settings file already has Bash(git:*) (left over from prior install).
    settings_path = config_dir / "settings.json"
    settings_path.write_text(
        json.dumps({"permissions": {"allow": ["Bash(git:*)"]}}),
        encoding="utf-8",
    )

    perms.install_permissions(
        settings_path=settings_path,
        allow=["Bash(git:*)"],
        spellbook_dir=tmp_path / "spellbook",
        dry_run=False,
    )

    # We must still be tracking it.
    state = mps.read_state()
    assert state["config_dirs"][str(config_dir)]["allow"] == ["Bash(git:*)"]


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

    settings_b_path = config_dir_b / "settings.json"
    assert settings_b_path.exists(), (
        "second call must write settings.json deterministically"
    )
    written_b = json.loads(settings_b_path.read_text(encoding="utf-8"))
    # Full-state assertion (Full Assertion Principle): config B was given no
    # allow/deny/ask args, so the result MUST be a normalised permissions
    # section with three empty buckets. Any mutable-default leak from any
    # previous test or call (not just "Bash(only-a:*)") would break this.
    assert written_b == {"permissions": {"allow": [], "deny": [], "ask": []}}

    # And config A must still hold its own entry (no leak the other direction).
    written_a = json.loads((config_dir_a / "settings.json").read_text(encoding="utf-8"))
    assert written_a == {
        "permissions": {
            "allow": ["Bash(only-a:*)"],
            "deny": [],
            "ask": [],
        }
    }


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
    assert result.message == "permissions: would be installed (dry run)"


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
    assert result.message.startswith(
        f"permissions: failed to parse {settings_path.name} - JSON decode error:"
    )


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
    assert result.message == (
        f"permissions: write to {settings_path.name} failed: disk full simulation"
    )


# ---------------------------------------------------------------------------
# Cross-bucket conflict warn-and-skip (I2 / design §14)
# ---------------------------------------------------------------------------


def test_install_permissions_warns_and_skips_cross_bucket_conflict_with_user_entry(
    tmp_path, monkeypatch, caplog
):
    """User has Bash(rm:*) in allow; spellbook wants it in deny -> warn + skip.

    The §14 contract: never duplicate a permission string into two buckets.
    If the user-added entry already lives in another bucket and we did not
    place it there (state file does not list it), the spellbook addition is
    refused. The user-added entry is preserved verbatim, the spellbook copy
    is NOT added to the target bucket, and the entry is NOT recorded in the
    managed-permissions state file (we do not own it).
    """
    import logging

    from installer.components import permissions as perms
    from installer.components import managed_permissions_state as mps

    state_path = tmp_path / "state" / "managed_permissions.json"
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    config_dir = tmp_path / ".claude"
    config_dir.mkdir()
    settings_path = config_dir / "settings.json"
    # User pre-added Bash(rm:*) to allow (intentional or accidental, but
    # state file does not record it -> we do not own it).
    settings_path.write_text(
        json.dumps({"permissions": {"allow": ["Bash(rm:*)"]}}),
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING, logger="installer.components.permissions"):
        result = perms.install_permissions(
            settings_path=settings_path,
            allow=[],
            deny=["Bash(rm:*)"],  # conflicts with user's allow entry
            ask=[],
            spellbook_dir=tmp_path / "spellbook",
            dry_run=False,
        )

    # 1. settings.json: user entry preserved, deny bucket NOT mutated.
    written = json.loads(settings_path.read_text(encoding="utf-8"))
    assert written == {
        "permissions": {
            "allow": ["Bash(rm:*)"],
            "deny": [],
            "ask": [],
        }
    }

    # 2. State file does not record Bash(rm:*) in deny -- we never claimed it.
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["config_dirs"][str(config_dir)] == {
        "allow": [],
        "deny": [],
        "ask": [],
    }

    # 3. HookResult surfaces the skip in its message.
    assert result.component == "permissions"
    assert result.success is True
    assert result.action == "installed"
    assert "skipped 1 cross-bucket conflict" in result.message
    assert "'Bash(rm:*)' (allow -> deny)" in result.message

    # 4. Warning logged.
    warnings = [
        r for r in caplog.records
        if r.levelno == logging.WARNING
        and "cross-bucket conflict" in r.getMessage()
    ]
    assert len(warnings) == 1
    assert "'Bash(rm:*)'" in warnings[0].getMessage()


def test_install_permissions_does_not_warn_when_we_own_the_other_bucket_entry(
    tmp_path, monkeypatch
):
    """If state says we previously placed Bash(rm:*) in allow, moving it to
    deny is a normal reconcile -- not a §14 user conflict. No skip, no warning.
    """
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
                        "allow": ["Bash(rm:*)"],
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
        json.dumps({"permissions": {"allow": ["Bash(rm:*)"]}}),
        encoding="utf-8",
    )

    result = perms.install_permissions(
        settings_path=settings_path,
        allow=[],
        deny=["Bash(rm:*)"],
        ask=[],
        spellbook_dir=tmp_path / "spellbook",
        dry_run=False,
    )

    # Pass 1 removes Bash(rm:*) from allow (we previously managed it there);
    # pass 2 adds it to deny (no conflict because we own it).
    written = json.loads(settings_path.read_text(encoding="utf-8"))
    assert written == {
        "permissions": {
            "allow": [],
            "deny": ["Bash(rm:*)"],
            "ask": [],
        }
    }
    new_state = json.loads(state_path.read_text(encoding="utf-8"))
    assert new_state["config_dirs"][str(config_dir)] == {
        "allow": [],
        "deny": ["Bash(rm:*)"],
        "ask": [],
    }
    assert "skipped" not in result.message


# ---------------------------------------------------------------------------
# Uninstall (I3)
# ---------------------------------------------------------------------------


def test_uninstall_permissions_removes_only_managed_entries(tmp_path, monkeypatch):
    """install then uninstall removes the managed entries but preserves
    user-added ones in the same buckets."""
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

    result = perms.uninstall_permissions(
        settings_path=settings_path,
        spellbook_dir=tmp_path / "spellbook",
        dry_run=False,
    )

    assert result.component == "permissions"
    assert result.success is True
    assert result.action == "removed"

    written = json.loads(settings_path.read_text(encoding="utf-8"))
    # Only user entries remain. The 'ask' bucket had no user entries so it
    # ends up empty; we keep the permissions key because the user's other
    # buckets still hold entries.
    assert written == {
        "permissions": {
            "allow": ["Bash(my-custom:*)"],
            "deny": ["Bash(user-blocked:*)"],
            "ask": [],
        }
    }

    # State file: managed sets cleared.
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["config_dirs"][str(config_dir)] == {
        "allow": [],
        "deny": [],
        "ask": [],
    }


def test_uninstall_permissions_drops_permissions_key_when_fully_empty(
    tmp_path, monkeypatch
):
    """install on a previously-empty file then uninstall yields a settings.json
    that no longer carries an empty permissions stub."""
    from installer.components import permissions as perms
    from installer.components import managed_permissions_state as mps

    state_path = tmp_path / "state" / "managed_permissions.json"
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    config_dir = tmp_path / ".claude"
    config_dir.mkdir()
    settings_path = config_dir / "settings.json"

    perms.install_permissions(
        settings_path=settings_path,
        allow=["Bash(git status:*)"],
        spellbook_dir=tmp_path / "spellbook",
        dry_run=False,
    )

    perms.uninstall_permissions(
        settings_path=settings_path,
        spellbook_dir=tmp_path / "spellbook",
        dry_run=False,
    )

    written = json.loads(settings_path.read_text(encoding="utf-8"))
    # No permissions key at all -- a true revert to the pre-install shape.
    assert written == {}


def test_uninstall_permissions_unchanged_when_no_managed_entries(
    tmp_path, monkeypatch
):
    """Uninstall on a fresh state is a no-op."""
    from installer.components import permissions as perms
    from installer.components import managed_permissions_state as mps

    state_path = tmp_path / "state" / "managed_permissions.json"
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    config_dir = tmp_path / ".claude"
    config_dir.mkdir()
    settings_path = config_dir / "settings.json"

    result = perms.uninstall_permissions(
        settings_path=settings_path,
        spellbook_dir=tmp_path / "spellbook",
        dry_run=False,
    )

    assert result.success is True
    assert result.action == "unchanged"
    assert settings_path.exists() is False


def test_uninstall_permissions_dry_run_makes_no_changes(tmp_path, monkeypatch):
    from installer.components import permissions as perms
    from installer.components import managed_permissions_state as mps

    state_path = tmp_path / "state" / "managed_permissions.json"
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    config_dir = tmp_path / ".claude"
    config_dir.mkdir()
    settings_path = config_dir / "settings.json"

    perms.install_permissions(
        settings_path=settings_path,
        allow=["Bash(git status:*)"],
        spellbook_dir=tmp_path / "spellbook",
        dry_run=False,
    )
    before_settings = settings_path.read_text(encoding="utf-8")
    before_state = state_path.read_text(encoding="utf-8")

    result = perms.uninstall_permissions(
        settings_path=settings_path,
        spellbook_dir=tmp_path / "spellbook",
        dry_run=True,
    )

    assert result.success is True
    assert result.action == "removed"
    assert settings_path.read_text(encoding="utf-8") == before_settings
    assert state_path.read_text(encoding="utf-8") == before_state


def test_install_then_uninstall_round_trips_to_pre_install_byte_state(
    tmp_path, monkeypatch
):
    """End-to-end: install + uninstall on a settings.json that started empty
    leaves the file with no managed defaultMode and no permissions entries."""
    from installer.components import default_mode as dm
    from installer.components import permissions as perms
    from installer.components import managed_permissions_state as mps

    state_path = tmp_path / "state" / "managed_permissions.json"
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    config_dir = tmp_path / ".claude"
    config_dir.mkdir()
    settings_path = config_dir / "settings.json"

    # No file -> empty.
    dm.install_default_mode(
        settings_path=settings_path,
        mode="acceptEdits",
        spellbook_dir=tmp_path / "spellbook",
        dry_run=False,
    )
    perms.install_permissions(
        settings_path=settings_path,
        allow=["Bash(git status:*)"],
        deny=["Bash(rm -rf:*)"],
        ask=["Bash(curl:*)"],
        spellbook_dir=tmp_path / "spellbook",
        dry_run=False,
    )

    perms.uninstall_permissions(
        settings_path=settings_path,
        spellbook_dir=tmp_path / "spellbook",
        dry_run=False,
    )
    dm.uninstall_default_mode(
        settings_path=settings_path,
        spellbook_dir=tmp_path / "spellbook",
        dry_run=False,
    )

    written = json.loads(settings_path.read_text(encoding="utf-8"))
    # Pre-install was "no file"; post-uninstall is "{}". That is the closest
    # we can get to byte-equality without deleting the file (which we don't,
    # since other components may share it). All managed surface area is gone.
    assert written == {}
