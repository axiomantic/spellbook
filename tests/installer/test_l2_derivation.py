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

import tripwire


_STATE_PATH_CALLS_PER_INSTALL = 5
"""Number of ``_state_file_path`` invocations per ``install_permissions`` call.

``install_permissions`` calls ``_state_file_path`` via reconcile (read_state +
lock-path) and via update_managed_set (read_state + lock-path + atomic-write).
The exact count is part of the contract this test file pins down: changes to
that internal call pattern should make these tests trip and force a deliberate
update."""


def _mock_state_path(state_path: Path, expected_calls: int):
    """Return a tripwire mock for ``_state_file_path`` configured for
    ``expected_calls`` returns.

    Tests that exercise N installs queue ``N * _STATE_PATH_CALLS_PER_INSTALL``
    returns and must call :func:`_assert_state_path_calls` after the sandbox
    closes to satisfy tripwire's per-call assertion contract.
    """
    mock = tripwire.mock(
        "installer.components.managed_permissions_state:_state_file_path"
    )
    for _ in range(expected_calls):
        mock.returns(state_path)
    return mock


def _assert_state_path_calls(mock, expected_calls: int) -> None:
    """Verify each recorded ``_state_file_path`` interaction in any order."""
    with tripwire.in_any_order():
        for _ in range(expected_calls):
            mock.assert_call()


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


def test_install_permissions_with_derived_deny_writes_to_settings_json(tmp_path):
    from installer.components import permissions as perms

    expected_state_calls = _STATE_PATH_CALLS_PER_INSTALL  # one install
    state_path = tmp_path / "state" / "managed_permissions.json"
    state_path_mock = _mock_state_path(state_path, expected_state_calls)

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

    with tripwire:
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
    _assert_state_path_calls(state_path_mock, expected_state_calls)


def test_l2_derivation_is_idempotent(tmp_path):
    """Re-running install with the same tiers.toml does not duplicate entries."""
    from installer.components import permissions as perms

    expected_state_calls = _STATE_PATH_CALLS_PER_INSTALL * 3  # three installs
    state_path = tmp_path / "state" / "managed_permissions.json"
    state_path_mock = _mock_state_path(state_path, expected_state_calls)

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

    with tripwire:
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
    _assert_state_path_calls(state_path_mock, expected_state_calls)


def test_l2_derivation_removes_dropped_records(tmp_path):
    """Dropping a T3 record from tiers.toml removes it from settings.json on re-install."""
    from installer.components import permissions as perms

    expected_state_calls = _STATE_PATH_CALLS_PER_INSTALL * 2  # two installs
    state_path = tmp_path / "state" / "managed_permissions.json"
    state_path_mock = _mock_state_path(state_path, expected_state_calls)

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

    with tripwire:
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

    with tripwire:
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
    _assert_state_path_calls(state_path_mock, expected_state_calls)


