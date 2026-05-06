"""Tests for installer/components/managed_permissions_state.py.

Covers WI-0 state-file management:
- Schema: {"version": 1, "config_dirs": {<path>: {"allow": [...], "deny": [...], "ask": [...]}}}
- File path: ~/.local/spellbook/state/managed_permissions.json
- Atomic writes via atomic_write_json
- Lock coordination via CrossPlatformLock
- read_state, update_managed_set, reconcile semantics
"""

import json



# ---------------------------------------------------------------------------
# read_state
# ---------------------------------------------------------------------------


def test_read_state_returns_empty_schema_when_file_missing(tmp_path, monkeypatch):
    """When no state file exists, read_state returns the empty schema."""
    from installer.components import managed_permissions_state as mps

    state_dir = tmp_path / "state"
    state_path = state_dir / "managed_permissions.json"
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    result = mps.read_state()

    assert result == {"version": 1, "config_dirs": {}}


def test_read_state_loads_existing_file(tmp_path, monkeypatch):
    """read_state loads and returns the on-disk schema verbatim."""
    from installer.components import managed_permissions_state as mps

    state_dir = tmp_path / "state"
    state_dir.mkdir()
    state_path = state_dir / "managed_permissions.json"
    payload = {
        "version": 1,
        "config_dirs": {
            "/home/u/.claude": {
                "allow": ["Bash(git status:*)"],
                "deny": ["Bash(rm:*)"],
                "ask": ["Bash(curl:*)"],
            }
        },
    }
    state_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    result = mps.read_state()

    assert result == payload


def test_read_state_returns_empty_schema_on_corrupt_json(tmp_path, monkeypatch):
    """A corrupt state file is treated as empty (recovery path)."""
    from installer.components import managed_permissions_state as mps

    state_dir = tmp_path / "state"
    state_dir.mkdir()
    state_path = state_dir / "managed_permissions.json"
    state_path.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    result = mps.read_state()

    assert result == {"version": 1, "config_dirs": {}}


# ---------------------------------------------------------------------------
# update_managed_set
# ---------------------------------------------------------------------------


def test_update_managed_set_creates_entry_for_new_config_dir(tmp_path, monkeypatch):
    """Initial call for a new config_dir adds entries with no prior state."""
    from installer.components import managed_permissions_state as mps

    state_dir = tmp_path / "state"
    state_path = state_dir / "managed_permissions.json"
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    config_dir = tmp_path / "claude"
    diff = mps.update_managed_set(
        config_dir=config_dir,
        allow=["Bash(git status:*)"],
        deny=["Bash(rm:*)"],
        ask=["Bash(curl:*)"],
    )

    assert diff == {
        "added": {
            "allow": ["Bash(git status:*)"],
            "deny": ["Bash(rm:*)"],
            "ask": ["Bash(curl:*)"],
        },
        "removed": {"allow": [], "deny": [], "ask": []},
    }
    written = json.loads(state_path.read_text(encoding="utf-8"))
    assert written == {
        "version": 1,
        "config_dirs": {
            str(config_dir): {
                "allow": ["Bash(git status:*)"],
                "deny": ["Bash(rm:*)"],
                "ask": ["Bash(curl:*)"],
            }
        },
    }


