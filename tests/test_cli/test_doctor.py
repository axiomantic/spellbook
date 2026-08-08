"""Tests for spellbook doctor command."""

import json
from pathlib import Path

import tripwire
import pytest

from spellbook.cli.commands.doctor import register, run


class TestRegister:
    """Tests for register()."""

    def test_register_adds_doctor_subcommand(self):
        """register() should add 'doctor' to the subparsers."""
        import argparse

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        register(subparsers)
        args = parser.parse_args(["doctor"])
        assert args.command == "doctor"
        assert hasattr(args, "func")

    def test_help_flag(self):
        """doctor --help should exit 0."""
        import argparse

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        register(subparsers)
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["doctor", "--help"])
        assert exc_info.value.code == 0


class TestDoctorRun:
    """Tests for the doctor run function."""

    def test_runs_without_crashing(self, capsys):
        """doctor should run without errors."""
        import argparse

        args = argparse.Namespace(json=False)
        # Should not raise; may exit with code 0 or 2 depending on checks
        try:
            run(args)
        except SystemExit:
            pass
        captured = capsys.readouterr()
        # Should produce some output with PASS or FAIL markers
        assert captured.out  # Some output produced

    def test_json_output_valid(self, capsys):
        """doctor --json should produce valid JSON."""
        import argparse

        args = argparse.Namespace(json=True)
        try:
            run(args)
        except SystemExit:
            pass
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "checks" in data
        assert isinstance(data["checks"], list)
        # Each check should have name, status
        for check in data["checks"]:
            assert "name" in check
            assert "status" in check
            assert check["status"] in ("pass", "fail", "warn")

    def test_exit_code_zero_when_all_pass(self, capsys):
        """doctor should exit 0 when all checks pass."""
        from spellbook.health import doctor

        def fake_checks():
            return [
                doctor.CheckResult("test", "pass", "ok"),
            ]

        proxy = tripwire.mock("spellbook.cli.commands.doctor:run_checks")
        proxy.calls(fake_checks)

        import argparse

        args = argparse.Namespace(json=False)
        with tripwire:
            run(args)
        # If we get here without SystemExit, exit code is 0
        proxy.assert_call(args=(), kwargs={})


class TestDoctorChecks:
    """Tests for individual doctor checks."""

    def test_run_checks_returns_list(self):
        """run_checks should return a list of CheckResult."""
        from spellbook.health.doctor import run_checks

        results = run_checks()
        assert isinstance(results, list)
        assert len(results) > 0

    def test_check_result_has_required_fields(self):
        """CheckResult should have name, status, detail."""
        from spellbook.health.doctor import CheckResult

        cr = CheckResult(name="test", status="pass", detail="ok")
        assert cr.name == "test"
        assert cr.status == "pass"
        assert cr.detail == "ok"

    def test_python_version_check_passes(self):
        """Python version check should pass on 3.10+."""
        from spellbook.health.doctor import check_python_version

        result = check_python_version()
        assert result.status == "pass"


