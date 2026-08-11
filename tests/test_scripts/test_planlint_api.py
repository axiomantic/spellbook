"""Tests for spellbook.planlint.api — the three call-site entry points, the
schema gate, phase behavior, fail-open/fail-closed, and BaseException
propagation through the error barrier (design §5.2/§5.3, §9.10).
"""

from pathlib import Path

import pytest
import tripwire

from spellbook.planlint import api, registry
from spellbook.planlint.document import PlanDocument
from spellbook.planlint.finding import ERROR, INFO, WARNING, Finding

FIXTURES = Path(__file__).parent / "fixtures" / "planlint"

RULE_NAMES = frozenset(
    {"structure", "depends", "checks", "consistency", "files", "ownership", "schema"}
)


def test_declares_schema_true_for_planlint_v1_text():
    assert api.declares_schema("**Schema:** planlint-v1\n\n### Task 1: X\n") is True


def test_declares_schema_false_for_text_with_no_schema_field():
    assert api.declares_schema("### Task 1: X\n\n**Files:**\n- Create: `x.py`\n") is False


def test_declares_schema_false_for_explicit_legacy_opt_out():
    assert api.declares_schema("**Schema:** legacy\n\n### Task 1: X\n") is False


def test_declares_schema_true_for_an_unknown_planlint_version():
    """The gate is FAMILY-wide, not marker-exact. `planlint-v2` opts IN, so
    rules/schema.py can report it as unknown. A marker-exact gate would route
    it to the legacy skip path, where no rule runs — making
    `schema-unknown-version` unreachable in production and giving an
    unrecognized schema the same silent pass a legacy plan gets."""
    assert api.declares_schema("**Schema:** planlint-v2\n\n### Task 1: X\n") is True


def test_declares_schema_false_for_a_value_outside_the_planlint_family():
    assert api.declares_schema("**Schema:** some-other-tool-v3\n\n### Task 1: X\n") is False


def test_declares_schema_ignores_a_schema_line_inside_a_fenced_block():
    """The gate and PlanDocument._resolve_plan_schema must read the same
    document. A `Schema:` line inside a CLOSED fence is an example, not a
    declaration — a plan ABOUT plans would otherwise be gated in and then
    parsed as carrying no schema."""
    text = (
        "# A plan that shows an example plan\n\n"
        "```markdown\n"
        "**Schema:** planlint-v1\n"
        "```\n\n"
        "### Task 1: X\n\n**Files:**\n- Create: `x.py`\n"
    )
    assert api.declares_schema(text) is False
    assert api.lint_text(text).linted is False


def test_declares_schema_builds_no_document():
    """A pure line-scan; PlanDocument.from_text must not be called for a
    legacy plan. Verified via tripwire (AGENTS.md: tripwire is the only
    acceptable mocking framework; monkeypatch.setattr is restricted to
    environment/cwd/sys.path only). `.required(False)` lets the mock stay
    unused without tripping tripwire's unused-mock guard — the whole point
    of this test is that the mock is NEVER called; if it fires at all, the
    configured `.raises()` turns that into a test failure."""
    from_text_mock = tripwire.mock.object(PlanDocument, "from_text")
    from_text_mock.__call__.required(False).raises(AssertionError("should not be called"))
    with tripwire:
        assert api.declares_schema("no schema field here\n") is False


def test_lint_text_builds_no_document_for_a_legacy_plan():
    """The cost contract of design §6.1/§8.1: on a False gate there is ZERO
    further work — including no document built merely to phrase the skip
    reason. This is the assertion that keeps the 75 in-flight legacy plans
    free, and it is the one a later 'just probe the doc for a nicer message'
    refactor would break."""
    from_text_mock = tripwire.mock.object(PlanDocument, "from_text")
    from_text_mock.__call__.required(False).raises(AssertionError("should not be called"))
    with tripwire:
        report = api.lint_text("### Task 1: X\n\n**Files:**\n- Create: `x.py`\n")
    assert report.linted is False
    assert report.skip_reason == "no Schema: field (legacy plan)"


