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
