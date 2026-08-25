"""The executable entry point for autonomous mode.

Every test here spawns the helper as a REAL SUBPROCESS against a real state
directory, because that is how the skill invokes it. A CLI proven by
importing its functions is not proven as a CLI: argparse wiring, the
session-id default, and the exit codes a slash command branches on all live
outside the functions.

The assertion is always the RECORD plus the exit code, never the helper's
own stdout alone. This feature is enabled-but-unwired in exactly the shape
where a command reports a write nothing verified.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
HELPER = PROJECT_ROOT / "skills" / "autonomous-mode" / "scripts" / "autonomous_mode.py"

SID = "cli-sess_1.2"

pytestmark = pytest.mark.allow("subprocess")


@pytest.fixture
def home(tmp_path):
    """A state directory of our own, addressed the way the module resolves it."""
    return tmp_path


def _env(home: Path, session_id: str | None = None) -> dict:
    env = dict(os.environ)
    for var in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA"):
        env[var] = str(home)
    env.pop("CLAUDE_CODE_SESSION_ID", None)
    if session_id is not None:
        env["CLAUDE_CODE_SESSION_ID"] = session_id
    return env


def _run(home: Path, *argv: str, session_id: str | None = None):
    return subprocess.run(
        [sys.executable, str(HELPER), *argv],
        capture_output=True,
        text=True,
        env=_env(home, session_id),
        timeout=30,
    )


def _record_path(home: Path, session_id: str = SID) -> Path:
    return home / ".local" / "spellbook" / "autonomous" / f"{session_id}.json"


def _enable(home: Path, *extra: str, session_id: str | None = SID):
    return _run(
        home,
        "enable",
        "--mode",
        "fully",
        "--philosophy",
        "hostile-review",
        "--goal",
        "ship the entry point",
        *extra,
        session_id=session_id,
    )


class TestTheHelperExists:
    def test_it_is_executable_and_reachable_from_the_repo(self):
        assert HELPER.is_file()


class TestEnable:
    def test_it_writes_a_record_the_hook_can_read(self, home):
        result = _enable(home)
        assert result.returncode == 0, result.stderr
        path = _record_path(home)
        assert path.is_file()
        record = json.loads(path.read_text(encoding="utf-8"))
        assert record["mode"] == "fully"
        assert record["philosophy"] == "hostile-review"
        assert record["goal"] == "ship the entry point"
        assert record["blocked_stops"] == 0
        assert record["decisions"] == []

    def test_the_session_id_comes_from_the_harness_variable(self, home):
        """The gap that made the feature unwireable: nothing said where the
        session id comes from, so an agent had to guess."""
        result = _enable(home)
        assert result.returncode == 0, result.stderr
        assert _record_path(home).is_file()

    def test_an_explicit_flag_overrides_the_variable(self, home):
        result = _enable(home, "--session-id", "explicit-sid", session_id=SID)
        assert result.returncode == 0, result.stderr
        assert _record_path(home, "explicit-sid").is_file()
        assert not _record_path(home, SID).exists()

    def test_it_prints_the_record_it_read_back(self, home):
        result = _enable(home)
        assert json.loads(result.stdout) == json.loads(
            _record_path(home).read_text(encoding="utf-8")
        )

    def test_no_session_id_anywhere_fails_without_a_traceback(self, home):
        result = _enable(home, session_id=None)
        assert result.returncode == 1
        assert "Traceback" not in result.stderr
        assert "CLAUDE_CODE_SESSION_ID" in result.stderr

    def test_an_invalid_session_id_fails_and_writes_nothing(self, home):
        result = _enable(home, session_id="../../etc/passwd")
        assert result.returncode == 1
        assert "Traceback" not in result.stderr
        assert not (home / ".local" / "spellbook" / "autonomous").exists()

    def test_an_unwritable_state_directory_fails_loudly(self, home):
        """The exact fault that traps a session, reported rather than raised."""
        if os.name != "posix" or os.geteuid() == 0:
            pytest.skip("POSIX permission bits only; root ignores them")
        local = home / ".local"
        local.mkdir(parents=True, exist_ok=True)
        local.chmod(0o500)
        try:
            result = _enable(home)
        finally:
            local.chmod(0o700)
        assert result.returncode == 1
        assert "Traceback" not in result.stderr
        assert result.stdout == ""

    def test_an_unknown_philosophy_is_refused_by_the_parser(self, home):
        result = _run(
            home,
            "enable",
            "--mode",
            "fully",
            "--philosophy",
            "vibes",
            "--goal",
            "x",
            session_id=SID,
        )
        assert result.returncode == 2
        assert not _record_path(home).exists()


class TestStatus:
    def test_it_reports_the_record_and_exits_zero(self, home):
        _enable(home)
        result = _run(home, "status", session_id=SID)
        assert result.returncode == 0
        assert json.loads(result.stdout)["goal"] == "ship the entry point"

    def test_no_record_is_not_autonomous_and_not_a_crash(self, home):
        result = _run(home, "status", session_id=SID)
        assert result.returncode == 3
        assert "not autonomous" in result.stderr
        assert "Traceback" not in result.stderr

    def test_a_malformed_record_reads_as_not_autonomous(self, home):
        _enable(home)
        _record_path(home).write_text("{not json", encoding="utf-8")
        result = _run(home, "status", session_id=SID)
        assert result.returncode == 3
        assert "Traceback" not in result.stderr

    def test_status_is_how_the_skill_confirms_the_write_landed(self, home):
        """Read is not optional: the skill must CONFIRM, not assume."""
        _enable(home)
        _record_path(home).unlink()
        assert _run(home, "status", session_id=SID).returncode == 3


class TestClear:
    def test_it_removes_the_record(self, home):
        _enable(home)
        result = _run(home, "clear", session_id=SID)
        assert result.returncode == 0
        assert not _record_path(home).exists()

    def test_clearing_an_absent_record_is_a_success(self, home):
        assert _run(home, "clear", session_id=SID).returncode == 0

    def test_a_clear_that_failed_reports_failure(self, home):
        if os.name != "posix" or os.geteuid() == 0:
            pytest.skip("POSIX permission bits only; root ignores them")
        _enable(home)
        directory = _record_path(home).parent
        directory.chmod(0o500)
        try:
            result = _run(home, "clear", session_id=SID)
        finally:
            directory.chmod(0o700)
        assert result.returncode == 1
        assert _record_path(home).is_file()
        assert str(_record_path(home)) in result.stderr


class TestDecide:
    def test_it_appends_a_decision(self, home):
        _enable(home)
        result = _run(
            home,
            "decide",
            "--decision",
            "used the a2a helper shape",
            "--alternatives",
            "a new MCP tool",
            session_id=SID,
        )
        assert result.returncode == 0, result.stderr
        decisions = json.loads(_record_path(home).read_text(encoding="utf-8"))[
            "decisions"
        ]
        assert len(decisions) == 1
        assert decisions[0]["decision"] == "used the a2a helper shape"
        assert decisions[0]["alternatives"] == "a new MCP tool"

    def test_it_copies_the_philosophy_active_at_the_time(self, home):
        _enable(home)
        _run(
            home,
            "decide",
            "--decision",
            "d",
            "--alternatives",
            "a",
            session_id=SID,
        )
        decisions = json.loads(_record_path(home).read_text(encoding="utf-8"))[
            "decisions"
        ]
        assert decisions[0]["philosophy"] == "hostile-review"

    def test_deciding_outside_autonomous_mode_fails(self, home):
        result = _run(
            home,
            "decide",
            "--decision",
            "d",
            "--alternatives",
            "a",
            session_id=SID,
        )
        assert result.returncode == 1
        assert "Traceback" not in result.stderr

    def test_the_decision_log_is_what_separates_fully_from_mostly(self, home):
        """With no caller for it, the two modes were indistinguishable."""
        _enable(home)
        for i in range(2):
            assert (
                _run(
                    home,
                    "decide",
                    "--decision",
                    f"d{i}",
                    "--alternatives",
                    "a",
                    session_id=SID,
                ).returncode
                == 0
            )
        record = json.loads(_record_path(home).read_text(encoding="utf-8"))
        assert [d["decision"] for d in record["decisions"]] == ["d0", "d1"]


class TestPhilosophies:
    def test_it_prints_the_enum_the_skill_offers(self, home):
        result = _run(home, "philosophies")
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        from spellbook.core.autonomous import DEFAULT_PHILOSOPHY, PHILOSOPHIES

        assert payload["philosophies"] == PHILOSOPHIES
        assert payload["default"] == DEFAULT_PHILOSOPHY


class TestUsage:
    def test_no_subcommand_is_a_usage_error(self, home):
        result = _run(home)
        assert result.returncode == 2

    def test_an_unknown_subcommand_is_a_usage_error(self, home):
        assert _run(home, "levitate").returncode == 2