def test_lint_text_on_a_legacy_plan_returns_unlinted_report():
    report = api.lint_text("### Task 1: X\n\n**Files:**\n- Create: `x.py`\n")
    assert report.linted is False
    assert report.skip_reason == "no Schema: field (legacy plan)"
    assert report.results == ()
    assert report.internal_errors == ()
    assert report.findings == ()


def test_lint_text_on_an_opted_out_plan_returns_unlinted_report():
    report = api.lint_text("**Schema:** legacy\n\n### Task 1: X\n")
    assert report.linted is False
    assert report.skip_reason == "Schema: legacy (explicit opt-out)"


def test_lint_text_on_a_value_outside_the_planlint_family_returns_unlinted_report():
    report = api.lint_text("**Schema:** some-other-tool-v3\n\n### Task 1: X\n")
    assert report.linted is False
    assert report.skip_reason == "Schema: some-other-tool-v3 (not a planlint schema)"


def test_an_unknown_planlint_version_is_linted_and_fires_schema_unknown_version():
    """The reachability assertion for `schema-unknown-version` (Task 11).

    Task 11 tests that rule by calling `schema.run` DIRECTLY, which proves the
    rule body works but says nothing about whether any production call path
    reaches it. This test is the one that decides that: it goes through
    `lint_text`, the real gate, and asserts BOTH that the plan was linted and
    that the finding came out. Delete the family gate and this test goes red;
    delete only the direct rule test and it stays green — which is why both
    exist."""
    text = (
        "**Schema:** planlint-v2\n\n"
        "### Task 1: A\n\n**Files:**\n- Create: `a.py`\n\n"
        "**Depends:** none\n\n**Check:** `pytest a`\n"
    )
    report = api.lint_text(text)
    assert report.linted is True
    assert report.skip_reason == ""
    hits = [f for f in report.findings if f.rule == "schema-unknown-version"]
    assert len(hits) == 1
    assert "planlint-v2" in hits[0].evidence


def test_lint_text_on_a_schema_v1_plan_runs_all_rules():
    text = (FIXTURES / "clean_plan.md").read_text(encoding="utf-8")
    report = api.lint_text(text, name="clean_plan.md")
    assert report.linted is True
    assert report.skip_reason == ""
    assert len(report.results) == 7  # seven rule modules
    assert {r.name for r in report.results} == RULE_NAMES


def test_lint_text_on_a_v1_plan_with_zero_tasks_reports_no_input_error():
    report = api.lint_text("**Schema:** planlint-v1\n\nNo tasks here at all.\n")
    assert report.linted is True
    assert report.failed is True
    no_input_hits = [f for f in report.findings if f.rule == "no-input"]
    # six of seven rules emit no-input on a zero-task plan; `files` has
    # nothing to say about a task-free plan (no Files: bullets to examine).
    assert len(no_input_hits) == 6


def test_lint_path_on_a_missing_file_returns_unlinted_not_an_exception(tmp_path):
    report = api.lint_path(tmp_path / "does_not_exist.md")
    assert report.linted is False
    assert "unreadable" in report.skip_reason


def test_lint_path_on_a_real_file(tmp_path):
    plan = tmp_path / "clean.md"
    plan.write_text((FIXTURES / "clean_plan.md").read_text(encoding="utf-8"), encoding="utf-8")
    report = api.lint_path(plan)
    assert report.linted is True
    assert report.plan == str(plan)


def test_lint_for_authoring_turns_on_create_path_exists_as_warning(tmp_path):
    (tmp_path / "spellbook").mkdir()
    (tmp_path / "spellbook" / "sample").mkdir()
    (tmp_path / "spellbook" / "sample" / "first.py").write_text("# x\n", encoding="utf-8")
    plan = tmp_path / "clean.md"
    plan.write_text((FIXTURES / "clean_plan.md").read_text(encoding="utf-8"), encoding="utf-8")
    report = api.lint_for_authoring(plan, repo_root=tmp_path)
    hits = [f for f in report.findings if f.rule == "create-path-exists"]
    assert len(hits) == 1
    assert hits[0].severity == WARNING
    assert hits[0].task == "Task 1"
    assert (
        hits[0].message
        == "a `Create:` path already exists; this is almost always a mislabeled `Modify:`"
    )


