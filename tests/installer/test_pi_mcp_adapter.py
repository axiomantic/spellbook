"""Pi has no native MCP; the adapter package is what makes mcp.json load.

Pi's own ``dist/`` references neither ``mcpServers`` nor ``mcp.json``, and its
``docs/usage.md`` states it "intentionally does not include built-in MCP". The
installer nevertheless wrote ``~/.pi/agent/mcp.json`` and reported that it had
registered spellbook's MCP server. Nothing read that file. The success message
was the only artifact the operation produced.

The fix has two halves and this file locks in both:

1. ``mcp.json`` is emitted in the shape ``pi-mcp-adapter`` actually needs, not
   the bare ``{url}`` a native host would accept.
2. The adapter is declared in ``settings.json``, and the reported outcome is
   conditioned on that declaration rather than on a file having been written.

No mocking is required anywhere in this file: ``PlatformInstaller`` takes
``config_dir`` as a constructor argument, so every assertion runs against real
files under ``tmp_path``. Nothing here shells out to ``pi``.
"""

import json
import os
import stat
import time
from pathlib import Path

import pytest

from installer.platforms.pi import (
    PI_MCP_ADAPTER_NAME,
    PI_MCP_ADAPTER_SPEC,
    PI_MCP_ADAPTER_VERSION,
    PI_RESTART_NOTICE,
    PI_SETTINGS_LOCK_SUFFIX,
    PI_SETTINGS_NEW_FILE_MODE,
    SPELLBOOK_SERVER_KEY,
    PiInstaller,
    _declare_pi_adapter,
    _generate_mcp_json_section,
    _pi_settings_lock,
    _read_pi_settings,
    _retract_pi_adapter,
)


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """A stand-in for ~/.pi/agent/."""
    d = tmp_path / "pi" / "agent"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def spellbook_dir(tmp_path: Path) -> Path:
    d = tmp_path / "spellbook"
    (d / "skills").mkdir(parents=True)
    (d / "commands").mkdir(parents=True)
    return d


def _installer(spellbook_dir: Path, config_dir: Path, **kw) -> PiInstaller:
    return PiInstaller(
        spellbook_dir=spellbook_dir, config_dir=config_dir, version="test", **kw
    )


def _result(results, component: str):
    matches = [r for r in results if r.component == component]
    assert len(matches) == 1, (
        f"expected exactly one {component!r} result, got "
        f"{[r.component for r in results]}"
    )
    return matches[0]


# ---------------------------------------------------------------------------
# The emitted mcp.json shape
# ---------------------------------------------------------------------------


def test_emitted_config_carries_the_adapter_only_fields():
    """``directTools`` and ``lifecycle`` are adapter settings, not MCP ones.

    A native MCP host ignores both. The adapter's global default for
    ``directTools`` is ``false``, which exposes a SINGLE proxy tool named
    ``mcp`` instead of the individual ``spellbook_*`` tools that every
    spellbook skill addresses by name.
    """
    entry = _generate_mcp_json_section()

    assert entry["directTools"] is True, (
        "directTools defaults to false in the adapter, which collapses every "
        "spellbook tool behind one proxy tool named 'mcp'. Spellbook skills "
        "reference tools by name, so they would all be unreachable."
    )
    assert entry["lifecycle"] == "eager", (
        "The adapter's lifecycle default is 'lazy'. Only 'eager' was verified "
        "to register direct tools; whether 'lazy' does so before first use is "
        "unverified, so 'eager' is emitted rather than relying on the default."
    )


def test_emitted_config_does_not_pin_protocol_version():
    """Pinning ``protocolVersion`` fails when the server does not offer it.

    The adapter's ``"legacy"`` default negotiates successfully against the
    daemon, which answers ``2024-11-05``. The daemon does not offer
    ``2026-07-28``, so a pinned value would break the handshake.
    """
    entry = _generate_mcp_json_section()

    assert "protocolVersion" not in entry, (
        "protocolVersion must stay unset so the adapter's 'legacy' default "
        "negotiates. The daemon answers 2024-11-05 and does not offer "
        "2026-07-28; pinning either value can only narrow what succeeds."
    )


