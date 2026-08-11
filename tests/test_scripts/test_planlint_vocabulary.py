"""Checkability self-application (design §9): every mechanically decidable
claim the design document makes about this port, decided by a check here.

9.1 — zero source-tool vocabulary in the ported engine.
9.2 — no call site (outside cli.py) spawns a subprocess.
9.3 — no new packaging entry is needed.
9.4 — every rule has at least one mutation test.
9.5 — no rule emits a rule ID its own module does not declare.
9.7 — the registry's RULES tuple and each rule's returned name are consistent.
9.10 — the registry's error barrier wraps Exception, not BaseException.
9.11 — no third-party dependency.

9.8, 9.9 continue in Task 22 (after the SKILL.md edits exist).
"""

import ast
import re
import sys
from pathlib import Path

import spellbook.planlint

PACKAGE = Path(spellbook.planlint.__file__).parent
REPO_ROOT = PACKAGE.parents[1]


def _package_modules():
    """Every module the §9 checks scan — and a hard error when there are none.

    `finding.py` states the rule this helper enforces on the tests themselves:
    nothing to check is never a pass. Every check below ends in
    `assert <offenders> == {}`, which an empty scan satisfies trivially. If
    `PACKAGE` ever resolved somewhere without modules — a moved package, an
    import that resolved to a namespace package, a stale install — the checks
    would report green having examined nothing at all. So the file list is
    produced in one place and proven non-empty there.
    """
    modules = sorted(PACKAGE.rglob("*.py"))
    assert modules, f"no modules found under {PACKAGE}: the checks would pass vacuously"
    return modules


# ------------------------------------------------------------------ 9.1

# SCOPE, stated so the pass is not read as more than it is: this is an
# ENUMERATED DENYLIST, so a green run means "zero KNOWN source-tool
# vocabulary", never "zero source-tool vocabulary". Source-tool wording that
# no pattern below names passes unseen. The list is the check's definition of
# the claim, so widening the claim means adding a pattern.
VOCAB_PATTERNS = [
    re.compile(p)
    for p in (
        r"\bT[0-2]\b",
        r"CMake",
        r"CTest",
        r"ctest",
        r"gearmulator",
        r"g2Lib",
        r"g2JucePlugin",
        r"g2TestConsole",
        r"dsp56kEmu",
        r"\bREPO-[0-9]",
        r"\bDSP-[0-9]",
        r"registrar",
        r"milestone",
        # Catch-all for any track prefix beyond the two named above. The
        # `(?!UTF-)` exclusion is load-bearing, not cosmetic: `api.py` and
        # `cli.py` both carry the literal `"not UTF-8"` skip reason, which
        # has the exact PREFIX-DIGIT shape this pattern looks for. Without
        # the exclusion `test_the_ported_engine_carries_zero_source_tool_vocabulary`
        # fails on the package's own correct source — a false positive that
        # teaches a reader to loosen the check rather than fix a real hit.
        r"\b(?!UTF-)[A-Z]{2,6}-[0-9]",
        r"@[A-Z]{2,6}-",
        r"[Ss]ection 7\.",
        r"PENDING|CONDITIONAL|THROWAWAY|BLOCKED-ON-DESIGN",
    )
]


def _grep_package(patterns):
    hits = {}
    for path in _package_modules():
        text = path.read_text(encoding="utf-8")
        for pattern in patterns:
            if pattern.search(text):
                hits.setdefault(str(path.relative_to(REPO_ROOT)), []).append(pattern.pattern)
    return hits


def test_known_bad_input_the_grep_actually_matches_unparameterized_vocabulary():
    """The check is proven against a KNOWN-BAD input first: an
    unparameterized copy of graph.py carrying source-tool vocabulary must
    trip the grep, or the grep is not doing anything."""
    bad_source = (
        "IDENT_ONLY = re.compile(r'^[A-Z]{2,6}-\\d+$')\n"
        "MARKERS = ('PENDING', 'CONDITIONAL', 'WAVE', 'OPERATOR', "
        "'THROWAWAY', 'BLOCKED-ON-DESIGN')\n"
        "# see Section 7.6 assertion 2\n"
        "REGISTRAR_PATH = 'DSP-0'\n"
    )
    hits = [p.pattern for p in VOCAB_PATTERNS if p.search(bad_source)]
    assert hits, "the known-bad fixture must trip at least one vocabulary pattern"