class TestRuleModulesCheck:
    """Tests for the RULES_MISSING check (dangling rule symlinks)."""

    def _installer(self, tmp_path):
        from installer.platforms.claude_code import ClaudeCodeInstaller

        return ClaudeCodeInstaller(
            spellbook_dir=tmp_path / "spellbook",
            config_dir=tmp_path / "config",
            version="0",
            dry_run=True,
        )

    def test_no_dangling_paths_when_nothing_installed(self, tmp_path):
        from spellbook.health.doctor import _dangling_rule_paths

        assert _dangling_rule_paths(self._installer(tmp_path)) == []

    def test_intact_module_symlink_is_not_dangling(self, tmp_path):
        from spellbook.health.doctor import _dangling_rule_paths

        source = tmp_path / "spellbook" / "rules" / "00-core.md"
        source.parent.mkdir(parents=True)
        source.write_text("rules", encoding="utf-8")

        rules_dir = tmp_path / "config" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "00-spellbook-core.md").symlink_to(source)

        assert _dangling_rule_paths(self._installer(tmp_path)) == []

    def test_dangling_module_symlink_is_detected(self, tmp_path):
        from spellbook.health.doctor import _dangling_rule_paths

        rules_dir = tmp_path / "config" / "rules"
        rules_dir.mkdir(parents=True)
        link = rules_dir / "00-spellbook-core.md"
        link.symlink_to(tmp_path / "spellbook" / "rules" / "00-core.md")

        assert _dangling_rule_paths(self._installer(tmp_path)) == [link]

    def test_dangling_legacy_sidecar_is_detected(self, tmp_path):
        from spellbook.health.doctor import _dangling_rule_paths

        rules_dir = tmp_path / "config" / "rules"
        rules_dir.mkdir(parents=True)
        legacy = rules_dir / "spellbook.md"
        legacy.symlink_to(tmp_path / "spellbook" / "AGENTS.spellbook.md")

        assert _dangling_rule_paths(self._installer(tmp_path)) == [legacy]

    def _fixture_tree(self, tmp_path, monkeypatch, *, dangling: bool):
        """A hermetic claude_code install: real rules source, real symlink.

        Every other platform is pointed at an empty directory so the check
        inspects the fixture and not the developer's own machine.
        """
        from installer.config import SUPPORTED_PLATFORMS

        repo_root = Path(__file__).resolve().parents[2]
        config = tmp_path / "config"
        rules_dir = config / "rules"
        rules_dir.mkdir(parents=True)

        source = repo_root / "rules" / "00-core.md"
        assert source.exists(), "precondition: the checkout ships rules/00-core.md"
        target = tmp_path / "gone" / "00-core.md" if dangling else source
        (rules_dir / "00-spellbook-core.md").symlink_to(target)

        # ForgeCode resolves its own dir from the environment, ignoring the
        # config_dir override, so it needs pinning separately.
        forge = tmp_path / "empty" / "forge"
        forge.mkdir(parents=True)
        monkeypatch.setenv("FORGE_CONFIG", str(forge))

        dirs = {p: tmp_path / "empty" / p for p in SUPPORTED_PLATFORMS}
        dirs["claude_code"] = config
        return repo_root, dirs

    def test_check_fails_on_a_dangling_link(self, tmp_path, monkeypatch):
        """The state the check exists for, asserted on a fixture tree.

        The previous test called ``check_rule_modules()`` with no arguments --
        inspecting the developer's real machine -- and asserted the status was
        one of the three possible statuses, so it could not fail.
        """
        from spellbook.health.doctor import check_rule_modules

        repo_root, dirs = self._fixture_tree(tmp_path, monkeypatch, dangling=True)

        result = check_rule_modules(
            config_dirs=dirs, spellbook_dir=repo_root
        )

        assert result.name == "rule_modules"
        assert result.status == "fail"
        assert "00-spellbook-core.md" in result.detail

    def test_check_passes_on_an_intact_link(self, tmp_path, monkeypatch):
        from spellbook.health.doctor import check_rule_modules

        repo_root, dirs = self._fixture_tree(tmp_path, monkeypatch, dangling=False)

        result = check_rule_modules(
            config_dirs=dirs, spellbook_dir=repo_root
        )

        assert result.status == "pass", result.detail

    def test_check_fails_when_an_installed_platform_has_no_core_module(
        self, tmp_path, monkeypatch
    ):
        """"Nothing is dangling" is satisfied by delivering nothing at all.

        A prune-everything regression leaves an installed platform with an
        empty rules directory and no dangling link, which read as healthy.
        """
        from spellbook.health.doctor import check_rule_modules

        repo_root, dirs = self._fixture_tree(tmp_path, monkeypatch, dangling=False)
        # Keep the platform detectably installed, then remove the core module.
        rules_dir = dirs["claude_code"] / "rules"
        (rules_dir / "00-spellbook-core.md").unlink()
        (rules_dir / "10-spellbook-session.md").symlink_to(
            repo_root / "rules" / "00-core.md"
        )

        result = check_rule_modules(
            config_dirs=dirs, spellbook_dir=repo_root
        )

        assert result.status == "fail"
        assert "core rule module" in result.detail

    def test_check_is_registered_in_run_checks(self):
        from spellbook.health.doctor import run_checks

        assert any(r.name == "rule_modules" for r in run_checks())

    def test_a_skipped_platform_is_named_not_silently_dropped(
        self, tmp_path, monkeypatch
    ):
        """A green line that inspected one platform read identically to one that
        inspected seven.

        ``except Exception: continue`` kept the loop alive but dropped the
        platform from the report entirely, so "No dangling rule paths across
        1 platform(s)" was the only trace -- and nothing asserted the count.
        """
        from installer.config import SUPPORTED_PLATFORMS
        from installer.core import get_platform_installer
        from spellbook.health.doctor import check_rule_modules

        repo_root, dirs = self._fixture_tree(tmp_path, monkeypatch, dangling=False)
        real = get_platform_installer

        def _only_claude_code(platform, root, **kwargs):
            if platform == "claude_code":
                return real(platform, root, **kwargs)
            raise OSError(f"{platform} config dir is unreadable")

        probe = tripwire.mock("installer.core:get_platform_installer")
        for _ in SUPPORTED_PLATFORMS:
            probe.calls(_only_claude_code)

        with tripwire:
            result = check_rule_modules(config_dirs=dirs, spellbook_dir=repo_root)

        with tripwire.in_any_order():
            for platform in SUPPORTED_PLATFORMS:
                probe.assert_call(
                    args=(platform, repo_root),
                    kwargs={
                        "version": "0",
                        "dry_run": True,
                        "config_dir_override": dirs[platform],
                    },
                )

        skipped = [p for p in SUPPORTED_PLATFORMS if p != "claude_code"]
        assert result.status == "warn", result.detail
        for platform in skipped:
            assert platform in result.detail, (
                f"{platform} was skipped without appearing in the report"
            )