def _adapter_get_server_prefix(server_name: str, mode: str) -> str:
    """Port of the adapter's ``getServerPrefix`` from ``types.ts``.

    Kept deliberately literal so a reader can diff it against the original.
    Only the modes reachable from a spellbook-emitted config are covered.
    """
    if mode == "none":
        return ""
    if mode == "mcp":
        return f"mcp__{server_name}"
    if mode == "short":
        return server_name.removesuffix("mcp").rstrip("-") or "mcp"
    return server_name  # "server", the adapter's default


def _adapter_format_tool_name(tool_name: str, server_name: str, mode: str) -> str:
    """Port of the adapter's ``formatToolName`` from ``types.ts``."""
    prefix = _adapter_get_server_prefix(server_name, mode)
    sanitized = tool_name.replace(".", "_")
    return f"{prefix}_{sanitized}" if prefix else sanitized


def test_tool_prefix_none_is_what_prevents_a_doubled_spellbook_prefix():
    """``toolPrefix`` is load-bearing, and ``directTools`` does NOT cover it.

    The adapter prefixes every direct tool name with the SERVER name. Our
    server is named ``spellbook`` and every tool it exports is already named
    ``spellbook_*``, so the adapter's default mode produces
    ``spellbook_spellbook_health_check``. Every tool name referenced by every
    spellbook skill would be wrong.

    This test runs the adapter's own prefixing rule over the name spellbook
    actually emits, so it fails with the doubled name in the message rather
    than with a bare shape mismatch.
    """
    entry = _generate_mcp_json_section()
    tool = "spellbook_health_check"

    default_mode_name = _adapter_format_tool_name(
        tool, SPELLBOOK_SERVER_KEY, "server"
    )
    assert default_mode_name == "spellbook_spellbook_health_check", (
        "Guard on the port itself: if this no longer reproduces the doubled "
        "name, _adapter_format_tool_name has drifted from the adapter's "
        "types.ts and the assertion below proves nothing."
    )

    assert entry.get("toolPrefix") == "none", (
        "toolPrefix must be 'none'. With the adapter's default ('server') the "
        f"server name is prepended to names that already start with "
        f"'spellbook_', yielding {default_mode_name!r}. directTools alone does "
        "NOT fix this -- it controls WHETHER tools are registered "
        "individually, not what they are NAMED."
    )

    configured_name = _adapter_format_tool_name(
        tool, SPELLBOOK_SERVER_KEY, entry["toolPrefix"]
    )
    assert configured_name == tool, (
        f"With the emitted toolPrefix the adapter registers {configured_name!r}; "
        f"spellbook skills address {tool!r}."
    )


def test_emitted_config_carries_a_url_and_no_auth_header():
    """The daemon authenticates on Origin and Host, not on a header.

    The entry must carry no ``headers`` map at all. Emitting one would put a
    credential in a world-readable config for an authentication scheme the
    daemon no longer runs.
    """
    entry = _generate_mcp_json_section()

    assert entry["url"].endswith("/mcp")
    assert "headers" not in entry, (
        f"the entry carries a headers map the daemon does not read: {entry!r}"
    )


# ---------------------------------------------------------------------------
# Declaring the adapter in settings.json
# ---------------------------------------------------------------------------


def test_install_declares_the_adapter_pinned_in_settings(spellbook_dir, config_dir):
    """A pinned ``npm:`` spec is skipped by ``pi update --extensions``."""
    _installer(spellbook_dir, config_dir).install()

    settings = _read_pi_settings(config_dir / "settings.json")

    assert settings["packages"] == [PI_MCP_ADAPTER_SPEC]
    assert PI_MCP_ADAPTER_SPEC == f"npm:{PI_MCP_ADAPTER_NAME}@{PI_MCP_ADAPTER_VERSION}"
    assert "@" in PI_MCP_ADAPTER_SPEC, (
        "The spec must carry an explicit version. Pi pins versioned npm specs "
        "and skips them during updates; an unversioned spec would drift to "
        "whatever is latest, which is not what was verified."
    )


def test_install_preserves_unrelated_settings_and_other_packages(
    spellbook_dir, config_dir
):
    """settings.json belongs to the user. Spellbook adds one entry to it."""
    settings_path = config_dir / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "defaultModel": "some-model",
                "theme": "dark",
                "packages": ["npm:someone-elses-package@1.0.0"],
            }
        ),
        encoding="utf-8",
    )

    _installer(spellbook_dir, config_dir).install()

    settings = _read_pi_settings(settings_path)
    assert settings["defaultModel"] == "some-model"
    assert settings["theme"] == "dark"
    assert "npm:someone-elses-package@1.0.0" in settings["packages"]
    assert PI_MCP_ADAPTER_SPEC in settings["packages"]