def test_the_scanned_module_list_is_proven_non_empty(monkeypatch, tmp_path):
    """The guard against the vacuous pass, proven against a KNOWN-BAD input.

    Asserting `_package_modules()` is non-empty on the real package proves
    little — it would also hold if the assert inside were deleted. So point
    `PACKAGE` at an empty directory and require the helper to RAISE."""
    monkeypatch.setattr(sys.modules[__name__], "PACKAGE", tmp_path)
    try:
        _package_modules()
    except AssertionError:
        return
    raise AssertionError("_package_modules() accepted an empty scan")


def test_the_ported_engine_carries_zero_source_tool_vocabulary():
    hits = _grep_package(VOCAB_PATTERNS)
    assert hits == {}


# ------------------------------------------------------------------ 9.2

FORBIDDEN_SUBPROCESS_CALLS = frozenset({"run", "Popen", "check_output", "check_call", "call"})


def _walks_subprocess(tree):
    """Subprocess use in one module, RESOLVED to the subprocess module.

    Matching any call whose attribute happens to be named `run` is not a
    subprocess check — it is a check for the word "run". `registry.run_rules`
    dispatches with `rule.run(ctx)`, and `rules/*.py` each define `run`; every
    one of those would be reported as spawning a process. So the walk binds
    names first (what `import subprocess` and `from subprocess import ...`
    introduced) and only then reports calls that resolve to those bindings.
    Design §9.2 words the claim the same way: "no `Call` whose function
    attribute is `run`/`Popen`/`check_output` RESOLVED FROM `subprocess`".
    """
    module_aliases = set()  # names bound to the subprocess module itself
    imported_callables = set()  # names bound by `from subprocess import X`
    findings = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "subprocess" or alias.name.startswith("subprocess."):
                    module_aliases.add(alias.asname or alias.name.split(".")[0])
                    findings.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.module == "subprocess":
            for alias in node.names:
                imported_callables.add(alias.asname or alias.name)
            findings.append("from subprocess import ...")

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "os"
            and (node.attr in ("system", "popen") or node.attr.startswith("exec"))
        ):
            findings.append(f"os.{node.attr}")
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                receiver = func.value
                if (
                    isinstance(receiver, ast.Name)
                    and receiver.id in module_aliases
                    and func.attr in FORBIDDEN_SUBPROCESS_CALLS
                ):
                    findings.append(f"call: {receiver.id}.{func.attr}(...)")
            elif isinstance(func, ast.Name) and func.id in imported_callables:
                findings.append(f"call: {func.id}(...)")

    return findings


def test_known_bad_input_subprocess_check_actually_detects_a_call():
    bad_source = "import subprocess\nsubprocess.run(['echo', 'hi'])\n"
    tree = ast.parse(bad_source)
    assert _walks_subprocess(tree), "the known-bad fixture must trip the subprocess check"


def test_known_bad_input_from_subprocess_import_form_is_detected():
    """The import form that binds a bare NAME, so the call carries no
    `subprocess.` receiver to look for."""
    bad_source = "from subprocess import check_output\ncheck_output(['echo', 'hi'])\n"
    tree = ast.parse(bad_source)
    found = _walks_subprocess(tree)
    assert "from subprocess import ..." in found
    assert "call: check_output(...)" in found


def test_a_plain_dot_run_call_is_not_mistaken_for_a_subprocess_call():
    """The false positive this check must NOT have. `registry.run_rules` calls
    `rule.run(ctx)`, and every rule module defines `run`. A check that flags any
    `.run(...)` reports the package's own dispatch loop as a process spawn — and
    the only available "fix" for a false positive in a gate is to stop believing
    the gate."""
    good_source = "def run_rules(ctx):\n    for rule in RULES:\n        rule.run(ctx)\n"
    assert _walks_subprocess(ast.parse(good_source)) == []


