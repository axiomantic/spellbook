"""Tests for spellbook doctor command."""

import json
import sys
from unittest.mock import patch

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

    def test_exit_code_zero_when_all_pass(self, capsys, monkeypatch):
        """doctor should exit 0 when all checks pass."""
        from spellbook.health import doctor

        def fake_checks():
            return [
                doctor.CheckResult("test", "pass", "ok"),
            ]

        monkeypatch.setattr(
            "spellbook.cli.commands.doctor.run_checks", fake_checks
        )
        import argparse

        args = argparse.Namespace(json=False)
        run(args)
        # If we get here without SystemExit, exit code is 0


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
