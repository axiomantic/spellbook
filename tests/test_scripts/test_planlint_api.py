"""Tests for spellbook.planlint.api — the three call-site entry points, the
schema gate, phase behavior, fail-open/fail-closed, and BaseException
propagation through the error barrier (design §5.2/§5.3, §9.10).
"""

from pathlib import Path

import pytest

from spellbook.planlint import api, registry

FIXTURES = Path(__file__).parent / "fixtures" / "planlint"


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


def test_declares_schema_builds_no_document(monkeypatch):
    """A pure line-scan; PlanDocument.from_text must not be called for a
    legacy plan. Verified by monkeypatching from_text to raise."""
    import spellbook.planlint.document as document_module

    monkeypatch.setattr(
        document_module.PlanDocument,
        "from_text",
        staticmethod(
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not be called"))
        ),
    )
    assert api.declares_schema("no schema field here\n") is False


def test_lint_text_builds_no_document_for_a_legacy_plan(monkeypatch):
    """The cost contract of design §6.1/§8.1: on a False gate there is ZERO
    further work — including no document built merely to phrase the skip
    reason. This is the assertion that keeps the 75 in-flight legacy plans
    free, and it is the one a later 'just probe the doc for a nicer message'
    refactor would break."""
    import spellbook.planlint.document as document_module

    monkeypatch.setattr(
        document_module.PlanDocument,
        "from_text",
        staticmethod(
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not be called"))
        ),
    )
    report = api.lint_text("### Task 1: X\n\n**Files:**\n- Create: `x.py`\n")
    assert report.linted is False
    assert "legacy" in report.skip_reason


def test_lint_text_on_a_legacy_plan_returns_unlinted_report():
    report = api.lint_text("### Task 1: X\n\n**Files:**\n- Create: `x.py`\n")
    assert report.linted is False
    assert "legacy" in report.skip_reason


def test_lint_text_on_an_opted_out_plan_returns_unlinted_report():
    report = api.lint_text("**Schema:** legacy\n\n### Task 1: X\n")
    assert report.linted is False
    assert "opt-out" in report.skip_reason


def test_lint_text_on_a_value_outside_the_planlint_family_returns_unlinted_report():
    report = api.lint_text("**Schema:** some-other-tool-v3\n\n### Task 1: X\n")
    assert report.linted is False
    assert "not a planlint schema" in report.skip_reason


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


def test_lint_text_on_a_v1_plan_with_zero_tasks_reports_no_input_error():
    report = api.lint_text("**Schema:** planlint-v1\n\nNo tasks here at all.\n")
    assert report.linted is True
    assert report.failed is True
    assert any(f.rule == "no-input" for f in report.findings)


def test_lint_path_on_a_missing_file_returns_unlinted_not_an_exception(tmp_path):
    report = api.lint_path(tmp_path / "does_not_exist.md")
    assert report.linted is False
    assert "unreadable" in report.skip_reason


def test_lint_path_on_a_real_file(tmp_path):
    plan = tmp_path / "clean.md"
    plan.write_text((FIXTURES / "clean_plan.md").read_text(encoding="utf-8"), encoding="utf-8")
    report = api.lint_path(plan)
    assert report.linted is True


def test_lint_for_authoring_turns_on_create_path_exists_as_warning(tmp_path):
    from spellbook.planlint.finding import WARNING

    (tmp_path / "spellbook").mkdir()
    (tmp_path / "spellbook" / "sample").mkdir()
    (tmp_path / "spellbook" / "sample" / "first.py").write_text("# x\n", encoding="utf-8")
    plan = tmp_path / "clean.md"
    plan.write_text((FIXTURES / "clean_plan.md").read_text(encoding="utf-8"), encoding="utf-8")
    report = api.lint_for_authoring(plan, repo_root=tmp_path)
    hits = [f for f in report.findings if f.rule == "create-path-exists"]
    assert len(hits) == 1
    assert hits[0].severity == WARNING


def test_lint_for_review_downgrades_create_path_exists_to_info(tmp_path):
    from spellbook.planlint.finding import INFO

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


def test_plan_lint_report_failed_is_true_on_a_crash_even_with_no_findings(monkeypatch):
    def crashing(ctx):
        raise RuntimeError("synthetic crash")

    crash_rule = registry.Rule(
        name="crasher", run=crashing, emits=frozenset(), phases=frozenset(api.Phase)
    )
    monkeypatch.setattr(registry, "RULES", (crash_rule,))
    report = api.lint_text("**Schema:** planlint-v1\n\n### Task 1: X\n\n**Files:**\n- Create: `x.py`\n")
    assert report.findings == ()
    assert report.failed is True
    assert len(report.internal_errors) == 1


def test_barrier_propagates_keyboardinterrupt(monkeypatch):
    def interrupting(ctx):
        raise KeyboardInterrupt()

    dummy = registry.Rule(
        name="dummy", run=interrupting, emits=frozenset(), phases=frozenset(api.Phase)
    )
    monkeypatch.setattr(registry, "RULES", (dummy,))
    with pytest.raises(KeyboardInterrupt):
        api.lint_text("**Schema:** planlint-v1\n\n### Task 1: X\n\n**Files:**\n- Create: `x.py`\n")


def test_decided_claims_reports_ran_rules_as_decided():
    text = (FIXTURES / "clean_plan.md").read_text(encoding="utf-8")
    report = api.lint_text(text)
    claims = api.decided_claims(report)
    assert len(claims) == 7
    names = {c.rule for c in claims}
    assert "structure" in names


def test_decided_claims_reports_skipped_rule_as_undecided(tmp_path):
    text = (FIXTURES / "clean_plan.md").read_text(encoding="utf-8")
    report = api.lint_text(text, repo_root=None)
    claims = api.decided_claims(report)
    files_claim = next(c for c in claims if c.rule == "files")
    assert files_claim.decided is False


def test_summary_line_is_one_line():
    text = (FIXTURES / "clean_plan.md").read_text(encoding="utf-8")
    report = api.lint_text(text)
    assert "\n" not in report.summary_line()