def test_no_call_site_outside_cli_spawns_a_subprocess():
    offenders = {}
    for path in _package_modules():
        if path.name == "cli.py":
            continue  # cli.py itself never spawns one either, but is exempt
            # from this check by design intent (design §9.2 scopes the check
            # to "every call site EXCEPT cli.py"); cli.py's own freedom from
            # subprocess use is incidental, not asserted here.
        tree = ast.parse(path.read_text(encoding="utf-8"))
        found = _walks_subprocess(tree)
        if found:
            offenders[str(path.relative_to(REPO_ROOT))] = found
    assert offenders == {}


# ----------------------------------------------------------------- 9.11


def _top_level_imports(tree):
    """Imports bound at module scope, read from `tree.body` ONLY.

    Two forms are therefore INVISIBLE to this walk, and a green run does not
    speak to either:

    1. A function-level import. `document.py`'s `declared_dependencies` uses
       one as a documented cycle-breaker, so the form is live in this package.
    2. An import nested in a module-level `try:`/`except ImportError:` — the
       `tomllib`/`tomli` fallback shape. The `Import` node sits inside the
       `Try` node rather than directly in `tree.body`.

    The narrow walk is deliberate: `ast.walk` would also reach imports inside
    `TYPE_CHECKING` guards and other conditionals that impose no install-time
    dependency, which is the thing §9.11 is actually about. The trade is that
    a third-party dependency introduced by either form above ships unflagged.
    """
    names = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.append(node.module.split(".")[0])
    return names


def test_the_package_adds_no_third_party_dependency():
    offenders = {}
    for path in _package_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for name in _top_level_imports(tree):
            if name == "spellbook":
                continue
            if name in sys.stdlib_module_names:
                continue
            offenders.setdefault(str(path.relative_to(REPO_ROOT)), []).append(name)
    assert offenders == {}


# ------------------------------------------------------------------ 9.3


def test_package_needs_no_new_wheel_packaging_entry():
    assert Path(spellbook.planlint.__file__).is_relative_to(
        Path(__import__("spellbook").__file__).parent
    )
    pyproject_text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    wheel_section_match = re.search(
        r"\[tool\.hatch\.build\.targets\.wheel\]\s*\npackages\s*=\s*\[(?P<list>[^\]]*)\]",
        pyproject_text,
    )
    assert wheel_section_match is not None
    packages_list = wheel_section_match.group("list")
    # The claim has TWO halves and needs both. "planlint is absent" alone is
    # satisfied by a wheel that ships nothing at all; it is only good news
    # because `spellbook` is present and carries `planlint` as a subpackage.
    # Assert the carrier, or deleting `spellbook` from the list would leave
    # this test green while the package stopped shipping entirely.
    assert '"spellbook"' in packages_list or "'spellbook'" in packages_list
    assert "planlint" not in packages_list


# ------------------------------------------------------------------ 9.4


def _string_literals_in(tree):
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.add(node.value)
    return out


def test_every_rule_has_at_least_one_mutation_test():
    """Union every emits set from the real registry, AST-scan
    test_planlint_rules.py for every string literal, and assert every rule
    ID appears as a literal somewhere in that file. Reported as missing
    NAMES only (no "added" side — a literal in the test file that is not
    a rule ID is not a failure mode this check cares about).

    Scope: the universe checked here is `union(rule.emits for rule in
    registry.RULES)`, not every rule ID any Finding in the package can
    carry. `no-input` and `no-rules-ran` (constructed in `finding.py`,
    not tied to any rule's `emits`) are outside that universe — they are
    tested elsewhere (`test_planlint_api.py`, `test_planlint_finding.py`),
    not a gap this check leaves open."""
    from spellbook.planlint import registry

    all_rule_ids = set()
    for rule in registry.RULES:
        all_rule_ids |= rule.emits

    rules_test_path = REPO_ROOT / "tests" / "test_scripts" / "test_planlint_rules.py"
    tree = ast.parse(rules_test_path.read_text(encoding="utf-8"))
    literals = _string_literals_in(tree)

    missing = sorted(all_rule_ids - literals)
    assert missing == [], f"rule IDs with no mutation test reference: {missing}"