def test_install_replaces_a_differently_versioned_adapter_entry(
    spellbook_dir, config_dir
):
    """Identity for an npm package is its NAME, per pi's docs/packages.md.

    Two entries for the same package name would be ambiguous, so an older
    pinned version is replaced rather than appended to.
    """
    settings_path = config_dir / "settings.json"
    settings_path.write_text(
        json.dumps({"packages": [f"npm:{PI_MCP_ADAPTER_NAME}@0.0.1"]}),
        encoding="utf-8",
    )

    _installer(spellbook_dir, config_dir).install()

    packages = _read_pi_settings(settings_path)["packages"]
    adapter_entries = [p for p in packages if PI_MCP_ADAPTER_NAME in str(p)]
    assert adapter_entries == [PI_MCP_ADAPTER_SPEC]


def test_install_does_not_touch_an_object_form_adapter_entry(
    spellbook_dir, config_dir
):
    """A user who filtered the package with the object form configured it
    deliberately. Spellbook leaves that entry alone rather than flattening it
    back to a bare string and silently discarding the filters."""
    settings_path = config_dir / "settings.json"
    user_entry = {"source": f"npm:{PI_MCP_ADAPTER_NAME}@2.0.0", "skills": []}
    settings_path.write_text(json.dumps({"packages": [user_entry]}), encoding="utf-8")

    _installer(spellbook_dir, config_dir).install()

    packages = _read_pi_settings(settings_path)["packages"]
    assert packages == [user_entry]


# ---------------------------------------------------------------------------
# Honest reporting -- the point of the whole change
# ---------------------------------------------------------------------------


def test_reported_message_names_the_adapter_not_a_bare_registration(
    spellbook_dir, config_dir
):
    """The old message claimed registration that nothing could substantiate."""
    results = _installer(spellbook_dir, config_dir).install()

    mcp = _result(results, "mcp_server")
    assert mcp.success
    assert PI_MCP_ADAPTER_NAME in mcp.message, (
        "Pi cannot read mcp.json on its own. A message that claims MCP "
        "registration without naming the adapter that provides it is the "
        "silent no-op this change exists to remove."
    )


def test_reports_unregistered_when_the_adapter_cannot_be_declared(
    spellbook_dir, config_dir
):
    """settings.json is unparseable, so the declaration cannot be made.

    mcp.json may still be written -- it is harmless -- but the installer must
    NOT report MCP as registered on the strength of having written a file.
    """
    (config_dir / "settings.json").write_text("{ this is not json", encoding="utf-8")

    results = _installer(spellbook_dir, config_dir).install()

    adapter = _result(results, "mcp_adapter")
    assert not adapter.success

    mcp = _result(results, "mcp_server")
    assert not mcp.success, (
        "Without the adapter declared, nothing in pi reads mcp.json. Reporting "
        "success here is exactly the defect being fixed."
    )
    assert "not registered" in mcp.message.lower()


def test_install_never_claims_a_verified_connection(spellbook_dir, config_dir):
    """The installer does not probe the daemon and must not imply that it did.

    A daemon that is down and a daemon that is up are indistinguishable to an
    installer that makes no request, so its vocabulary is confined to what it
    did: declare and write.
    """
    results = _installer(spellbook_dir, config_dir).install()

    for component in ("mcp_adapter", "mcp_server"):
        message = _result(results, component).message.lower()
        for claim in ("connected", "verified", "reachable", "working", "available"):
            assert claim not in message, (
                f"{component} message claims {claim!r}, but the installer "
                f"never contacts the daemon: {message!r}"
            )


def test_detect_reports_mcp_unregistered_when_the_adapter_is_absent(
    spellbook_dir, config_dir
):
    """mcp.json alone is not MCP support. ``detect`` must agree with that."""
    (config_dir / "mcp.json").write_text(
        json.dumps({"mcpServers": {SPELLBOOK_SERVER_KEY: {"url": "http://x/mcp"}}}),
        encoding="utf-8",
    )

    status = _installer(spellbook_dir, config_dir).detect()

    assert status.details["mcp_registered"] is False, (
        "A spellbook entry in mcp.json with no adapter declared is the state "
        "every prior install left behind. It is not a registration."
    )
    assert status.details["mcp_adapter_declared"] is False