def test_unprojectable_record_warns_does_not_fail(tmp_path, caplog):
    import logging

    from installer.components import permissions as perms

    # ``derive_managed_deny`` only reads ``tiers.toml``; it never touches
    # the managed-permissions state file, so no state-path mock is needed.

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

    Per-config-dir MCP contract: the MCP registration block in
    ``ClaudeCodeInstaller.install()`` is no longer gated behind
    ``skip_global_steps``. It runs for EVERY config dir, including a second
    ``--claude-config-dir`` installed with ``skip_global_steps=True`` (see
    ``test_claude_code_registers_mcp_per_config_dir.py``). That block first
    calls ``unregister_mcp_server("spellbook-http")`` -- which internally hits
    the ``installer.components.mcp`` binding of ``check_claude_cli_available``
    -- and then calls the ``installer.platforms.claude_code`` binding of
    ``check_claude_cli_available`` for the registration guard. Both bindings
    are mocked to ``False`` here so the block short-circuits to the
    "claude CLI not available" branch without ever shelling out to
    ``claude --version`` / ``claude mcp ...``. This mirrors the mocking idiom
    in ``test_claude_code_registers_mcp_per_config_dir.py``.
    """
    # Isolate HOME / USERPROFILE so any install-time path that resolves
    # through Path.home() does not touch the operator's real config.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    from installer.platforms.claude_code import ClaudeCodeInstaller

    # ``ClaudeCodeInstaller.install(skip_global_steps=True)`` calls
    # ``_state_file_path`` 9 times and ``generate_claude_context`` once
    # (one CLAUDE.md write). The MCP block runs ungated under
    # skip_global_steps but never touches ``_state_file_path`` (that symbol
    # lives only in ``managed_permissions_state``; the MCP path uses
    # subprocess/CLAUDE_CONFIG_DIR, not the managed-permissions state file),
    # so the state-path count is unchanged at 9. ``check_claude_cli_available``
    # is hit exactly once per binding (claude_code + mcp), both mocked False.
    # These counts are intentional and part of the contract pinned by this test.
    expected_state_calls = 9
    expected_ctx_calls = 1
    expected_cli_calls = 1  # per binding
    state_path = tmp_path / "state" / "managed_permissions.json"
    state_path_mock = _mock_state_path(state_path, expected_state_calls)

    # MCP block (now ungated under skip_global_steps): mock BOTH
    # ``check_claude_cli_available`` bindings to False so the block takes the
    # "claude CLI not available" branch and emits a single skipped mcp_server
    # result without shelling out. The ``..components.mcp import
    # check_claude_cli_available`` in claude_code.py creates a SEPARATE binding
    # from the symbol defined in mcp.py: ``unregister_mcp_server`` (called
    # inside mcp.py) uses mcp's binding, the registration guard (called inside
    # claude_code.py) uses claude_code's binding. Two bindings, two mocks.
    cc_cli_mock = tripwire.mock(
        "installer.platforms.claude_code:check_claude_cli_available"
    )
    for _ in range(expected_cli_calls):
        cc_cli_mock.returns(False)
    mcp_cli_mock = tripwire.mock(
        "installer.components.mcp:check_claude_cli_available"
    )
    for _ in range(expected_cli_calls):
        mcp_cli_mock.returns(False)

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
    # Stub out the CLAUDE.md generation side-effect; we only assert deny
    # patterns reach settings.json here. The MCP block's CLI probes are
    # mocked above (cc_cli_mock / mcp_cli_mock).
    ctx_mock = tripwire.mock(
        "installer.platforms.claude_code:generate_claude_context"
    )
    for _ in range(expected_ctx_calls):
        ctx_mock.returns("")

    with tripwire:
        results = inst.install(skip_global_steps=True)

    settings_path = config_dir / "settings.json"
    assert settings_path.exists()
    written = json.loads(settings_path.read_text(encoding="utf-8"))
    deny = set(written.get("permissions", {}).get("deny", []))
    assert "Bash(git push --force:*)" in deny
    assert "mcp__atlassian__delete_*" in deny
    _assert_state_path_calls(state_path_mock, expected_state_calls)
    # ``generate_claude_context`` is called with the spellbook_dir Path; we
    # assert the recorded call was against ``sbdir`` exactly.
    with tripwire.in_any_order():
        for _ in range(expected_ctx_calls):
            ctx_mock.assert_call(args=(sbdir,))
    # MCP block CLI probes (ungated under skip_global_steps): each binding of
    # ``check_claude_cli_available`` is hit exactly once.
    with tripwire.in_any_order():
        for _ in range(expected_cli_calls):
            cc_cli_mock.assert_call(args=(), kwargs={})
        for _ in range(expected_cli_calls):
            mcp_cli_mock.assert_call(args=(), kwargs={})
    # The MCP block emitted exactly one skipped mcp_server result (CLI mocked
    # unavailable), confirming registration ran ungated for this config dir.
    mcp_results = [r for r in results if r.component == "mcp_server"]
    assert len(mcp_results) == 1, mcp_results
    assert mcp_results[0].action == "skipped"
    # On Windows, ``hooks.install_hooks`` probes for PowerShell via
    # ``shutil.which``; tripwire intercepts that call and requires it to be
    # asserted explicitly. On other platforms, no such call is made.
    import sys as _sys
    if _sys.platform == "win32":
        tripwire.subprocess.assert_which(name="powershell", returns=None)


def test_derive_managed_deny_calls_validate_tiers_toml(tmp_path):
    """A malformed [protected] block in the install-time path raises
    ValueError instead of being silently ignored until first push."""
    import pytest

    spellbook_dir = tmp_path
    (spellbook_dir / "spellbook" / "gates").mkdir(parents=True)
    tiers_path = spellbook_dir / "spellbook" / "gates" / "tiers.toml"
    tiers_path.write_text(
        '[protected]\n'
        'branches = 42\n',  # wrong type
        encoding="utf-8",
    )

    # Clear lru_cache so the malformed file is actually parsed in this test.
    from spellbook.gates.git_push import _reset_caches
    _reset_caches()

    from installer.components.permissions import derive_managed_deny
    with pytest.raises(ValueError, match=r"branches.*list"):
        derive_managed_deny(spellbook_dir)


def test_derive_l2_deny_list_after_t2_pushpath_removal():
    """Pin the shipped tiers.toml L2 projection after the catch-all
    git push T2 row was removed and the +(master|main) T3 row added."""
    from pathlib import Path

    from spellbook.gates.tiers import derive_l2_deny_list

    tiers_path = Path(__file__).resolve().parents[2] / "spellbook" / "gates" / "tiers.toml"
    deny = derive_l2_deny_list(tiers_path)

    # Catch-all is gone.
    assert "Bash(git push:*)" not in deny, deny

    # Existing T3 --force / -f rows still expand.
    for expected in (
        "Bash(git push --force origin master:*)",
        "Bash(git push --force origin main:*)",
        "Bash(git push -f origin master:*)",
        "Bash(git push -f origin main:*)",
    ):
        assert expected in deny, (expected, deny)

    # New T3 +(master|main) row expands to all four combinations
    # of (origin|upstream) x (master|main).
    for expected in (
        "Bash(git push origin +master:*)",
        "Bash(git push origin +main:*)",
        "Bash(git push upstream +master:*)",
        "Bash(git push upstream +main:*)",
    ):
        assert expected in deny, (expected, deny)