# ------------------------------------------------------------------ 9.5
#
# SCOPE: Findings in this section come from `rules/*.py` only. `graph.py`
# also constructs `Finding(rule="depends-prose", ...)` for a `depends-prose`
# check that lives outside `PACKAGE / "rules"` — a deliberate, already-
# documented split from `depends.py`'s own docstring (Task 6). The test
# names below read as a universal claim about "no rule"; they are not — the
# universe is `rules/*.py`, and `graph.py` is intentionally excluded, not
# missed.


def _emits_literals(tree):
    """Literal string rule IDs declared by a module's `EMITS = frozenset({...})`
    (or `set`/`tuple`/`list`-of-string-literals) assignment.

    Only the literal form is recognized: `EMITS = SOME_OTHER_NAME` or any
    non-`Call` right-hand side yields an empty set here, same as an absent
    `EMITS` entirely.
    """
    emits_literal = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "EMITS" for t in node.targets)
            and isinstance(node.value, ast.Call)
        ):
            for arg in node.value.args:
                if isinstance(arg, (ast.Set, ast.Tuple, ast.List)):
                    emits_literal |= {el.value for el in arg.elts if isinstance(el, ast.Constant)}
    return emits_literal


def _finding_rule_ids(tree):
    """Literal string `rule=` arguments passed to `Finding(...)` calls.

    Only string-literal `rule=` arguments are recognized. A `rule=` argument
    that is a variable reference (e.g. `rule=SOME_CONSTANT`) is invisible to
    this walk — see `_dynamic_rule_args`, which exists specifically to catch
    that gap rather than let it pass unseen (design §9.5 known limitation).
    """
    used_ids = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "Finding":
                for kw in node.keywords:
                    if kw.arg == "rule" and isinstance(kw.value, ast.Constant):
                        used_ids.add(kw.value.value)
    return used_ids


def _dynamic_rule_args(tree):
    """`Finding(rule=...)` call sites whose `rule=` argument is NOT a string
    literal (e.g. `rule=SOME_CONSTANT`). These are invisible to
    `_finding_rule_ids`'s literal-only scan, so a rules module could route a
    variable reference into `rule=` and never trip the undeclared-ID check.
    Rather than let that pass silently, every such site is reported here and
    the check that calls this fails loudly, flagging it for manual
    investigation."""
    dynamic = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "Finding":
                for kw in node.keywords:
                    if kw.arg == "rule" and not isinstance(kw.value, ast.Constant):
                        dynamic.append(ast.unparse(kw.value))
    return dynamic


def test_known_bad_input_undeclared_rule_id_check_actually_fires():
    """The known-bad-input guard for `test_no_rule_emits_a_rule_id_its_own_
    module_does_not_declare`, exercised through the SAME helper functions
    (`_emits_literals`, `_finding_rule_ids`) the real check calls below —
    not a reimplementation of the walk. If this guard used its own inline
    AST walk instead, a green real check would prove only that a fork of
    the scanner fires, not that the scanner itself does."""
    bad_source = (
        "from spellbook.planlint.finding import Finding\n"
        "EMITS = frozenset({'declared-id'})\n"
        "def run(ctx):\n"
        "    return [Finding(rule='undeclared-id', message='x')]\n"
    )
    tree = ast.parse(bad_source)
    emits = _emits_literals(tree)
    used = _finding_rule_ids(tree)
    assert sorted(used - emits) == ["undeclared-id"]