def test_detect_reports_mcp_registered_once_the_adapter_is_declared(
    spellbook_dir, config_dir
):
    _installer(spellbook_dir, config_dir).install()

    status = _installer(spellbook_dir, config_dir).detect()

    assert status.details["mcp_registered"] is True
    assert status.details["mcp_adapter_declared"] is True


# ---------------------------------------------------------------------------
# Uninstall
# ---------------------------------------------------------------------------


def test_uninstall_retracts_the_adapter_when_spellbook_was_its_only_reason(
    spellbook_dir, config_dir
):
    """Spellbook declared it and no other server needs it, so it is retracted."""
    _installer(spellbook_dir, config_dir).install()

    _installer(spellbook_dir, config_dir).uninstall()

    packages = _read_pi_settings(config_dir / "settings.json").get("packages", [])
    assert PI_MCP_ADAPTER_SPEC not in packages


def test_uninstall_keeps_the_adapter_when_another_mcp_server_remains(
    spellbook_dir, config_dir
):
    """The adapter is a general-purpose bridge, not a spellbook component.

    Removing it would break every other server in the user's mcp.json.
    """
    _installer(spellbook_dir, config_dir).install()
    mcp_path = config_dir / "mcp.json"
    config = json.loads(mcp_path.read_text(encoding="utf-8"))
    config["mcpServers"]["someone-else"] = {"url": "http://example/mcp"}
    mcp_path.write_text(json.dumps(config), encoding="utf-8")

    _installer(spellbook_dir, config_dir).uninstall()

    packages = _read_pi_settings(config_dir / "settings.json").get("packages", [])
    assert PI_MCP_ADAPTER_SPEC in packages, (
        "another server still needs the adapter to be loaded"
    )
    remaining = json.loads(mcp_path.read_text(encoding="utf-8"))["mcpServers"]
    assert SPELLBOOK_SERVER_KEY not in remaining
    assert "someone-else" in remaining


def test_uninstall_never_removes_an_adapter_entry_spellbook_did_not_write(
    spellbook_dir, config_dir
):
    """A user-authored object-form entry survives uninstall untouched."""
    settings_path = config_dir / "settings.json"
    user_entry = {"source": f"npm:{PI_MCP_ADAPTER_NAME}@2.0.0", "skills": []}
    settings_path.write_text(json.dumps({"packages": [user_entry]}), encoding="utf-8")

    _installer(spellbook_dir, config_dir).install()
    _installer(spellbook_dir, config_dir).uninstall()

    assert _read_pi_settings(settings_path)["packages"] == [user_entry]


def test_dry_run_writes_nothing(spellbook_dir, config_dir):
    _installer(spellbook_dir, config_dir, dry_run=True).install()

    assert not (config_dir / "settings.json").exists()
    assert not (config_dir / "mcp.json").exists()


# ---------------------------------------------------------------------------
# The adapter-entry boundary: which settings.json entries ARE the adapter
# ---------------------------------------------------------------------------


def test_install_repins_a_version_less_adapter_entry(spellbook_dir, config_dir):
    """A bare ``npm:pi-mcp-adapter`` with no version is spellbook-shaped.

    An unpinned spec is the exact drift ``PI_MCP_ADAPTER_VERSION`` exists to
    prevent: ``pi update --extensions`` skips pinned specs and moves unpinned
    ones to whatever is latest, which is not the version verified end to end.
    The entry is a bare string, which is the only shape spellbook writes, so it
    is repinned rather than left alone.
    """
    settings_path = config_dir / "settings.json"
    settings_path.write_text(
        json.dumps({"packages": [f"npm:{PI_MCP_ADAPTER_NAME}"]}), encoding="utf-8"
    )

    _installer(spellbook_dir, config_dir).install()

    packages = _read_pi_settings(settings_path)["packages"]
    assert packages == [PI_MCP_ADAPTER_SPEC], (
        "An unpinned bare-string entry must be repinned. Leaving it makes the "
        "installer report a version it did not write."
    )


