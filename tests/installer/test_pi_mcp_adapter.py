"""Pi has no native MCP; the adapter package is what makes mcp.json load.

Pi's own ``dist/`` references neither ``mcpServers`` nor ``mcp.json``, and its
``docs/usage.md`` states it "intentionally does not include built-in MCP". The
installer nevertheless wrote ``~/.pi/agent/mcp.json`` and reported that it had
registered spellbook's MCP server. Nothing read that file. The success message
was the only artifact the operation produced.

The fix has two halves and this file locks in both:

1. ``mcp.json`` is emitted in the shape ``pi-mcp-adapter`` actually needs, not
   the bare ``{url, headers}`` a native host would accept.
2. The adapter is declared in ``settings.json``, and the reported outcome is
   conditioned on that declaration rather than on a file having been written.

No mocking is required anywhere in this file: ``PlatformInstaller`` takes
``config_dir`` as a constructor argument, so every assertion runs against real
files under ``tmp_path``. Nothing here shells out to ``pi``.
"""

import json
from pathlib import Path

import pytest

from installer.platforms.pi import (
    PI_MCP_ADAPTER_NAME,
    PI_MCP_ADAPTER_SPEC,
    PI_MCP_ADAPTER_VERSION,
    SPELLBOOK_SERVER_KEY,
    PiInstaller,
    _generate_mcp_json_section,
    _read_pi_settings,
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
        "directTools defaults to false in the adapter, which collapses all 28 "
        "spellbook tools behind one proxy tool named 'mcp'. Spellbook skills "
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


def test_emitted_config_keeps_the_bearer_header_shape():
    """The adapter accepts a raw ``headers`` map; the daemon 401s without it."""
    entry = _generate_mcp_json_section()

    assert entry["url"].endswith("/mcp")
    if "headers" in entry:
        assert entry["headers"]["Authorization"].startswith("Bearer ")


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

    Two states are explicitly untested upstream -- daemon down, and a stale
    token. The installer cannot distinguish them because it makes no request,
    so its vocabulary is confined to what it did: declare and write.
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
