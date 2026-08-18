"""Behavioural tests for the Phase 1.5 understanding-document checker.

Each test pins a document that MUST be rejected against the same document
repaired, so a check that degenerates into "always pass" fails here. The
old form of this gate was markdown pseudocode nobody executed; a checker
that cannot be shown to reject anything would reproduce that defect in a
language that merely looks executable.

Stated blind spot: these tests prove the checker distinguishes a
structurally complete document from an incomplete one. They say nothing
about whether the content of a passing document is CORRECT -- that half of
the old checklist is labelled self-assessment in `feature-discover.md`.
"""

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_understanding_doc.py"

_spec = importlib.util.spec_from_file_location("check_understanding_doc", SCRIPT)
assert _spec and _spec.loader
checker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checker)


COMPLETE_DOC = """# Understanding Document: Widget Sync

## Feature Essence
Sync widgets between the local store and the remote API.

## Research Summary
- Patterns discovered: repository pattern in src/store
- Integration points: src/api/client.py
- Constraints identified: rate limit of 10 req/s

## Architectural Approach
Pull-based reconciliation on a timer.
Alternatives considered: push webhooks, rejected for firewall reasons.

## Scope Definition

IN SCOPE:
- Widget create and update sync

EXPLICITLY OUT OF SCOPE:
- Widget deletion sync

MVP DEFINITION:
One-way sync from remote to local.

## Integration Plan
- Integrates with: src/api/client.py
- Follows patterns: repository pattern
- Interfaces: WidgetRepository.sync()

## Failure Modes & Edge Cases
- Remote returns 429 mid-page

## Success Criteria
- Sync latency: under 5 seconds
- Conflict rate: below 1 percent

## Glossary
- Widget: a synchronised record

## Validated Assumptions
- Rate limit is 10 req/s: confirmed against api docs by operator

## Project Standards (Discovered Governance Docs)
- Searched: yes
- Globs used: AGENTS.md, docs/*.md
- Sources found: AGENTS.md — conventions — top-level imports required
- None found: false
"""


def failures_for(text: str) -> dict[str, list[str]]:
    return {name: found for name, found in checker.run_checks(text) if found}


def test_complete_document_passes_every_check():
    assert failures_for(COMPLETE_DOC) == {}


def test_missing_required_section_is_rejected():
    mutated = COMPLETE_DOC.replace("## Failure Modes & Edge Cases", "## Notes")
    assert "required-sections" in failures_for(mutated)


def test_empty_section_is_rejected():
    mutated = COMPLETE_DOC.replace("- Remote returns 429 mid-page", "[...]")
    assert "sections-non-empty" in failures_for(mutated)


def test_missing_out_of_scope_block_is_rejected():
    mutated = COMPLETE_DOC.replace(
        "EXPLICITLY OUT OF SCOPE:\n- Widget deletion sync\n", ""
    )
    assert "scope-boundaries" in failures_for(mutated)


def test_empty_scope_block_is_rejected():
    mutated = COMPLETE_DOC.replace("- Widget deletion sync", "[...]")
    assert "scope-boundaries" in failures_for(mutated)


def test_success_criterion_without_threshold_is_rejected():
    mutated = COMPLETE_DOC.replace("- Sync latency: under 5 seconds", "- Sync latency:")
    assert "success-criteria-thresholds" in failures_for(mutated)


@pytest.mark.parametrize("marker", ["TBD", "to be determined", "figure it out later"])
def test_deferral_markers_are_rejected(marker):
    mutated = COMPLETE_DOC.replace("under 5 seconds", marker)
    assert "no-deferrals" in failures_for(mutated)


def test_unrun_standards_sweep_is_rejected():
    mutated = COMPLETE_DOC.replace("- Searched: yes", "- Searched: no")
    assert "project-standards-recorded" in failures_for(mutated)


def test_empty_sweep_without_globs_is_rejected():
    mutated = COMPLETE_DOC.replace(
        "- Globs used: AGENTS.md, docs/*.md", "- Globs used: [...]"
    ).replace(
        "- Sources found: AGENTS.md — conventions — top-level imports required",
        "- Sources found: [...]",
    ).replace("- None found: false", "- None found: true")
    assert "project-standards-recorded" in failures_for(mutated)


def test_empty_sweep_with_recorded_globs_is_accepted():
    mutated = COMPLETE_DOC.replace(
        "- Sources found: AGENTS.md — conventions — top-level imports required",
        "- Sources found: [...]",
    ).replace("- None found: false", "- None found: true")
    assert "project-standards-recorded" not in failures_for(mutated)


def test_exit_status_is_the_gate(tmp_path):
    good = tmp_path / "good.md"
    good.write_text(COMPLETE_DOC, encoding="utf-8")
    assert checker.main([str(good)]) == 0

    bad = tmp_path / "bad.md"
    bad.write_text(COMPLETE_DOC.replace("## Success Criteria", "## Hopes"), encoding="utf-8")
    assert checker.main([str(bad)]) == 1

    assert checker.main([str(tmp_path / "absent.md")]) == 2
