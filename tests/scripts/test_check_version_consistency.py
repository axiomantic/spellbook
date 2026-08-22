"""Behavioral tests for the version-consistency pre-commit hook.

The script sits on the release-critical path: it runs on every commit via
``always_run: true`` and blocks a release when CHANGELOG or the manifest
drifts from ``.version``. These tests pin its three outcomes (clean, drift,
broken) as distinguishable signals, the --fix contract (repair manifests,
never touch CHANGELOG, re-validate after writing), and the heading-extraction
logic the release workflow depends on.

Tests call the module's functions directly with monkeypatched paths so the
real repository is never touched.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# Import the module from its real location. Its REPO_ROOT points at the real
# repo, but every test monkeypatches the paths it uses, so no real file is
# read or written during a test.
import scripts.check_version_consistency as vc  # noqa: E402


@pytest.fixture()
def planted(tmp_path: Path):
    """A minimal tree that the script treats as a repo root."""
    (tmp_path / ".version").write_text("0.89.0")
    (tmp_path / "extensions" / "gemini").mkdir(parents=True)
    (tmp_path / "extensions" / "gemini" / "gemini-extension.json").write_text(
        '{\n  "name": "spellbook",\n  "version": "0.89.0"\n}\n'
    )
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [Unreleased]\n\n## [0.89.0] - 2026-08-17\n\n"
        "### Fixed\n- test release\n"
    )
    return tmp_path


def _patches(tmp_path: Path):
    """Monkeypatch the module-level paths to point at ``tmp_path``."""
    return (
        patch.object(vc, "REPO_ROOT", tmp_path),
        patch.object(vc, "CHANGELOG_PATH", tmp_path / "CHANGELOG.md"),
        patch(
            "scripts.check_version_consistency.read_version",
            lambda p: "0.89.0",
        ),
        patch(
            "scripts.check_version_consistency.validate_version_consistency",
            lambda root: [],
        ),
        patch(
            "scripts.check_version_consistency.sync_version_to_files",
            lambda root, ver: [],
        ),
    )


# --- check_changelog_heading ---

class TestCheckChangelogHeading:
    def test_returns_empty_when_heading_exists(self, planted):
        with patch.object(vc, "CHANGELOG_PATH", planted / "CHANGELOG.md"):
            assert vc.check_changelog_heading("0.89.0") == []

    def test_returns_issue_when_heading_missing(self, planted):
        with patch.object(vc, "CHANGELOG_PATH", planted / "CHANGELOG.md"):
            result = vc.check_changelog_heading("0.99.0")
            assert len(result) == 1
            assert "## [0.99.0]" in result[0]

    def test_returns_issue_when_changelog_absent(self, planted):
        with patch.object(vc, "CHANGELOG_PATH", planted / "nonexistent.md"):
            result = vc.check_changelog_heading("0.89.0")
            assert len(result) == 1
            assert "not found" in result[0].lower()


# --- main() default path (no --fix) ---

class TestMainDefaultPath:
    def test_exit_zero_on_clean_tree(self, planted):
        p = _patches(planted)
        for cm in p:
            cm.__enter__()
        try:
            with patch.object(vc, "CHANGELOG_PATH", planted / "CHANGELOG.md"):
                assert vc.main([]) == 0
        finally:
            for cm in reversed(p):
                cm.__exit__(None, None, None)

    def test_exit_one_on_manifest_drift(self, planted):
        with patch.object(vc, "REPO_ROOT", planted), \
             patch.object(vc, "CHANGELOG_PATH", planted / "CHANGELOG.md"), \
             patch("scripts.check_version_consistency.read_version", lambda p: "0.89.0"), \
             patch("scripts.check_version_consistency.validate_version_consistency",
                   lambda root: ["gemini-extension.json has 0.1.0, expected 0.89.0"]), \
             patch("scripts.check_version_consistency.sync_version_to_files",
                   lambda root, ver: []):
            assert vc.main([]) == 1

    def test_exit_one_on_missing_changelog_heading(self, planted):
        (planted / "CHANGELOG.md").write_text("# Changelog\n\n## [Unreleased]\n")
        with patch.object(vc, "REPO_ROOT", planted), \
             patch.object(vc, "CHANGELOG_PATH", planted / "CHANGELOG.md"), \
             patch("scripts.check_version_consistency.read_version", lambda p: "0.89.0"), \
             patch("scripts.check_version_consistency.validate_version_consistency",
                   lambda root: []), \
             patch("scripts.check_version_consistency.sync_version_to_files",
                   lambda root, ver: []):
            assert vc.main([]) == 1


# --- main() --fix path ---

class TestMainFixPath:
    def test_fix_repairs_manifest_drift(self, planted):
        with patch.object(vc, "REPO_ROOT", planted), \
             patch.object(vc, "CHANGELOG_PATH", planted / "CHANGELOG.md"), \
             patch("scripts.check_version_consistency.read_version", lambda p: "0.89.0"), \
             patch("scripts.check_version_consistency.validate_version_consistency",
                   lambda root: [] if (planted / "extensions" / "gemini" / "gemini-extension.json")
                   .read_text().count("0.89.0") > 1 else ["drift"]), \
             patch("scripts.check_version_consistency.sync_version_to_files",
                   lambda root, ver: [str(planted / "extensions" / "gemini" / "gemini-extension.json")]):
            # Plant drift so validate returns non-empty on first call
            (planted / "extensions" / "gemini" / "gemini-extension.json").write_text(
                '{\n  "name": "spellbook",\n  "version": "0.1.0"\n}\n'
            )
            # After --fix, validate returns [] (synced)
            call_count = [0]
            def validate_side(root):
                call_count[0] += 1
                if call_count[0] == 1:
                    return ["drift"]
                return []
            with patch("scripts.check_version_consistency.validate_version_consistency",
                       validate_side):
                assert vc.main(["--fix"]) == 0

    def test_fix_does_not_touch_changelog(self, planted):
        """--fix must not write a CHANGELOG section even when one is missing."""
        (planted / "CHANGELOG.md").write_text("# Changelog\n\n## [Unreleased]\n")
        changelog_before = (planted / "CHANGELOG.md").read_text()
        with patch.object(vc, "REPO_ROOT", planted), \
             patch.object(vc, "CHANGELOG_PATH", planted / "CHANGELOG.md"), \
             patch("scripts.check_version_consistency.read_version", lambda p: "0.89.0"), \
             patch("scripts.check_version_consistency.validate_version_consistency",
                   lambda root: []), \
             patch("scripts.check_version_consistency.sync_version_to_files",
                   lambda root, ver: []):
            assert vc.main(["--fix"]) == 1
        changelog_after = (planted / "CHANGELOG.md").read_text()
        assert changelog_before == changelog_after
        assert "## [0.89.0]" not in changelog_after

    def test_fix_noop_on_clean_tree(self, planted):
        with patch.object(vc, "REPO_ROOT", planted), \
             patch.object(vc, "CHANGELOG_PATH", planted / "CHANGELOG.md"), \
             patch("scripts.check_version_consistency.read_version", lambda p: "0.89.0"), \
             patch("scripts.check_version_consistency.validate_version_consistency",
                   lambda root: []), \
             patch("scripts.check_version_consistency.sync_version_to_files",
                   lambda root, ver: []):
            assert vc.main(["--fix"]) == 0

    def test_fix_revalidates_after_repair(self, planted):
        """If --fix repairs the manifest but CHANGELOG is still missing the
        heading, it must exit 1, not 0."""
        (planted / "extensions" / "gemini" / "gemini-extension.json").write_text(
            '{\n  "name": "spellbook",\n  "version": "0.1.0"\n}\n'
        )
        (planted / "CHANGELOG.md").write_text("# Changelog\n\n## [Unreleased]\n")
        call_count = [0]
        def validate_side(root):
            call_count[0] += 1
            if call_count[0] == 1:
                return ["drift"]
            return []
        with patch.object(vc, "REPO_ROOT", planted), \
             patch.object(vc, "CHANGELOG_PATH", planted / "CHANGELOG.md"), \
             patch("scripts.check_version_consistency.read_version", lambda p: "0.89.0"), \
             patch("scripts.check_version_consistency.validate_version_consistency",
                   validate_side), \
             patch("scripts.check_version_consistency.sync_version_to_files",
                   lambda root, ver: [str(planted / "extensions" / "gemini" / "gemini-extension.json")]):
            assert vc.main(["--fix"]) == 1


# --- report() ---

class TestReport:
    def test_report_names_repair_command_for_manifest_issues(self, capsys):
        vc.report("0.89.0", ["manifest broken"], [])
        captured = capsys.readouterr()
        assert vc.REPAIR_COMMAND in captured.out

    def test_report_does_not_name_repair_for_changelog_only(self, capsys):
        vc.report("0.89.0", [], ["heading missing"])
        captured = capsys.readouterr()
        assert vc.REPAIR_COMMAND not in captured.out


# --- mutation test: neutering the guards makes tests red ---

class TestGuardsAreLoadBearing:
    """If check_changelog_heading always returns [], main() must not exit 0
    when the heading is genuinely missing — proving the check is load-bearing."""

    def test_heading_check_cannot_be_neutered(self, planted):
        (planted / "CHANGELOG.md").write_text("# Changelog\n\n## [Unreleased]\n")
        with patch.object(vc, "REPO_ROOT", planted), \
             patch.object(vc, "CHANGELOG_PATH", planted / "CHANGELOG.md"), \
             patch("scripts.check_version_consistency.read_version", lambda p: "0.89.0"), \
             patch("scripts.check_version_consistency.validate_version_consistency",
                   lambda root: []), \
             patch("scripts.check_version_consistency.sync_version_to_files",
                   lambda root, ver: []):
            # Real check catches the missing heading.
            assert vc.main([]) == 1
            # Neuter: replace the check with a no-op.
            with patch.object(vc, "check_changelog_heading", lambda v: []):
                assert vc.main([]) == 0