def test_a_package_whose_name_merely_starts_with_the_adapter_is_not_the_adapter(
    spellbook_dir, config_dir
):
    """``npm:pi-mcp-adapter-extra`` is a DIFFERENT package.

    A prefix test without a boundary matches it, which makes ``detect`` report
    the adapter as declared while the real adapter is absent, and makes the
    installer decline to declare the one thing it is responsible for.
    """
    settings_path = config_dir / "settings.json"
    lookalike = f"npm:{PI_MCP_ADAPTER_NAME}-extra@1.0.0"
    settings_path.write_text(json.dumps({"packages": [lookalike]}), encoding="utf-8")

    _installer(spellbook_dir, config_dir).install()

    packages = _read_pi_settings(settings_path)["packages"]
    assert lookalike in packages, "the user's unrelated package must survive"
    assert PI_MCP_ADAPTER_SPEC in packages, (
        f"{lookalike!r} is not the adapter; the adapter must still be declared"
    )


def test_detect_does_not_count_a_lookalike_package_as_the_adapter(
    spellbook_dir, config_dir
):
    """``detect`` must not report a registration a lookalike name cannot provide."""
    (config_dir / "settings.json").write_text(
        json.dumps({"packages": [f"npm:{PI_MCP_ADAPTER_NAME}-extra@1.0.0"]}),
        encoding="utf-8",
    )
    (config_dir / "mcp.json").write_text(
        json.dumps({"mcpServers": {SPELLBOOK_SERVER_KEY: {"url": "http://x/mcp"}}}),
        encoding="utf-8",
    )

    status = _installer(spellbook_dir, config_dir).detect()

    assert status.details["mcp_adapter_declared"] is False
    assert status.details["mcp_registered"] is False


def test_reported_message_never_names_a_version_spellbook_did_not_write(
    spellbook_dir, config_dir
):
    """The object-form entry is left as is, so the pinned spec is NOT on disk.

    Reporting "via npm:pi-mcp-adapter@<pinned>" here states a version that the
    installer declined to write. The message must name the spec that actually
    loads mcp.json -- the user's own.
    """
    settings_path = config_dir / "settings.json"
    user_source = f"npm:{PI_MCP_ADAPTER_NAME}@2.0.0"
    settings_path.write_text(
        json.dumps({"packages": [{"source": user_source, "skills": []}]}),
        encoding="utf-8",
    )

    results = _installer(spellbook_dir, config_dir).install()

    packages = _read_pi_settings(settings_path)["packages"]
    assert packages == [{"source": user_source, "skills": []}]

    message = _result(results, "mcp_server").message
    assert PI_MCP_ADAPTER_SPEC not in message, (
        f"message names {PI_MCP_ADAPTER_SPEC!r}, but that spec was never "
        f"written to settings.json: {message!r}"
    )
    assert user_source in message, (
        f"the message must name the spec that actually loads mcp.json: {message!r}"
    )


# ---------------------------------------------------------------------------
# settings.json belongs to the user: its mode, its shape, its concurrent writer
# ---------------------------------------------------------------------------


def test_install_preserves_an_owner_only_settings_mode(spellbook_dir, config_dir):
    """An owner-only settings.json must not come back world-readable.

    ``os.replace`` swaps in the TEMPORARY file, so without an explicit chmod the
    result carries the temp file's default-umask mode -- typically 0644. A user
    who tightened settings.json to 0600 would have it widened by an install that
    only meant to append a package entry.
    """
    settings_path = config_dir / "settings.json"
    settings_path.write_text(json.dumps({"theme": "dark"}), encoding="utf-8")
    settings_path.chmod(0o600)

    _installer(spellbook_dir, config_dir).install()

    assert stat.S_IMODE(settings_path.stat().st_mode) == 0o600, (
        "the install widened the user's settings.json; every other local "
        "account can now read it"
    )
    assert PI_MCP_ADAPTER_SPEC in _read_pi_settings(settings_path)["packages"]


def test_a_settings_file_the_installer_creates_is_owner_only(
    spellbook_dir, config_dir
):
    """With no file to inherit a mode from, the restrictive default applies."""
    settings_path = config_dir / "settings.json"
    assert not settings_path.exists()

    _installer(spellbook_dir, config_dir).install()

    assert stat.S_IMODE(settings_path.stat().st_mode) == PI_SETTINGS_NEW_FILE_MODE


