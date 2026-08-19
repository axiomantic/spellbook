"""Behavioural tests for the Phase 1 research-findings checker.

Each test pins a findings artifact that MUST be rejected against the same
artifact repaired, so a check that degenerates into "always pass" fails here.
The old form of this gate was TypeScript pseudocode nobody executed; a checker
that cannot be shown to reject anything would reproduce that defect in a
language that merely looks executable.

Stated blind spot: these tests prove the checker distinguishes a structurally
complete findings artifact from an incomplete one. They say nothing about
whether a passing artifact's answers are CORRECT or whether a HIGH confidence
rating is deserved -- that half is labelled self-assessment in
`commands/feature-research.md`.
"""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_research_quality.py"

_spec = importlib.util.spec_from_file_location("check_research_quality", SCRIPT)
assert _spec and _spec.loader
checker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checker)


COMPLETE = {
    "findings": [
        {
            "question": "Where is authentication handled?",
            "answer": "In src/auth/session.py via a middleware.",
            "confidence": "HIGH",
            "evidence": ["src/auth/session.py:41"],
            "ambiguities": [],
        },
        {
            "question": "Which token format do mobile clients send?",
            "answer": "No evidence found in the repository.",
            "confidence": "UNKNOWN",
            "evidence": [],
            "ambiguities": ["Mobile client repo is not vendored here"],
        },
    ],
    "patterns_discovered": [
        {
            "name": "middleware-per-concern",
            "files": ["src/auth/session.py"],
            "description": "Each cross-cutting concern is one middleware.",
        }
    ],
    "unknowns": ["Which token format do mobile clients send"],
    "project_standards": {
        "searched": True,
        "search_globs_used": ["AGENTS.md", "docs/**/*.md"],
        "none_found": False,
        "sources": [{"path": "AGENTS.md", "kind": "process", "summary": "run pytest"}],
        "binding_rules": [],
    },
    "tooling": {
        "checked": True,
        "none_missing": True,
        "missing": [],
    },
}


def failures_for(data: dict, name: str) -> list[str]:
    return dict(checker.run_checks(data))[name]


def test_complete_artifact_passes_every_check():
    assert all(not failures for _, failures in checker.run_checks(COMPLETE))


def test_missing_top_level_key_is_rejected():
    broken = {k: v for k, v in COMPLETE.items() if k != "unknowns"}
    assert any("unknowns" in f for f in failures_for(broken, "schema-shape"))


def test_empty_findings_is_rejected():
    broken = copy.deepcopy(COMPLETE)
    broken["findings"] = []
    assert failures_for(broken, "schema-shape")


def test_finding_missing_a_field_is_rejected():
    broken = copy.deepcopy(COMPLETE)
    del broken["findings"][0]["ambiguities"]
    assert any("ambiguities" in f for f in failures_for(broken, "finding-fields"))


def test_blank_answer_is_rejected():
    broken = copy.deepcopy(COMPLETE)
    broken["findings"][0]["answer"] = "[...]"
    assert any("blank" in f for f in failures_for(broken, "finding-fields"))


def test_confidence_outside_the_enum_is_rejected():
    broken = copy.deepcopy(COMPLETE)
    broken["findings"][0]["confidence"] = "PRETTY SURE"
    assert any("confidence not one of" in f for f in failures_for(broken, "finding-fields"))


def test_answerable_finding_without_evidence_is_rejected():
    broken = copy.deepcopy(COMPLETE)
    broken["findings"][0]["evidence"] = []
    assert failures_for(broken, "evidence-present")


def test_blank_evidence_entry_does_not_count_as_evidence():
    broken = copy.deepcopy(COMPLETE)
    broken["findings"][0]["evidence"] = ["   "]
    assert failures_for(broken, "evidence-present")


def test_unknown_finding_needs_no_evidence():
    assert not failures_for(COMPLETE, "evidence-present")


def test_low_confidence_finding_absent_from_unknowns_is_rejected():
    broken = copy.deepcopy(COMPLETE)
    broken["findings"][0]["confidence"] = "LOW"
    assert any("absent from `unknowns`" in f for f in failures_for(broken, "unknowns-flagged"))