def test_lint_for_review_downgrades_create_path_exists_to_info(tmp_path):
    (tmp_path / "spellbook").mkdir()
    (tmp_path / "spellbook" / "sample").mkdir()
    (tmp_path / "spellbook" / "sample" / "first.py").write_text("# x\n", encoding="utf-8")
    plan = tmp_path / "clean.md"
    plan.write_text((FIXTURES / "clean_plan.md").read_text(encoding="utf-8"), encoding="utf-8")
    report = api.lint_for_review(plan, repo_root=tmp_path)
    hits = [f for f in report.findings if f.rule == "create-path-exists"]
    assert len(hits) == 1
    assert hits[0].severity == INFO


def test_lint_on_write_returns_none_for_a_legacy_plan(tmp_path):
    plan = tmp_path / "legacy.md"
    text = "### Task 1: X\n\n**Files:**\n- Create: `x.py`\n"
    report = api.lint_on_write(plan, text, repo_root=tmp_path)
    assert report is None


def test_lint_on_write_runs_with_create_path_exists_off(tmp_path):
    (tmp_path / "spellbook").mkdir()
    (tmp_path / "spellbook" / "sample").mkdir()
    (tmp_path / "spellbook" / "sample" / "first.py").write_text("# x\n", encoding="utf-8")
    text = (FIXTURES / "clean_plan.md").read_text(encoding="utf-8")
    report = api.lint_on_write(tmp_path / "clean.md", text, repo_root=tmp_path)
    assert report is not None
    assert [f for f in report.findings if f.rule == "create-path-exists"] == []


def test_plan_lint_report_failed_is_true_on_a_crash_even_with_no_findings():
    def crashing(ctx):
        raise RuntimeError("synthetic crash")

    crash_rule = registry.Rule(
        name="crasher", run=crashing, emits=frozenset(), phases=frozenset(api.Phase)
    )
    rules_mock = tripwire.mock("spellbook.planlint.registry:_rules")
    rules_mock.returns((crash_rule,))
    with tripwire:
        report = api.lint_text(
            "**Schema:** planlint-v1\n\n### Task 1: X\n\n**Files:**\n- Create: `x.py`\n"
        )
    rules_mock.assert_call(args=(), kwargs={})
    assert report.findings == ()
    assert report.failed is True
    assert len(report.internal_errors) == 1
    assert report.internal_errors[0].rule == "crasher"
    assert report.internal_errors[0].exc_type == "RuntimeError"
    assert report.internal_errors[0].message == "synthetic crash"


def test_barrier_propagates_keyboardinterrupt():
    def interrupting(ctx):
        raise KeyboardInterrupt()

    dummy = registry.Rule(
        name="dummy", run=interrupting, emits=frozenset(), phases=frozenset(api.Phase)
    )
    rules_mock = tripwire.mock("spellbook.planlint.registry:_rules")
    rules_mock.returns((dummy,))
    with tripwire, pytest.raises(KeyboardInterrupt):
        api.lint_text("**Schema:** planlint-v1\n\n### Task 1: X\n\n**Files:**\n- Create: `x.py`\n")
    rules_mock.assert_call(args=(), kwargs={})


def test_decided_claims_reports_ran_rules_as_decided():
    text = (FIXTURES / "clean_plan.md").read_text(encoding="utf-8")
    report = api.lint_text(text)
    claims = api.decided_claims(report)
    assert len(claims) == 7
    names = {c.rule for c in claims}
    assert names == RULE_NAMES
    assert all(c.decided is True for c in claims if c.rule != "files")


def test_decided_claims_reports_skipped_rule_as_undecided():
    text = (FIXTURES / "clean_plan.md").read_text(encoding="utf-8")
    report = api.lint_text(text, repo_root=None)
    claims = api.decided_claims(report)
    files_claim = next(c for c in claims if c.rule == "files")
    assert files_claim.decided is False
    assert files_claim.finding_count == 0
    assert files_claim.reason == "no repo_root supplied"