def test_a_non_list_packages_key_is_never_overwritten(spellbook_dir, config_dir):
    """A wrong-typed ``packages`` is the user's data, not a blank slate.

    Coercing it to ``[]`` and writing that back destroys it silently. The file
    level already raises on a non-object; the key level must not be laxer.
    """
    settings_path = config_dir / "settings.json"
    original = json.dumps({"theme": "dark", "packages": "npm:pi-mcp-adapter"})
    settings_path.write_text(original, encoding="utf-8")

    results = _installer(spellbook_dir, config_dir).install()

    assert settings_path.read_text(encoding="utf-8") == original, (
        "settings.json was rewritten; whatever 'packages' held is gone"
    )
    adapter = _result(results, "mcp_adapter")
    assert not adapter.success
    assert "packages" in adapter.message


def test_a_second_stale_adapter_entry_is_not_left_behind(spellbook_dir, config_dir):
    """Handling only the FIRST match leaves a sibling that can win.

    Pi resolves an npm package by name, so a leftover older pin is not additive
    -- it is a second answer to the same question, and the version the
    installer reports need not be the version that loads.
    """
    settings_path = config_dir / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "packages": [
                    f"npm:{PI_MCP_ADAPTER_NAME}@0.0.1",
                    "npm:someone-elses-package@1.0.0",
                    f"npm:{PI_MCP_ADAPTER_NAME}@0.0.2",
                ]
            }
        ),
        encoding="utf-8",
    )

    _installer(spellbook_dir, config_dir).install()

    packages = _read_pi_settings(settings_path)["packages"]
    assert [p for p in packages if PI_MCP_ADAPTER_NAME in str(p)] == [
        PI_MCP_ADAPTER_SPEC
    ], f"a stale adapter declaration survived: {packages!r}"
    assert "npm:someone-elses-package@1.0.0" in packages


def test_duplicate_entries_including_a_user_one_fail_loudly(
    spellbook_dir, config_dir
):
    """Which entry pi loads is ambiguous, and one of them is the user's.

    Rewriting either would guess, and reporting a version would report the
    guess. The installer says so instead.
    """
    settings_path = config_dir / "settings.json"
    user_entry = {"source": f"npm:{PI_MCP_ADAPTER_NAME}@2.0.0", "skills": []}
    packages = [f"npm:{PI_MCP_ADAPTER_NAME}@0.0.1", user_entry]
    settings_path.write_text(json.dumps({"packages": packages}), encoding="utf-8")

    results = _installer(spellbook_dir, config_dir).install()

    assert _read_pi_settings(settings_path)["packages"] == packages
    adapter = _result(results, "mcp_adapter")
    assert not adapter.success
    assert not _result(results, "mcp_server").success


def test_uninstall_removes_every_entry_spellbook_wrote(spellbook_dir, config_dir):
    """One retract, every managed entry -- the same reason install collapses them."""
    settings_path = config_dir / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "packages": [
                    f"npm:{PI_MCP_ADAPTER_NAME}@0.0.1",
                    f"npm:{PI_MCP_ADAPTER_NAME}",
                ]
            }
        ),
        encoding="utf-8",
    )

    ok, message, retracted = _retract_pi_adapter(config_dir)

    assert ok and retracted, message
    assert _read_pi_settings(settings_path)["packages"] == []


def test_the_retracted_flag_is_a_fact_not_a_word_in_the_message(
    spellbook_dir, config_dir
):
    """``action`` must come from what was removed, not from the message's text.

    Deriving it by searching the message for a substring makes a reworded
    message change the recorded outcome, silently and for no stated reason.
    """
    _installer(spellbook_dir, config_dir).install()
    results = _installer(spellbook_dir, config_dir).uninstall()

    assert _result(results, "mcp_adapter").action == "removed"

    ok, message, retracted = _retract_pi_adapter(config_dir)
    assert ok
    assert retracted is False, (
        f"nothing was removed on the second pass, yet retracted is True: {message!r}"
    )


# ---------------------------------------------------------------------------
# Pi's lock, which pi takes around every settings.json read-modify-write
# ---------------------------------------------------------------------------