def test_flagging_the_low_confidence_question_repairs_it():
    repaired = copy.deepcopy(COMPLETE)
    repaired["findings"][0]["confidence"] = "LOW"
    repaired["unknowns"].append("Where is authentication handled")
    assert not failures_for(repaired, "unknowns-flagged")


def test_pattern_without_file_references_is_rejected():
    broken = copy.deepcopy(COMPLETE)
    broken["patterns_discovered"][0]["files"] = []
    assert any("no file references" in f for f in failures_for(broken, "patterns-sourced"))


def test_deferral_marker_is_rejected():
    broken = copy.deepcopy(COMPLETE)
    broken["findings"][0]["answer"] = "TBD"
    assert failures_for(broken, "no-deferrals")


def test_unknown_confidence_is_not_read_as_a_deferral():
    assert not failures_for(COMPLETE, "no-deferrals")


def test_standards_sweep_not_run_is_rejected():
    broken = copy.deepcopy(COMPLETE)
    broken["project_standards"]["searched"] = False
    assert any("not recorded as run" in f for f in failures_for(broken, "standards-sweep-recorded"))


def test_empty_sweep_needs_globs_to_be_auditable():
    broken = copy.deepcopy(COMPLETE)
    broken["project_standards"]["sources"] = []
    broken["project_standards"]["none_found"] = True
    broken["project_standards"]["search_globs_used"] = []
    assert failures_for(broken, "standards-sweep-recorded")

    repaired = copy.deepcopy(broken)
    repaired["project_standards"]["search_globs_used"] = ["AGENTS.md"]
    assert not failures_for(repaired, "standards-sweep-recorded")


def test_exit_status_is_the_gate(tmp_path, capsys):
    good = tmp_path / "good.json"
    good.write_text(json.dumps(COMPLETE), encoding="utf-8")
    assert checker.main([str(good)]) == 0

    broken = copy.deepcopy(COMPLETE)
    broken["findings"][0]["evidence"] = []
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(broken), encoding="utf-8")
    assert checker.main([str(bad)]) == 1
    assert "Phase 1 gate: BLOCKED" in capsys.readouterr().out


def test_missing_file_is_a_usage_error(tmp_path):
    assert checker.main([str(tmp_path / "absent.json")]) == 2


def test_unparseable_file_is_a_usage_error(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    assert checker.main([str(path)]) == 2


def test_no_percentage_is_printed(tmp_path, capsys):
    path = tmp_path / "good.json"
    path.write_text(json.dumps(COMPLETE), encoding="utf-8")
    checker.main([str(path)])
    assert "%" not in capsys.readouterr().out


def blocked_session() -> dict:
    """The reported session: `hg: command not found`, then design around it."""
    broken = copy.deepcopy(COMPLETE)
    del broken["tooling"]
    broken["findings"][0]["answer"] = (
        "Could not compare against the upstream history: hg: command not found, "
        "so the design assumes a git-only workflow."
    )
    return broken


def test_missing_tool_mentioned_without_a_tooling_record_is_rejected():
    failures = failures_for(blocked_session(), "tooling-blockers-resolved")
    assert any("`tooling` object missing" in f for f in failures)


def test_the_blocked_session_is_advised_on_the_line_that_names_the_tool():
    advisories = dict(
        (name, advise(blocked_session())) for name, advise in checker.ADVISORIES
    )["tooling-blockers-mentioned"]
    assert any("command not found" in a for a in advisories)


def test_the_detector_is_advisory_and_does_not_change_exit_status(tmp_path, capsys):
    artifact = copy.deepcopy(COMPLETE)
    artifact["findings"][0]["answer"] = "The probe reported: hg: command not found."
    path = tmp_path / "advisory.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")
    assert checker.main([str(path)]) == 0
    out = capsys.readouterr().out
    assert "WARN  tooling-blockers-mentioned" in out
    assert "Phase 1 gate: BLOCKED" not in out


