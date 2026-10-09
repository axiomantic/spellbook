"""Upgrade path: install over an older install removes the stale gate plugin.

Older installs deployed ``plugins/spellbook-security.ts``. OpenCode loads every
file in that directory, and the stale file crashes each prompt, so an upgrade
must sweep it, not only an uninstall.
"""

from pathlib import Path

import pytest

from installer.platforms.opencode import OpenCodeInstaller

SPELLBOOK_DIR = Path(__file__).resolve().parents[2]


@pytest.fixture
def config_dir(tmp_path):
    path = tmp_path / "opencode"
    path.mkdir()
    return path


def _plant_stale_plugin(config_dir: Path) -> Path:
    stale = config_dir / "plugins" / "spellbook-security.ts"
    stale.parent.mkdir(parents=True)
    stale.write_text("export default function stale() {}\n", encoding="utf-8")
    return stale


def _gate_results(results):
    return [r for r in results if r.component == "gate_plugin"]


def test_install_removes_stale_plugin_and_reports_it(config_dir):
    stale = _plant_stale_plugin(config_dir)

    results = OpenCodeInstaller(SPELLBOOK_DIR, config_dir, "0.1.0").install()

    assert not stale.exists()
    gate = _gate_results(results)
    assert [(r.success, r.action) for r in gate] == [(True, "removed")]


def test_dry_run_install_keeps_stale_plugin_but_reports_it(config_dir):
    stale = _plant_stale_plugin(config_dir)

    results = OpenCodeInstaller(
        SPELLBOOK_DIR, config_dir, "0.1.0", dry_run=True
    ).install()

    assert stale.is_file()
    gate = _gate_results(results)
    assert [(r.success, r.action) for r in gate] == [(True, "removed")]


def test_install_without_stale_plugin_reports_nothing(config_dir):
    results = OpenCodeInstaller(SPELLBOOK_DIR, config_dir, "0.1.0").install()

    assert _gate_results(results) == []
    assert not (config_dir / "plugins" / "spellbook-security.ts").exists()