def test_update_managed_set_returns_diff_against_prior_state(tmp_path, monkeypatch):
    """Subsequent calls produce add/remove diffs against the previous managed set."""
    from installer.components import managed_permissions_state as mps

    state_dir = tmp_path / "state"
    state_dir.mkdir()
    state_path = state_dir / "managed_permissions.json"
    config_dir = tmp_path / "claude"
    state_path.write_text(
        json.dumps(
            {
                "version": 1,
                "config_dirs": {
                    str(config_dir): {
                        "allow": ["Bash(git status:*)", "Bash(ls:*)"],
                        "deny": ["Bash(rm:*)"],
                        "ask": [],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    diff = mps.update_managed_set(
        config_dir=config_dir,
        allow=["Bash(git status:*)", "Bash(pwd:*)"],
        deny=["Bash(rm:*)"],
        ask=["Bash(curl:*)"],
    )

    assert diff == {
        "added": {
            "allow": ["Bash(pwd:*)"],
            "deny": [],
            "ask": ["Bash(curl:*)"],
        },
        "removed": {
            "allow": ["Bash(ls:*)"],
            "deny": [],
            "ask": [],
        },
    }
    written = json.loads(state_path.read_text(encoding="utf-8"))
    assert written == {
        "version": 1,
        "config_dirs": {
            str(config_dir): {
                "allow": ["Bash(git status:*)", "Bash(pwd:*)"],
                "deny": ["Bash(rm:*)"],
                "ask": ["Bash(curl:*)"],
            }
        },
    }


def test_update_managed_set_idempotent_returns_empty_diff(tmp_path, monkeypatch):
    """Updating with the same set as already stored produces an empty diff."""
    from installer.components import managed_permissions_state as mps

    state_dir = tmp_path / "state"
    state_dir.mkdir()
    state_path = state_dir / "managed_permissions.json"
    config_dir = tmp_path / "claude"
    state_path.write_text(
        json.dumps(
            {
                "version": 1,
                "config_dirs": {
                    str(config_dir): {
                        "allow": ["Bash(git status:*)"],
                        "deny": [],
                        "ask": [],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    diff = mps.update_managed_set(
        config_dir=config_dir,
        allow=["Bash(git status:*)"],
        deny=[],
        ask=[],
    )

    assert diff == {
        "added": {"allow": [], "deny": [], "ask": []},
        "removed": {"allow": [], "deny": [], "ask": []},
    }


def test_update_managed_set_isolates_per_config_dir(tmp_path, monkeypatch):
    """Updating one config_dir leaves other config_dirs untouched."""
    from installer.components import managed_permissions_state as mps

    state_dir = tmp_path / "state"
    state_dir.mkdir()
    state_path = state_dir / "managed_permissions.json"
    other_dir = tmp_path / "other"
    target_dir = tmp_path / "claude"
    state_path.write_text(
        json.dumps(
            {
                "version": 1,
                "config_dirs": {
                    str(other_dir): {
                        "allow": ["Bash(echo:*)"],
                        "deny": [],
                        "ask": [],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    mps.update_managed_set(
        config_dir=target_dir,
        allow=["Bash(ls:*)"],
        deny=[],
        ask=[],
    )

    written = json.loads(state_path.read_text(encoding="utf-8"))
    assert written == {
        "version": 1,
        "config_dirs": {
            str(other_dir): {
                "allow": ["Bash(echo:*)"],
                "deny": [],
                "ask": [],
            },
            str(target_dir): {
                "allow": ["Bash(ls:*)"],
                "deny": [],
                "ask": [],
            },
        },
    }


def test_update_managed_set_uses_atomic_write(tmp_path, monkeypatch):
    """update_managed_set writes via atomic_write_json (no partial writes)."""
    from installer.components import managed_permissions_state as mps

    state_dir = tmp_path / "state"
    state_path = state_dir / "managed_permissions.json"
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    captured: list[tuple] = []
    real_atomic = mps.atomic_write_json

    def spy(path, data, **kw):
        captured.append((path, data))
        real_atomic(path, data, **kw)

    monkeypatch.setattr(mps, "atomic_write_json", spy)

    config_dir = tmp_path / "claude"
    mps.update_managed_set(
        config_dir=config_dir,
        allow=["Bash(ls:*)"],
        deny=[],
        ask=[],
    )

    assert captured == [
        (
            str(state_path),
            {
                "version": 1,
                "config_dirs": {
                    str(config_dir): {
                        "allow": ["Bash(ls:*)"],
                        "deny": [],
                        "ask": [],
                    }
                },
            },
        )
    ]


# ---------------------------------------------------------------------------
# Lock semantics
# ---------------------------------------------------------------------------


def test_update_managed_set_acquires_lock(tmp_path, monkeypatch):
    """update_managed_set wraps the read-modify-write in CrossPlatformLock."""
    from installer.components import managed_permissions_state as mps

    state_dir = tmp_path / "state"
    state_path = state_dir / "managed_permissions.json"
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    lock_calls: list[tuple] = []

    class TrackingLock:
        def __init__(self, lock_path, **kwargs):
            lock_calls.append(("init", lock_path, kwargs))
            # Mirror CrossPlatformLock's directory creation so atomic_write_json
            # can write its sibling .lock file inside the same directory.
            lock_path.parent.mkdir(parents=True, exist_ok=True)

        def __enter__(self):
            lock_calls.append(("enter",))
            return self

        def __exit__(self, *exc):
            lock_calls.append(("exit",))
            return False

    monkeypatch.setattr(mps, "CrossPlatformLock", TrackingLock)

    config_dir = tmp_path / "claude"
    mps.update_managed_set(
        config_dir=config_dir,
        allow=["Bash(ls:*)"],
        deny=[],
        ask=[],
    )

    expected_lock_path = state_path.with_suffix(state_path.suffix + ".coordlock")
    assert lock_calls == [
        ("init", expected_lock_path, {"blocking": True}),
        ("enter",),
        ("exit",),
    ]


def test_update_managed_set_preserves_default_mode_field(tmp_path, monkeypatch):
    """update_managed_set must not clobber the default_mode field that
    set_managed_default_mode writes into the same per-config-dir entry.

    Regression: a previous version did ``config_dirs[key] = desired`` which
    silently dropped any sibling fields. The wired install path calls
    set_managed_default_mode first then update_managed_set, so a clobber here
    causes the uninstall path to lose track of the managed defaultMode.
    """
    import json

    from installer.components import managed_permissions_state as mps

    state_path = tmp_path / "state.json"
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    config_dir = tmp_path / ".claude"
    mps.set_managed_default_mode(config_dir, "acceptEdits")
    mps.update_managed_set(
        config_dir=config_dir,
        allow=["Bash(git status:*)"],
        deny=[],
        ask=[],
    )

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["config_dirs"][str(config_dir)] == {
        "allow": ["Bash(git status:*)"],
        "deny": [],
        "ask": [],
        "default_mode": "acceptEdits",
    }