def test_summary_line_is_one_line():
    text = (FIXTURES / "clean_plan.md").read_text(encoding="utf-8")
    report = api.lint_text(text)
    assert "\n" not in report.summary_line()


# --------------------------------------------------------- H1: no-rules-ran


def test_lint_text_with_a_phase_matching_no_rule_reports_no_rules_ran():
    text = (FIXTURES / "clean_plan.md").read_text(encoding="utf-8")
    report = api.lint_text(text, phase=None)
    assert report.linted is True
    assert report.failed is True
    assert len(report.results) == 1
    assert report.results[0].name == "no-rules-ran"
    hits = [f for f in report.findings if f.rule == "no-rules-ran"]
    assert len(hits) == 1
    assert hits[0] == api.NO_RULES_RAN
    assert hits[0].severity == api.ERROR
    assert hits[0].message == "phase matched zero registered rules; nothing was checked"


def test_lint_path_with_a_phase_matching_no_rule_reports_no_rules_ran(tmp_path):
    plan = tmp_path / "clean.md"
    plan.write_text((FIXTURES / "clean_plan.md").read_text(encoding="utf-8"), encoding="utf-8")
    report = api.lint_path(plan, phase=None)
    assert report.linted is True
    assert report.failed is True
    assert len(report.results) == 1
    assert report.results[0].name == "no-rules-ran"
    assert report.findings == (api.NO_RULES_RAN,)


# ------------------------------------------------- H2: gate/parser agreement


# A CRLF-only variant of this test was removed: `split("\n")` on `\r\n` text
# still splits correctly line-by-line (the trailing `\r` lands at end-of-line
# and gets absorbed by `.strip()` downstream), so a CRLF-only scenario passes
# against the OLD buggy line-splitting gate just as well as the fixed one and
# proves nothing about the fix. `test_gate_and_lint_text_agree_on_bare_cr_line_endings`
# below is the regression test that actually distinguishes old vs new behavior,
# since a bare `\r` line ending is exactly what `split("\n")` fails to split on.


def test_gate_and_lint_text_agree_on_bare_cr_line_endings():
    text = (
        "**Schema:** planlint-v1\r\r"
        "### Task 1: A\r\r**Files:**\r- Create: `a.py`\r\r"
        "**Depends:** none\r\r**Check:** `pytest a`\r"
    )
    assert api.declares_schema(text) is True
    report = api.lint_text(text)
    assert report.linted is True
    assert report.skip_reason == ""


def test_skip_reason_truncates_an_overly_long_schema_value():
    huge_value = "x" * 500
    text = f"**Schema:** {huge_value}\n\n### Task 1: X\n"
    report = api.lint_text(text)
    assert report.linted is False
    assert report.skip_reason == f"Schema: {huge_value[:50]}... (not a planlint schema)"


# --------------------------------------------------------- M1: summary_line


def test_summary_line_reports_skipped_rules_when_a_rule_is_undecided():
    text = (FIXTURES / "clean_plan.md").read_text(encoding="utf-8")
    report = api.lint_text(text, repo_root=None)
    assert report.failed is False
    line = report.summary_line()
    assert line == f"{report.plan}: clean (6 of 7 rule(s) decided, 1 skipped, 0 findings)"


# --------------------------------------------------- M2: decided_claims crash


def test_decided_claims_reports_a_crashed_rule_as_undecided_with_a_reason():
    def crashing(ctx):
        raise KeyError("boom")

    crash_rule = registry.Rule(
        name="crasher", run=crashing, emits=frozenset(), phases=frozenset(api.Phase)
    )
    rules_mock = tripwire.mock("spellbook.planlint.registry:_rules")
    rules_mock.returns((crash_rule,))
    with tripwire:
        report = api.lint_text(
            "**Schema:** planlint-v1\n\n### Task 1: X\n\n**Files:**\n- Create: `x.py`\n"
        )
    rules_mock.assert_call(args=(), kwargs={})
    claims = api.decided_claims(report)
    assert claims == (
        api.DecidedClaim(
            rule="crasher",
            decided=False,
            finding_count=0,
            reason="crashed: KeyError: 'boom'",
        ),
    )


