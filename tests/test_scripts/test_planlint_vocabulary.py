"""Checkability self-application (design §9): every mechanically decidable
claim the design document makes about this port, decided by a check here.

9.1 — zero source-tool vocabulary in the ported engine.
9.2 — no call site (outside cli.py) spawns a subprocess.
9.3 — no new packaging entry is needed.
9.11 — no third-party dependency.

9.4, 9.5 continue in Task 18. 9.8, 9.9 continue in Task 22 (after the
SKILL.md edits exist).
"""

import ast
import re
import subprocess
import sys
from pathlib import Path

import spellbook.planlint

PACKAGE = Path(spellbook.planlint.__file__).parent
REPO_ROOT = PACKAGE.parents[1]

# ------------------------------------------------------------------ 9.1

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
    for path in sorted(PACKAGE.rglob("*.py")):
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
    module_aliases = set()      # names bound to the subprocess module itself
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
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == "os" and (
                node.attr in ("system", "popen") or node.attr.startswith("exec")
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
    good_source = (
        "def run_rules(ctx):\n"
        "    for rule in RULES:\n"
        "        rule.run(ctx)\n"
    )
    assert _walks_subprocess(ast.parse(good_source)) == []


def test_no_call_site_outside_cli_spawns_a_subprocess():
    offenders = {}
    for path in sorted(PACKAGE.rglob("*.py")):
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
    names = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.append(node.module.split(".")[0])
    return names


def test_the_package_adds_no_third_party_dependency():
    offenders = {}
    for path in sorted(PACKAGE.rglob("*.py")):
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
    assert "planlint" not in wheel_section_match.group("list")