def test_no_rule_emits_a_rule_id_its_own_module_does_not_declare():
    """Every `rule=` literal a `rules/*.py` module passes to `Finding(...)`
    must appear in that same module's own `EMITS` set — a rule cannot emit
    an ID it never declared.

    Scope: only `rules/*.py`. `graph.py`'s `depends-prose` Finding is
    outside this walk by design (see the module-level scope note above this
    section) and a `rule=` argument that is not a string literal is outside
    `_finding_rule_ids`'s reach (see `_dynamic_rule_args`, checked
    separately below)."""
    offenders = {}
    dynamic_offenders = {}
    rules_dir = PACKAGE / "rules"
    scanned = sorted(p for p in rules_dir.glob("*.py") if p.name != "__init__.py")
    assert scanned, f"no rule modules found under {rules_dir}: the check would pass vacuously"
    for path in scanned:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        emits_literal = _emits_literals(tree)
        used_ids = _finding_rule_ids(tree)
        stray = used_ids - emits_literal
        if stray:
            offenders[path.name] = sorted(stray)
        dynamic = _dynamic_rule_args(tree)
        if dynamic:
            dynamic_offenders[path.name] = dynamic
    assert offenders == {}
    assert dynamic_offenders == {}, (
        f"non-literal rule= arguments found, undetectable by the literal-only "
        f"scan above and requiring manual investigation: {dynamic_offenders}"
    )


# ------------------------------------------------------------------ 9.7


def test_registry_rules_tuple_has_exactly_seven_entries():
    """Cross-check against test_planlint_api.py's own zero-invocation test
    (Task 16): this asserts the STRUCTURAL precondition — RULES has one
    entry per rule module — that makes the zero-invocation counting test
    meaningful (7 entries, not 0, not a subset)."""
    from spellbook.planlint import registry

    assert len(registry.RULES) == 7
    assert {r.name for r in registry.RULES} == {
        "structure",
        "depends",
        "checks",
        "consistency",
        "files",
        "ownership",
        "schema",
    }


def test_every_rule_result_name_matches_its_registry_row_name():
    """`Rule.name` and the `LintResult.name` the rule returns must be equal.

    `api.decided_claims()` builds its per-rule verdicts from `LintResult.name`
    alone, and reviewing-impl-plans's Phase 0 report (design §3.2.2) names
    rules from that list — so a disagreement makes a REVIEW GATE state a wrong
    fact: a claim attributed to a rule that did not decide it, or a rule
    reported missing that actually ran. Both are worse than a gap, because a
    gap is visible. `guard_no_input(name=...)` is the single place the returned
    name is set, so this compares the registry row against what the rule body
    actually passes there."""
    from spellbook.planlint import api, registry
    from spellbook.planlint.document import PlanDocument

    fixture = REPO_ROOT / "tests" / "test_scripts" / "fixtures" / "planlint" / "clean_plan.md"
    ctx = registry.RuleContext(
        doc=PlanDocument.from_path(fixture), phase=api.Phase.REVIEW, repo_root=None
    )
    mismatched = []
    for rule in registry.RULES:
        returned = rule.run(ctx).name
        if returned != rule.name:
            mismatched.append(f"registry row {rule.name!r} returns {returned!r}")
    assert mismatched == []


# ----------------------------------------------------------------- 9.10


def test_registry_error_barrier_wraps_exception_not_baseexception():
    """Cross-check on the AST: run_rules()'s except clause names Exception,
    not BaseException and not a bare except. A bare except or an
    except BaseException would catch KeyboardInterrupt, defeating the
    guarantee test_barrier_propagates_keyboardinterrupt (Task 12) checks
    at runtime — this is the static counterpart of that dynamic test."""
    tree = ast.parse((PACKAGE / "registry.py").read_text(encoding="utf-8"))
    except_types = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                except_types.append("bare except")
            elif isinstance(node.type, ast.Name):
                except_types.append(node.type.id)
            else:
                # ast.Attribute (`except mod.Error:`), ast.Tuple
                # (`except (A, B):`), or any other handler-type shape —
                # captured here so a second handler of one of these forms
                # cannot slip past the two branches above unrecorded.
                except_types.append(ast.unparse(node.type))
    assert except_types == ["Exception"]
