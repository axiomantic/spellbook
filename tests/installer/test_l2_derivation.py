"""Integration tests for L2 deny derivation (WI-6b sub-phase c).

Verifies that ``installer/components/permissions.derive_managed_deny`` reads
``spellbook/gates/tiers.toml``, projects T3 records to ``settings.json`` deny
patterns, and that the resulting list flows through ``install_permissions``
into the on-disk settings file.

Acceptance criteria covered:

- T3 records project into ``settings.json`` ``permissions.deny`` per the
  cases in design §6.4.
- Re-running install is idempotent (no duplicates).
- Removing a record from ``tiers.toml`` removes it from the deny list on the
  next install.
- A missing ``tiers.toml`` does NOT crash the installer; it just produces
  an empty deny list.
- Unprojectable records (regex-class patterns, unknown tools) warn and
  are skipped without failing the install.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest


def _write_toml(path: Path, body: str) -> Path:
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def _make_spellbook_dir(tmp_path: Path, toml_body: str | None) -> Path:
    """Build a fake spellbook tree containing ``spellbook/gates/tiers.toml``."""
    sbdir = tmp_path / "spellbook_repo"
    gates = sbdir / "spellbook" / "gates"
    gates.mkdir(parents=True)
    if toml_body is not None:
        _write_toml(gates / "tiers.toml", toml_body)
    return sbdir


# ---------------------------------------------------------------------------
# derive_managed_deny — unit-level
# ---------------------------------------------------------------------------


def test_derive_managed_deny_returns_t3_projection(tmp_path):
    from installer.components.permissions import derive_managed_deny

    sbdir = _make_spellbook_dir(
        tmp_path,
        """
        [[tiers]]
        tool = "Bash"
        pattern = "git push --force"
        tier = "T3"
        description = "force-push"

        [[tiers]]
        tool = "mcp__github__delete_*"
        pattern = "*"
        tier = "T3"
        description = "github delete"

        [[tiers]]
        tool = "Edit"
        pattern = "*"
        tier = "T3"
        description = "edit denied for test"

        [[tiers]]
        tool = "Bash"
        pattern = "git status"
        tier = "T0"
        description = "ok"
        """,
    )

    deny = derive_managed_deny(sbdir)
    assert "Bash(git push --force:*)" in deny
    assert "mcp__github__delete_*" in deny
    assert "Edit" in deny
    # T0 must not contribute.
    assert not any("git status" in d for d in deny)


def test_derive_managed_deny_missing_toml_returns_empty(tmp_path):
    from installer.components.permissions import derive_managed_deny

    sbdir = _make_spellbook_dir(tmp_path, toml_body=None)
    assert derive_managed_deny(sbdir) == []


# ---------------------------------------------------------------------------
# Integration with install_permissions
# ---------------------------------------------------------------------------


def test_install_permissions_with_derived_deny_writes_to_settings_json(
    tmp_path, monkeypatch
):
    from installer.components import permissions as perms
    from installer.components import managed_permissions_state as mps

    state_path = tmp_path / "state" / "managed_permissions.json"
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    sbdir = _make_spellbook_dir(
        tmp_path,
        """
        [[tiers]]
        tool = "Bash"
        pattern = "git push --force"
        tier = "T3"
        description = "force-push"

        [[tiers]]
        tool = "mcp__github__delete_*"
        pattern = "*"
        tier = "T3"
        description = "github delete"

        [[tiers]]
        tool = "Edit"
        pattern = "*"
        tier = "T3"
        description = "edit denied"
        """,
    )
    config_dir = tmp_path / ".claude"
    config_dir.mkdir()
    settings_path = config_dir / "settings.json"

    deny_list = perms.derive_managed_deny(sbdir)
    result = perms.install_permissions(
        settings_path=settings_path,
        allow=None,
        deny=deny_list,
        ask=None,
        spellbook_dir=sbdir,
        dry_run=False,
    )

    assert result.success is True
    written = json.loads(settings_path.read_text(encoding="utf-8"))
    deny_written = set(written["permissions"]["deny"])
    assert {
        "Bash(git push --force:*)",
        "mcp__github__delete_*",
        "Edit",
    }.issubset(deny_written)


def test_l2_derivation_is_idempotent(tmp_path, monkeypatch):
    """Re-running install with the same tiers.toml does not duplicate entries."""
    from installer.components import permissions as perms
    from installer.components import managed_permissions_state as mps

    state_path = tmp_path / "state" / "managed_permissions.json"
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    sbdir = _make_spellbook_dir(
        tmp_path,
        """
        [[tiers]]
        tool = "Bash"
        pattern = "git push --force"
        tier = "T3"
        description = "force-push"
        """,
    )
    config_dir = tmp_path / ".claude"
    config_dir.mkdir()
    settings_path = config_dir / "settings.json"

    for _ in range(3):
        perms.install_permissions(
            settings_path=settings_path,
            allow=None,
            deny=perms.derive_managed_deny(sbdir),
            ask=None,
            spellbook_dir=sbdir,
            dry_run=False,
        )

    written = json.loads(settings_path.read_text(encoding="utf-8"))
    deny = written["permissions"]["deny"]
    assert deny.count("Bash(git push --force:*)") == 1, deny


def test_l2_derivation_removes_dropped_records(tmp_path, monkeypatch):
    """Dropping a T3 record from tiers.toml removes it from settings.json on re-install."""
    from installer.components import permissions as perms
    from installer.components import managed_permissions_state as mps

    state_path = tmp_path / "state" / "managed_permissions.json"
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    sbdir = _make_spellbook_dir(
        tmp_path,
        """
        [[tiers]]
        tool = "Bash"
        pattern = "git push --force"
        tier = "T3"
        description = "force-push"

        [[tiers]]
        tool = "Bash"
        pattern = "rm -rf /"
        tier = "T3"
        description = "rm root"
        """,
    )
    config_dir = tmp_path / ".claude"
    config_dir.mkdir()
    settings_path = config_dir / "settings.json"

    perms.install_permissions(
        settings_path=settings_path,
        allow=None,
        deny=perms.derive_managed_deny(sbdir),
        ask=None,
        spellbook_dir=sbdir,
        dry_run=False,
    )

    after_first = set(
        json.loads(settings_path.read_text(encoding="utf-8"))["permissions"]["deny"]
    )
    assert "Bash(rm -rf /:*)" in after_first
    assert "Bash(git push --force:*)" in after_first

    # Drop the rm-rf record.
    _write_toml(
        sbdir / "spellbook" / "gates" / "tiers.toml",
        """
        [[tiers]]
        tool = "Bash"
        pattern = "git push --force"
        tier = "T3"
        description = "force-push"
        """,
    )

    perms.install_permissions(
        settings_path=settings_path,
        allow=None,
        deny=perms.derive_managed_deny(sbdir),
        ask=None,
        spellbook_dir=sbdir,
        dry_run=False,
    )

    after_drop = set(
        json.loads(settings_path.read_text(encoding="utf-8"))["permissions"]["deny"]
    )
    assert "Bash(rm -rf /:*)" not in after_drop, (
        "dropped T3 record was not removed from settings.json deny list"
    )
    assert "Bash(git push --force:*)" in after_drop


def test_unprojectable_record_warns_does_not_fail(tmp_path, monkeypatch, caplog):
    import logging

    from installer.components import permissions as perms
    from installer.components import managed_permissions_state as mps

    state_path = tmp_path / "state" / "managed_permissions.json"
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    # Bash record with regex-class -> unprojectable.
    sbdir = _make_spellbook_dir(
        tmp_path,
        """
        [[tiers]]
        tool = "Bash"
        pattern = "rm [^a-z]+"
        tier = "T3"
        description = "regex class — unprojectable"

        [[tiers]]
        tool = "Bash"
        pattern = "git push --force"
        tier = "T3"
        description = "force-push (projectable)"
        """,
    )

    with caplog.at_level(logging.WARNING):
        deny = perms.derive_managed_deny(sbdir)

    assert "Bash(git push --force:*)" in deny
    # Unprojectable record should produce no entry but log a warning.
    assert not any("[^a-z]" in d for d in deny)
    assert any("not projectable" in m.lower() or "skip" in m.lower() for m in caplog.messages)


# ---------------------------------------------------------------------------
# claude_code installer call site
# ---------------------------------------------------------------------------


def test_claude_code_installer_uses_derived_deny(tmp_path, monkeypatch):
    """End-to-end: ClaudeCodeInstaller.install() writes T3 deny patterns to
    settings.json by calling install_permissions with derive_managed_deny output.

    Uses a fixture spellbook_dir that contains a minimal tiers.toml.
    """
    from installer.components import managed_permissions_state as mps
    from installer.platforms.claude_code import ClaudeCodeInstaller

    state_path = tmp_path / "state" / "managed_permissions.json"
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)

    sbdir = _make_spellbook_dir(
        tmp_path,
        """
        [[tiers]]
        tool = "Bash"
        pattern = "git push --force"
        tier = "T3"
        description = "force-push"

        [[tiers]]
        tool = "mcp__atlassian__delete_*"
        pattern = "*"
        tier = "T3"
        description = "atlassian delete"
        """,
    )

    # Build a minimal layout the installer needs (skills/commands/scripts dirs).
    for sub in ("skills", "commands", "scripts", "patterns", "docs", "profiles"):
        (sbdir / sub).mkdir(exist_ok=True)

    config_dir = tmp_path / ".claude"
    inst = ClaudeCodeInstaller(
        spellbook_dir=sbdir,
        config_dir=config_dir,
        dry_run=False,
        version="test",
    )
    # Skip global MCP/daemon and CLAUDE.md side-effects we don't care about here.
    monkeypatch.setattr(
        "installer.platforms.claude_code.check_claude_cli_available", lambda: False
    )
    monkeypatch.setattr(
        "installer.platforms.claude_code.generate_claude_context", lambda *_: ""
    )

    inst.install(skip_global_steps=True)

    settings_path = config_dir / "settings.json"
    assert settings_path.exists()
    written = json.loads(settings_path.read_text(encoding="utf-8"))
    deny = set(written.get("permissions", {}).get("deny", []))
    assert "Bash(git push --force:*)" in deny
    assert "mcp__atlassian__delete_*" in deny