def test_tooling_record_missing_is_rejected_even_with_no_blocker_prose():
    broken = copy.deepcopy(COMPLETE)
    del broken["tooling"]
    assert failures_for(broken, "tooling-blockers-resolved")


def test_tooling_not_checked_is_rejected():
    broken = copy.deepcopy(COMPLETE)
    broken["tooling"]["checked"] = False
    assert any("not recorded as run" in f for f in failures_for(broken, "tooling-blockers-resolved"))


def test_nothing_missing_needs_the_affirmative_none_missing_branch():
    broken = copy.deepcopy(COMPLETE)
    broken["tooling"]["none_missing"] = False
    assert failures_for(broken, "tooling-blockers-resolved")


@pytest.mark.parametrize(
    "resolution,extra",
    [
        ("installed", {}),
        ("installation_proposed", {}),
        ("operator_declined", {}),
        ("alternative_found", {"alternative": "git-remote-hg"}),
    ],
)
def test_each_accepted_resolution_passes(resolution, extra):
    repaired = copy.deepcopy(COMPLETE)
    repaired["findings"][0]["answer"] = "hg: command not found, so mercurial was installed."
    repaired["tooling"] = {
        "checked": True,
        "none_missing": False,
        "missing": [
            {"tool": "hg", "resolution": resolution, "detail": "brew install mercurial", **extra}
        ],
    }
    assert not failures_for(repaired, "tooling-blockers-resolved")


def test_designed_around_is_not_an_accepted_resolution():
    broken = copy.deepcopy(COMPLETE)
    broken["tooling"] = {
        "checked": True,
        "none_missing": False,
        "missing": [{"tool": "hg", "resolution": "designed_around", "detail": "used git only"}],
    }
    assert any("resolution not one of" in f for f in failures_for(broken, "tooling-blockers-resolved"))


def test_alternative_found_must_name_the_alternative():
    broken = copy.deepcopy(COMPLETE)
    broken["tooling"] = {
        "checked": True,
        "none_missing": False,
        "missing": [{"tool": "hg", "resolution": "alternative_found", "detail": "used a plugin"}],
    }
    assert any("alternative" in f for f in failures_for(broken, "tooling-blockers-resolved"))


def test_missing_entry_needs_a_named_tool_and_detail():
    broken = copy.deepcopy(COMPLETE)
    broken["tooling"] = {
        "checked": True,
        "none_missing": False,
        "missing": [{"tool": "   ", "resolution": "installed", "detail": ""}],
    }
    failures = failures_for(broken, "tooling-blockers-resolved")
    assert any("tool" in f for f in failures)
    assert any("detail" in f for f in failures)


def advisories_for(data: dict) -> list[str]:
    return dict((n, a(data)) for n, a in checker.ADVISORIES)["tooling-blockers-mentioned"]


def test_blocker_prose_is_accepted_once_the_tooling_record_accounts_for_it():
    repaired = copy.deepcopy(COMPLETE)
    repaired["findings"][0]["answer"] = "ripgrep was not installed; installed it with brew."
    repaired["tooling"] = {
        "checked": True,
        "none_missing": False,
        "missing": [{"tool": "ripgrep", "resolution": "installed", "detail": "brew install ripgrep"}],
    }
    assert not failures_for(repaired, "tooling-blockers-resolved")
    assert not advisories_for(repaired)


@pytest.mark.parametrize(
    "prose",
    [
        "The `strict` config option is not available in v2 of the parser.",
        "The upstream mirror is currently unavailable, per the status page.",
        "The `retries` field is missing from the serialized payload.",
        "We couldn't find any caller of this helper outside the tests.",
        "No such command exists in the CLI's public surface, per docs/cli.md.",
        "The vendored copy is not installed into site-packages by the build.",
    ],
)
def test_prose_findings_are_not_read_as_tooling_blockers(prose):
    """Legitimate findings that use blocker-shaped words are not flagged."""
    artifact = copy.deepcopy(COMPLETE)
    artifact["findings"][0]["answer"] = prose
    assert not advisories_for(artifact)
