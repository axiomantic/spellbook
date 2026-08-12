"""Tests for spellbook.planlint.finding — Finding, LintResult, guard_no_input.

Ported near-verbatim from nmg2-tools/planlint/finding.py. No mocking: real
dataclass instances only.
"""

from spellbook.planlint.finding import (
    ERROR,
    WARNING,
    SEVERITY_ORDER,
    Finding,
    LintResult,
    guard_no_input,
)


def test_severity_order_ranks_error_before_warning_before_info():
    assert SEVERITY_ORDER["ERROR"] < SEVERITY_ORDER["WARNING"] < SEVERITY_ORDER["INFO"]


def test_finding_defaults_to_error_severity():
    f = Finding(rule="x", message="y")
    assert f.severity == ERROR
    assert f.task == ""
    assert f.line == 0


def test_lint_result_failed_is_true_when_findings_present():
    result = LintResult(name="r", findings=[Finding(rule="x", message="y")], examined=1)
    assert result.failed is True


def test_lint_result_failed_is_false_when_no_findings():
    result = LintResult(name="r", findings=[], examined=1)
    assert result.failed is False


def test_lint_result_report_is_clean_message_when_no_findings():
    result = LintResult(name="r", findings=[], examined=3, examined_label="tasks")
    assert result.report() == "r: clean (3 tasks examined)\n"


def test_lint_result_report_orders_by_severity_rule_task_line():
    findings = [
        Finding(rule="b", severity=ERROR, task="Task 1", line=1, message="m-b1"),
        Finding(rule="a", severity=ERROR, task="Task 2", line=1, message="m-a2"),
        Finding(rule="a", severity=ERROR, task="Task 1", line=5, message="m-a1-5"),
        Finding(rule="a", severity=ERROR, task="Task 1", line=1, message="m-a1-1"),
    ]
    result = LintResult(name="r", findings=findings, examined=4)
    expected = (
        "r: 4 finding(s) (4 inputs examined)\n"
        "  [ERROR] a  Task 1  line 1\n"
        "      m-a1-1\n"
        "  [ERROR] a  Task 1  line 5\n"
        "      m-a1-5\n"
        "  [ERROR] a  Task 2  line 1\n"
        "      m-a2\n"
        "  [ERROR] b  Task 1  line 1\n"
        "      m-b1\n"
    )
    assert result.report() == expected


def test_guard_no_input_adds_no_input_error_when_examined_is_zero():
    result = guard_no_input("mylint", [], 0, "task blocks", "mylint")
    assert result.failed is True
    assert result.findings[0] == Finding(
        rule="no-input",
        message="the mylint examined 0 task blocks",
        severity=ERROR,
    )


def test_guard_no_input_passes_through_when_examined_is_nonzero():
    result = guard_no_input("mylint", [], 3, "task blocks", "mylint")
    assert result.failed is False
    assert result.examined == 3
    assert result.findings == []
    assert result.name == "mylint"
    assert result.examined_label == "task blocks"


def test_lint_result_report_is_skipped_message_when_skipped_reason_is_set():
    result = LintResult(name="files", findings=[], examined=0, skipped_reason="some reason")
    assert result.report() == "files: skipped (some reason)\n"


def test_lint_result_report_shows_skip_reason_and_findings_when_both_present():
    """L2 regression: `skipped_reason` and `findings` are not mutually
    exclusive in the dataclass's shape. When both are present, `report()`
    must show the skip reason AND the findings — never silently dropping
    either."""
    findings = [Finding(rule="x", message="m", severity=ERROR)]
    result = LintResult(
        name="r", findings=findings, examined=1, skipped_reason="why", examined_label="tasks"
    )
    assert result.report() == (
        "r: skipped (why)\n"
        "r: 1 finding(s) (1 tasks examined)\n"
        "  [ERROR] x\n"
        "      m\n"
    )