# --------------------------------------------------------------------- M3


def test_report_on_an_unlinted_plan():
    report = api.lint_text("### Task 1: X\n\n**Files:**\n- Create: `x.py`\n")
    assert report.report() == "<text>: not linted (no Schema: field (legacy plan))\n"


def test_report_with_findings_includes_per_rule_report_text():
    report = api.lint_text("**Schema:** planlint-v1\n\nNo tasks here at all.\n")
    assert report.report() == (
        "structure: 1 finding(s) (0 task bodies examined)\n"
        "  [ERROR] no-input\n"
        "      the structure lint examined 0 task bodies\n"
        "depends: 1 finding(s) (0 task blocks examined)\n"
        "  [ERROR] no-input\n"
        "      the depends lint examined 0 task blocks\n"
        "checks: 1 finding(s) (0 task blocks examined)\n"
        "  [ERROR] no-input\n"
        "      the checks lint examined 0 task blocks\n"
        "consistency: 1 finding(s) (0 task blocks examined)\n"
        "  [ERROR] no-input\n"
        "      the consistency lint examined 0 task blocks\n"
        "files: skipped (no repo_root supplied)\n"
        "ownership: 1 finding(s) (0 task blocks examined)\n"
        "  [ERROR] no-input\n"
        "      the ownership lint examined 0 task blocks\n"
        "schema: 1 finding(s) (0 task blocks examined)\n"
        "  [ERROR] no-input\n"
        "      the schema lint examined 0 task blocks\n"
    )


def test_report_with_crashes_includes_crash_traceback():
    def crashing(ctx):
        raise KeyError("boom")

    crash_rule = registry.Rule(
        name="crasher", run=crashing, emits=frozenset(), phases=frozenset(api.Phase)
    )
    rules_mock = tripwire.mock("spellbook.planlint.registry:_rules")
    rules_mock.returns((crash_rule,))
    with tripwire:
        report = api.lint_text(
            "**Schema:** planlint-v1\n\n### Task 1: X\n\n**Files:**\n- Create: `x.py`\n"
        )
    rules_mock.assert_call(args=(), kwargs={})
    text = report.report()
    assert "crasher: CRASHED (KeyError: 'boom')" in text
    assert "Traceback" in text


def test_errors_property_returns_only_error_severity_findings():
    report = api.lint_text("**Schema:** planlint-v1\n\nNo tasks here at all.\n")
    assert report.errors == (
        Finding(
            rule="no-input",
            message="the structure lint examined 0 task bodies",
            severity=ERROR,
        ),
        Finding(
            rule="no-input",
            message="the depends lint examined 0 task blocks",
            severity=ERROR,
        ),
        Finding(
            rule="no-input",
            message="the checks lint examined 0 task blocks",
            severity=ERROR,
        ),
        Finding(
            rule="no-input",
            message="the consistency lint examined 0 task blocks",
            severity=ERROR,
        ),
        Finding(
            rule="no-input",
            message="the ownership lint examined 0 task blocks",
            severity=ERROR,
        ),
        Finding(
            rule="no-input",
            message="the schema lint examined 0 task blocks",
            severity=ERROR,
        ),
    )


def test_lint_path_on_a_non_utf8_file_returns_unlinted_not_an_exception(tmp_path):
    plan = tmp_path / "bad.md"
    plan.write_bytes(b"\xff\xfe not utf-8 at all")
    report = api.lint_path(plan)
    assert report.linted is False
    assert report.skip_reason == "not UTF-8"


def test_decided_claim_finding_count_for_a_rule_that_actually_fires():
    report = api.lint_text("**Schema:** planlint-v1\n\nNo tasks here at all.\n")
    claims = api.decided_claims(report)
    structure_claim = next(c for c in claims if c.rule == "structure")
    assert structure_claim.decided is True
    assert structure_claim.finding_count >= 1
    assert structure_claim.finding_count == len(
        next(r for r in report.results if r.name == "structure").findings
    )
