"""The Stop hook's time budget, held against what the handler actually spends.

The harness cancels a hook that reaches its registered timeout, discards its
output, and renders no decision -- so the stop PROCEEDS. Overrunning the
timeout is therefore a SILENT BYPASS of autonomous-mode enforcement, not a
loud failure, and it strikes exactly the long-running sessions the gate
exists for. Nothing in the running system reports it.

That makes the registered number load-bearing, so it is derived rather than
chosen, and the terms of the derivation are pinned here against measured
behavior rather than against reasoning:

* the git spend is pinned by driving a real ``dispatch("Stop", ...)`` down the
  path that cannot resolve a repo root without git, and counting the
  subprocesses it actually starts;
* the transcript spend is pinned by measuring the real scan and extrapolating
  the measured rate to the largest transcript the allowance was sized for.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest
import tripwire

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

import spellbook_hook  # noqa: E402

from installer.components.hooks import (  # noqa: E402
    HOOK_DEFINITIONS,
    STOP_HOOK_TIMEOUT_SECONDS,
    TRANSCRIPT_SCAN_ALLOWANCE_SECONDS,
)
from spellbook.core import autonomous  # noqa: E402
from spellbook.core import path_utils  # noqa: E402
from spellbook.core.path_utils import (  # noqa: E402
    GIT_SUBPROCESS_CALLS_PER_RESOLVE,
    GIT_SUBPROCESS_TIMEOUT_SECONDS,
)

SID = "sess-budget_1"

# What git reports on stderr for a path it can discover no repository for.
NOT_A_REPOSITORY = "fatal: not a git repository (or any of the parent directories): .git\n"

GIT_WORST_CASE_SECONDS = GIT_SUBPROCESS_CALLS_PER_RESOLVE * GIT_SUBPROCESS_TIMEOUT_SECONDS

# The transcript allowance was sized against a transcript of this size, seen on
# the operator's machine on an autonomous session. The scan is linear in bytes,
# so a measured rate extrapolates to it; ``test_the_transcript_allowance_covers
# _the_largest_observed_transcript`` is what keeps that true.
LARGEST_OBSERVED_TRANSCRIPT_MB = 310


def _registered_stop_timeout() -> int:
    entries = HOOK_DEFINITIONS["Stop"]
    hooks = [h for entry in entries for h in entry["hooks"]]
    assert len(hooks) == 1, "the derivation below assumes one Stop hook"
    return hooks[0]["timeout"]


class TestTheRegisteredTimeoutCoversTheWorstCase:
    def test_the_git_worst_case_alone_would_exhaust_the_old_budget(self):
        """Why this is not a style change: the spend can outrun a small number.

        Resolving the ledger path can spend ``GIT_WORST_CASE_SECONDS`` before
        the handler has read a single byte of transcript. Any timeout at or
        below that is bypassable by the git spend by itself.
        """
        assert GIT_WORST_CASE_SECONDS > 5

    def test_the_registered_timeout_exceeds_the_git_worst_case(self):
        assert _registered_stop_timeout() > GIT_WORST_CASE_SECONDS

    def test_the_registered_timeout_is_the_derived_budget(self):
        assert _registered_stop_timeout() == STOP_HOOK_TIMEOUT_SECONDS
        assert STOP_HOOK_TIMEOUT_SECONDS == (
            GIT_WORST_CASE_SECONDS + TRANSCRIPT_SCAN_ALLOWANCE_SECONDS
        )


class TestTheGitSpendIsWhatTheBudgetAssumes:
    """The ``GIT_SUBPROCESS_CALLS_PER_RESOLVE`` term, held against a real Stop.

    A record and a ledger are both present, so the handler takes the branch
    that resolves the ledger path. Git is spawned only when the git-free
    repo-root walk defers, and the walk defers under a git discovery override
    -- so the override is set as an environment variable rather than the walk
    replaced, which leaves real git seeing the same discovery rules the walk
    answered from.
    """

    @pytest.fixture
    def git_is_reached(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        monkeypatch.setenv("APPDATA", str(tmp_path))
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        # An exact override would skip resolution entirely, which is the very
        # thing under measurement.
        monkeypatch.delenv("SPELLBOOK_DEV_DIR", raising=False)
        # Git stops discovery at a ceiling, so under one it can report no
        # repository for a path the walk would otherwise have answered from
        # disk. The walk defers on every GIT_* override for that reason, and
        # deferring is the only condition under which git is spawned at all.
        monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))

        import develop_gate_ledger

        state_dir = develop_gate_ledger.default_state_dir()
        state_dir.mkdir(parents=True, exist_ok=True)
        # The state dir must be non-empty or _develop_ledger_path short
        # circuits before resolution -- the case this measurement is not about.
        (state_dir / "develop_gate_ledger-someproject.json").write_text(
            "{}", encoding="utf-8"
        )

    def test_a_stop_spawns_no_more_git_than_the_budget_pays_for(
        self, git_is_reached, tmp_path
    ):
        assert autonomous.write_autonomous_record(
            SID,
            mode="fully",
            philosophy="hostile-review",
            goal="measure the budget",
            goal_criteria=["tests pass"],
            set_at="2026-08-24T00:00:00Z",
        ) is True
        transcript = tmp_path / "t.jsonl"
        transcript.write_text(
            json.dumps({"type": "user", "message": {"role": "user", "content": "go"}})
            + "\n",
            encoding="utf-8",
        )

        # Enumerating the spend is what bounds it. A spawn beyond this list
        # finds no mock left in the queue and fails the call outright, so the
        # budget cannot be overrun quietly; a spawn that never happens is an
        # unused mock, which fails at teardown. The list is held against the
        # budgeted count so the two cannot drift apart.
        budgeted = [
            ["git", "worktree", "list", "--porcelain"],
            ["git", "rev-parse", "--show-toplevel"],
        ]
        assert len(budgeted) == GIT_SUBPROCESS_CALLS_PER_RESOLVE
        # What git reports for a path under a ceiling directory: no repository,
        # which is the path the fallback below is written for.
        for command in budgeted:
            tripwire.subprocess.mock_run(
                command,
                returncode=128,
                stdout="",
                stderr=NOT_A_REPOSITORY,
            )

        with tripwire:
            raw = spellbook_hook.dispatch(
                "Stop",
                "",
                {
                    "hook_event_name": "Stop",
                    "session_id": SID,
                    "transcript_path": str(transcript),
                    "cwd": str(tmp_path),
                    "stop_hook_active": False,
                },
            )

        # The gate still ran: this is a measurement of a working handler, not
        # of one that returned early for an unrelated reason.
        assert raw is not None and json.loads(raw)["decision"] == "block"
        for command in budgeted:
            tripwire.subprocess.assert_run(
                command,
                returncode=128,
                stdout="",
                stderr=NOT_A_REPOSITORY,
            )

    @pytest.mark.slow
    def test_the_git_spend_cannot_outrun_the_budgeted_worst_case(
        self, git_is_reached, tmp_path, monkeypatch
    ):
        """Both spawns made to hang, and the real wall clock held to the term.

        ``GIT_WORST_CASE_SECONDS`` is the number the registered timeout is
        derived from, and it is a product of a call count and a per-call
        timeout. Neither factor is observable from outside the call, so this
        spends the worst case for real: a git that never answers makes every
        spawn pay its full timeout, and the elapsed time is then the product
        itself. Raising a timeout, dropping one, or adding a third spawn moves
        this reading; asserting the keyword argument would catch only the
        first.
        """
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        never_answers = bin_dir / "git"
        # Bounded so a lost timeout fails the upper bound rather than hanging
        # the suite until pytest is killed.
        never_answers.write_text("#!/bin/sh\nsleep 30\n", encoding="utf-8")
        never_answers.chmod(0o755)
        monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")

        started = time.monotonic()
        resolved = path_utils.resolve_repo_root(str(tmp_path))
        elapsed = time.monotonic() - started

        # Neither probe answered, so the documented fallback is the input path.
        # A different answer here means git was never reached and the reading
        # below measures nothing.
        assert resolved == str(tmp_path)
        # Every budgeted spawn paid its full timeout: below this, a spawn was
        # skipped or a timeout was shortened.
        assert elapsed >= GIT_WORST_CASE_SECONDS - 1, elapsed
        # And no spawn outran it. The slack is process startup for each spawn,
        # not room for another one.
        assert elapsed < GIT_WORST_CASE_SECONDS + GIT_SUBPROCESS_TIMEOUT_SECONDS, elapsed


class TestTheTranscriptSpendIsWhatTheBudgetAssumes:
    def test_the_transcript_allowance_covers_the_largest_observed_transcript(
        self, tmp_path
    ):
        """Measure the real scan, then extrapolate to the size sized against.

        The assertion is on a rate rather than on a wall-clock reading of the
        full size: generating a 310 MB file per run is not worth the seconds,
        and the scan is linear in bytes. A change that made it super-linear --
        the way this allowance would realistically be blown -- shows up as a
        collapsed rate here.
        """
        line = json.dumps(
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "tool_use", "id": "t", "name": "Bash", "input": {"x": "y" * 200}}
                    ],
                },
            }
        )
        chunk = (line + "\n").encode("utf-8")
        target_bytes = 8 * 1024 * 1024
        transcript = tmp_path / "big.jsonl"
        with transcript.open("wb") as handle:
            written = 0
            while written < target_bytes:
                handle.write(chunk)
                written += len(chunk)
        megabytes = transcript.stat().st_size / (1024 * 1024)

        started = time.monotonic()
        result = spellbook_hook._transcript_has_ask_user_question(str(transcript))
        elapsed = time.monotonic() - started

        # A scan that answered nothing was not a scan.
        assert result is False

        projected = (elapsed / megabytes) * LARGEST_OBSERVED_TRANSCRIPT_MB
        assert projected <= TRANSCRIPT_SCAN_ALLOWANCE_SECONDS, (
            f"scanned {megabytes:.1f} MB in {elapsed:.3f}s; projected "
            f"{projected:.2f}s for {LARGEST_OBSERVED_TRANSCRIPT_MB} MB, over the "
            f"{TRANSCRIPT_SCAN_ALLOWANCE_SECONDS}s allowance"
        )