def test_the_declaration_waits_for_pis_lock_instead_of_overwriting(config_dir):
    """A held lock means pi is mid read-modify-write. Writing through it loses.

    Pi's ``withLock`` reads INSIDE the lock and writes back inside the same one
    (``core/settings-manager.js``). An installer that ignores the lock has its
    entry overwritten by pi's write, which was computed from a read taken
    before ours -- after the installer already reported success.
    """
    settings_path = config_dir / "settings.json"
    settings_path.write_text(json.dumps({"theme": "dark"}), encoding="utf-8")
    lock_path = settings_path.with_name(settings_path.name + PI_SETTINGS_LOCK_SUFFIX)
    lock_path.mkdir()

    try:
        ok, message, _ = _declare_pi_adapter(config_dir)
    finally:
        lock_path.rmdir()

    assert not ok, "the installer wrote through a lock pi was holding"
    assert "lock" in message
    assert "packages" not in _read_pi_settings(settings_path)


def test_the_lock_is_the_path_proper_lockfile_uses(config_dir):
    """The lock is only pi's lock if it is at the path pi's library uses.

    proper-lockfile's ``getLockFile`` returns the target path with ``.lock``
    appended, and the lock itself is a DIRECTORY, created with mkdir. A lock at
    any other path, or of any other kind, contends with nothing.
    """
    settings_path = config_dir / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")

    with _pi_settings_lock(settings_path):
        held = config_dir / "settings.json.lock"
        assert held.is_dir(), "pi's lock is a directory at <file>.lock"

    assert not held.exists(), "the lock must be released, or pi blocks forever"


def test_a_stale_lock_does_not_block_the_install_forever(spellbook_dir, config_dir):
    """proper-lockfile treats a lock older than its staleness window as dead."""
    settings_path = config_dir / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    lock_path = settings_path.with_name(settings_path.name + PI_SETTINGS_LOCK_SUFFIX)
    lock_path.mkdir()
    ancient = time.time() - 3600
    os.utime(lock_path, (ancient, ancient))

    ok, message, _ = _declare_pi_adapter(config_dir)

    assert ok, message
    assert PI_MCP_ADAPTER_SPEC in _read_pi_settings(settings_path)["packages"]


# ---------------------------------------------------------------------------
# What the dry run says it would do, and what the user is told to do next
# ---------------------------------------------------------------------------


def test_dry_run_does_not_claim_a_write_it_would_not_perform(
    spellbook_dir, config_dir
):
    """The entry is already correct, so a real run writes nothing.

    Returning "would declare ..." before reading the file announces a write for
    the one case that performs none.
    """
    _installer(spellbook_dir, config_dir).install()

    results = _installer(spellbook_dir, config_dir, dry_run=True).install()

    message = _result(results, "mcp_adapter").message
    assert "would declare" not in message, (
        f"the dry run announces a write that would not happen: {message!r}"
    )
    assert "already declared" in message


def test_dry_run_reports_leaving_a_user_entry_alone(spellbook_dir, config_dir):
    """A user's object-form entry is left as is, dry run or not."""
    settings_path = config_dir / "settings.json"
    settings_path.write_text(
        json.dumps(
            {"packages": [{"source": f"npm:{PI_MCP_ADAPTER_NAME}@2.0.0", "skills": []}]}
        ),
        encoding="utf-8",
    )

    results = _installer(spellbook_dir, config_dir, dry_run=True).install()

    message = _result(results, "mcp_adapter").message
    assert "would declare" not in message
    assert "left as is" in message


def test_dry_run_still_announces_a_write_it_would_perform(spellbook_dir, config_dir):
    """Reading first must not silence the case that does write."""
    results = _installer(spellbook_dir, config_dir, dry_run=True).install()

    assert "would declare" in _result(results, "mcp_adapter").message


def test_install_tells_the_user_that_pi_must_be_restarted(spellbook_dir, config_dir):
    """The tools do not exist until pi restarts, and nothing else says so.

    The adapter connects a ``directTools`` server during ``session_start`` when
    it has no cache entry for it and then reports, in its own ``init.ts``, that
    the tools "will be available after restart". Pi separately installs a
    declared-but-missing npm package on its next start.
    """
    results = _installer(spellbook_dir, config_dir).install()

    assert PI_RESTART_NOTICE in _result(results, "mcp_server").message
