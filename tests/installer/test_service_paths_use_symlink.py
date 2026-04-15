"""Tests: launchd plist and systemd unit must reference the stable source
symlink (``$SPELLBOOK_CONFIG_DIR/source``) for WorkingDirectory and the
``SPELLBOOK_DIR`` environment variable -- never the underlying worktree.

This lets the user re-install from a different worktree without
regenerating the service file: re-pointing the symlink is enough.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def fake_paths(tmp_path, monkeypatch):
    """Redirect config/source lookups to a sandboxed tmp layout."""
    cfg = tmp_path / "spellbook-config"
    cfg.mkdir()
    src = tmp_path / "worktree"
    src.mkdir()
    (src / "pyproject.toml").write_text("[project]\nname='spellbook'\n")
    # Create the stable-source symlink (what the installer does first).
    (cfg / "source").symlink_to(src.resolve())

    # Point installer.config + source_link at the sandbox.
    import installer.config as config_mod
    import installer.components.source_link as source_link_mod
    monkeypatch.setattr(config_mod, "get_spellbook_config_dir", lambda: cfg)
    monkeypatch.setattr(source_link_mod, "get_spellbook_config_dir", lambda: cfg)

    # Point spellbook.core.config.get_spellbook_dir at the raw worktree.
    import spellbook.core.config as core_cfg
    monkeypatch.setattr(core_cfg, "get_spellbook_dir", lambda: src)

    # Service module also needs its imported reference rebound.
    import spellbook.daemon.service as service_mod
    monkeypatch.setattr(service_mod, "get_spellbook_dir", lambda: src)

    # Stub out helpers unrelated to the path we are testing.
    monkeypatch.setattr(service_mod, "get_log_file", lambda: Path("/tmp/sb.log"))
    monkeypatch.setattr(service_mod, "get_err_log_file", lambda: Path("/tmp/sb.err.log"))
    monkeypatch.setattr(service_mod, "get_port", lambda: 8765)
    monkeypatch.setattr(service_mod, "get_host", lambda: "127.0.0.1")
    monkeypatch.setattr(service_mod, "_get_darwin_daemon_path", lambda: "/usr/bin:/bin")
    monkeypatch.setattr(service_mod, "_get_linux_daemon_path", lambda: "/usr/bin:/bin")
    monkeypatch.setattr(
        service_mod,
        "get_daemon_python",
        lambda: Path("/nonexistent/daemon-venv/bin/python"),
    )

    return {"cfg": cfg, "src": src, "symlink": cfg / "source"}


def test_launchd_plist_uses_symlink_path(fake_paths):
    from spellbook.daemon.service import _generate_launchd_plist

    plist = _generate_launchd_plist()

    symlink = str(fake_paths["symlink"])
    src = str(fake_paths["src"])

    # Both WorkingDirectory and the SPELLBOOK_DIR env var must use the symlink.
    assert f"<key>WorkingDirectory</key>\n    <string>{symlink}</string>" in plist
    assert f"<key>SPELLBOOK_DIR</key>\n        <string>{symlink}</string>" in plist
    # The raw worktree path must NOT appear anywhere.
    assert src not in plist


def test_systemd_unit_uses_symlink_path(fake_paths):
    from spellbook.daemon.service import _generate_systemd_service

    unit = _generate_systemd_service()

    symlink = str(fake_paths["symlink"])
    src = str(fake_paths["src"])

    assert f"WorkingDirectory={symlink}" in unit
    assert f"Environment=SPELLBOOK_DIR={symlink}" in unit
    assert src not in unit
