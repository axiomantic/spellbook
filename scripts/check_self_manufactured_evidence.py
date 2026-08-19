#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Corpus checks whose only evidence is input they manufactured for themselves.

A corpus check is code that has a real population in this repository: it
enumerates one of the corpus trees (``skills/``, ``rules/``, ``commands/``,
``agents/``, ``patterns/``, ``profiles/``, ``extensions/``). Two shapes exist
here, and both are discovered:

``script``
    A checker under ``scripts/`` or ``hooks/``, driven by tests, pre-commit, or
    CI.
``test``
    A check that lives inside pytest with no ``scripts/`` counterpart -- it
    enumerates the corpus directly from a test module.

Such a check is a SELF-MANUFACTURED EVIDENCE instance when the suite references
it -- so it LOOKS guarded -- yet nothing anywhere aims it at the real
population. Every input it is given was built by the test that gives it, and no
pre-commit hook or CI step points it at the tree either.

The question this asks is NOT "did a test fabricate its input". Fabricating
input to drive a subject is legitimate, and a scratch-copy RED proof is the
best evidence a check can have that it CAN fail. The question is whether
ANYTHING aims the check at the real tree. A check with only RED proofs is green
on a corpus it has never read.

What is deliberately NOT flagged
--------------------------------
1. A check no test mentions at all. That is a plain coverage gap, reported
   separately; it does not wear the costume of a verified one.
2. A check registered in ``.pre-commit-config.yaml`` or in a workflow ``run:``
   step. Those aim it at the checkout on every commit or push.
3. A check driven with an argument that flows from ``Path(__file__)`` -- the
   real checkout -- anywhere in the suite. One such call site is enough.

Taint propagation
-----------------
Deciding "was this call aimed at the real tree" is a taint question, and a
taint analysis that cannot see through a boundary must not answer "real" by
default: that is a FALSE CLEAR, which is the dangerous direction. Taint
therefore crosses two boundaries here.

``fixture``
    A pytest fixture that writes scratch state -- ``monkeypatch.setenv``,
    ``monkeypatch.chdir``, ``os.chdir``, an ``os.environ`` assignment -- from a
    ``tmp_path`` value redirects every test that requests it, even though
    nothing at the call site looks temporary. Fixtures are read from the module
    and from every ``conftest.py`` above it.

``helper``
    A module-local function inherits the scratch context of any caller that has
    it, and a helper that RETURNS a temporary path taints its call sites.

A parameter that names no known fixture and no pytest builtin cannot be
classified. Such a call site is reported as UNCLASSIFIED and is never credited
as real coverage. Loud beats silent.

Usage:
    uv run scripts/check_self_manufactured_evidence.py [REPO_ROOT]

Exit codes:
    0  no self-manufactured-evidence instance and nothing unclassified
    1  at least one instance, or at least one unclassifiable call site
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from corpus_trees import ENUMERABLE_TREES

# The vocabulary that MARKS a Python file as corpus-facing. Naming one of
# these is evidence about a file's subject, not a directory this script
# walks; the scan roots are named explicitly in discover_script_checks.
CORPUS_DIRS = ENUMERABLE_TREES
_CORPUS_ALT = "|".join(CORPUS_DIRS)
# Importing a membership from corpus_trees names those trees just as much as
# spelling them out, and this detection is textual. Without these symbols the
# shared module would be a blind-spot generator: every checker that adopted it
# would silently drop out of this inventory while still enumerating the tree.
CORPUS_MEMBERSHIP_NAMES = frozenset(
    {"DOCUMENTED_TREES", "ENUMERABLE_TREES", "README_ARTIFACT_KINDS"}
)
_CORPUS_SYMBOLS = ("corpus_trees", *sorted(CORPUS_MEMBERSHIP_NAMES))
_SYMBOL_ALT = "|".join(_CORPUS_SYMBOLS)
CORPUS_RE = re.compile(
    rf"""["']({_CORPUS_ALT})["']|/({_CORPUS_ALT})/|\b({_SYMBOL_ALT})\b"""
)
CHECKER_RE = re.compile(
    r"^def (main|check_|find_|validate_|build_|scan_|collect_|run_)", re.MULTILINE
)
# A check only HAS a real population if it ENUMERATES one. Naming a corpus
# directory in a docstring, or joining one path to reach a single known file,
# is not a population. Requiring an enumeration is what separates
# check_removed_mode_tokens (walks skills/ + commands/ + agents/) from
# develop_gate_ledger (the string "skills" is a dict key).
ENUM_RE = re.compile(r"\.(rglob|glob|iterdir)\(|os\.walk\(|os\.listdir\(")
ENUM_METHODS = {"rglob", "glob", "iterdir", "walk", "listdir", "scandir"}

SUBPROCESS_FUNCS = {"run", "check_output", "check_call", "call", "Popen"}
LOADER_ATTRS = {"exec_module", "module_from_spec", "spec_from_file_location"}

TMP_SEEDS = {"tmp_path", "tmp_path_factory", "tmpdir", "tmpdir_factory"}
# Builtin fixtures carry no repository population. They are known, so a
# parameter naming one is classified rather than reported as unclassifiable.
PYTEST_BUILTIN_FIXTURES = TMP_SEEDS | {
    "monkeypatch",
    "capsys",
    "capsysbinary",
    "capfd",
    "capfdbinary",
    "caplog",
    "request",
    "recwarn",
    "pytestconfig",
    "cache",
    "doctest_namespace",
    "record_property",
    "record_testsuite_property",
    "record_xml_attribute",
    "pytester",
    "testdir",
    "subtests",
    "event_loop",
    "self",
    "cls",
}

ENV_WRITE_ATTRS = {"setenv", "chdir", "delenv", "setattr"}


# =============================================================================
# Emitted paths
# =============================================================================
#
# Every path this check prints or puts in a Verdict is a name a reader compares
# and a consumer matches on. `str(Path)` renders the native separator, so the
# same checkout emits `tests/x.py` on POSIX and `tests\x.py` on Windows and the
# tool's own output changes shape by platform. POSIX form is the one form.


def rel_posix(path: Path, root: Path) -> str:
    """Path relative to the repo root, in POSIX form on every platform."""
    return path.relative_to(root).as_posix()


# =============================================================================
# Taint
# =============================================================================


@dataclass
class TaintSets:
    """Names known to carry each kind of provenance inside one scope."""

    root: set[str] = field(default_factory=set)
    tmp: set[str] = field(default_factory=set)
    corpus: set[str] = field(default_factory=set)

    def copy(self) -> TaintSets:
        return TaintSets(set(self.root), set(self.tmp), set(self.corpus))


class Tainter:
    """Classify expressions as root-derived, tmp-derived, or neither.

    root-derived: the value flows from ``Path(__file__)`` -- the real checkout.
    tmp-derived:  the value flows from a pytest ``tmp_path`` family fixture, or
                  from a helper that returns one.
    tmp wins when both appear, because a scratch copy of the real tree that the
    test then mutates is manufactured input, not the population.
    """

    def __init__(
        self,
        seeds: TaintSets,
        opaque: set[str],
        tmp_funcs: set[str],
        root_funcs: set[str],
    ) -> None:
        self.sets = seeds.copy()
        # A module object or a script-path constant mentions the checker but
        # says nothing about what the checker was pointed AT. Counting it would
        # credit every launch, whatever its target.
        self.opaque = opaque
        self.tmp_funcs = tmp_funcs
        self.root_funcs = root_funcs

    # -- expression classification -------------------------------------------

    def _names(self, node: ast.AST) -> set[str]:
        return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)} - self.opaque

    def _called(self, node: ast.AST) -> set[str]:
        return {
            n.func.id
            for n in ast.walk(node)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        }

    def _is_file_expr(self, node: ast.AST) -> bool:
        # Both the bare `__file__` and a package's `pkg.__file__` anchor at the
        # real checkout. Matching only the bare Name left a module whose corpus
        # root came from `spellbook.planlint.__file__` unclassifiable.
        return any(
            (isinstance(n, ast.Name) and n.id == "__file__")
            or (isinstance(n, ast.Attribute) and n.attr == "__file__")
            for n in ast.walk(node)
        )

    def classify(self, node: ast.AST) -> str:
        names = self._names(node)
        called = self._called(node)
        if (names & self.sets.tmp) or (called & self.tmp_funcs):
            return "tmp"
        if self._is_file_expr(node) or (names & self.sets.root) or (called & self.root_funcs):
            return "root"
        return "neutral"

    def is_corpus(self, node: ast.AST) -> bool:
        names = self._names(node)
        if names & self.sets.corpus:
            return True
        # A membership imported from corpus_trees IS a list of corpus dirs;
        # the constants simply live in another module. Without this, adopting
        # the shared module would launder a corpus enumeration into an
        # unrecognised one and drop the check out of the inventory.
        if names & CORPUS_MEMBERSHIP_NAMES:
            return True
        return any(
            isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value in CORPUS_DIRS
            for n in ast.walk(node)
        )

    # -- statement absorption -------------------------------------------------

    def _bind(self, target: ast.AST, kind: str, corpus: bool) -> None:
        if isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                self._bind(elt, kind, corpus)
            return
        if not isinstance(target, ast.Name):
            return
        if kind == "tmp":
            self.sets.tmp.add(target.id)
        elif kind == "root":
            self.sets.root.add(target.id)
        if corpus:
            self.sets.corpus.add(target.id)

    def absorb(self, body: list[ast.stmt]) -> None:
        """Bind names from assignments and for-targets, to a fixed point.

        Three passes, because a name may be used before the statement that
        makes it tainted is reached in walk order (a helper defined below its
        caller, a comprehension target, a re-binding inside a loop).
        """
        stmts = [n for stmt in body for n in ast.walk(stmt)]
        for _ in range(3):
            before = (len(self.sets.root), len(self.sets.tmp), len(self.sets.corpus))
            for node in stmts:
                if isinstance(node, ast.Assign):
                    kind = self.classify(node.value)
                    corpus = self.is_corpus(node.value)
                    for tgt in node.targets:
                        self._bind(tgt, kind, corpus)
                elif isinstance(node, (ast.AnnAssign, ast.AugAssign)) and node.value is not None:
                    self._bind(node.target, self.classify(node.value), self.is_corpus(node.value))
                elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
                    src = node.iter
                    self._bind(node.target, self.classify(src), self.is_corpus(src))
                elif isinstance(node, ast.withitem) and node.optional_vars is not None:
                    self._bind(
                        node.optional_vars,
                        self.classify(node.context_expr),
                        self.is_corpus(node.context_expr),
                    )
            if (len(self.sets.root), len(self.sets.tmp), len(self.sets.corpus)) == before:
                break


# =============================================================================
# Module model
# =============================================================================


@dataclass
class FuncInfo:
    name: str
    node: ast.FunctionDef | ast.AsyncFunctionDef
    params: list[str]
    is_fixture: bool
    calls: set[str] = field(default_factory=set)
    # Filled by the fixed point.
    env_tmp: bool = False
    returns_tmp: bool = False
    returns_root: bool = False
    unknown_params: set[str] = field(default_factory=set)


def _is_fixture(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for dec in node.decorator_list:
        text = ast.dump(dec)
        if "'fixture'" in text or '"fixture"' in text:
            return True
    return False


def _param_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    args = node.args
    return [a.arg for a in list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs)]


class ModuleModel:
    """Functions, fixtures, and taint for one test module."""

    def __init__(self, tree: ast.Module, opaque: set[str], external_fixtures: dict[str, FuncInfo]):
        self.tree = tree
        self.opaque = opaque
        self.functions: dict[str, FuncInfo] = {}
        self.enclosing: dict[ast.AST, str | None] = {}
        self._collect(tree)
        self.fixtures: dict[str, FuncInfo] = dict(external_fixtures)
        self.fixtures.update({f.name: f for f in self.functions.values() if f.is_fixture})
        self.module_seeds = TaintSets()
        self.solve()

    # -- collection ----------------------------------------------------------

    def _collect(self, tree: ast.Module) -> None:
        def walk(node: ast.AST, current: str | None) -> None:
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    info = FuncInfo(
                        name=child.name,
                        node=child,
                        params=_param_names(child),
                        is_fixture=_is_fixture(child),
                    )
                    info.calls = {
                        n.func.id
                        for n in ast.walk(child)
                        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                    }
                    # A nested redefinition of the same name is rare; last wins.
                    self.functions[child.name] = info
                    self.enclosing[child] = current
                    walk(child, child.name)
                else:
                    self.enclosing[child] = current
                    walk(child, current)

        walk(tree, None)

    def enclosing_function(self, node: ast.AST) -> FuncInfo | None:
        name = self.enclosing.get(node)
        return self.functions.get(name) if name else None

    # -- fixed point ---------------------------------------------------------

    def _tainter_for(self, seeds: TaintSets) -> Tainter:
        return Tainter(
            seeds,
            self.opaque,
            {f.name for f in self.functions.values() if f.returns_tmp},
            {f.name for f in self.functions.values() if f.returns_root},
        )

    def _seed_params(self, info: FuncInfo, seeds: TaintSets) -> set[str]:
        """Seed a function's parameters from the fixture map; return unknowns."""
        unknown: set[str] = set()
        for p in info.params:
            if p in TMP_SEEDS:
                seeds.tmp.add(p)
                continue
            if p in PYTEST_BUILTIN_FIXTURES or p.startswith("_"):
                continue
            fixture = self.fixtures.get(p)
            if fixture is None:
                # Only test functions and fixtures receive fixtures; a plain
                # helper's parameters are ordinary arguments handled at the
                # call site.
                if info.name.startswith("test_") or info.is_fixture:
                    unknown.add(p)
                continue
            if fixture.returns_tmp:
                seeds.tmp.add(p)
            elif fixture.returns_root:
                seeds.root.add(p)
        return unknown

    def local_tainter(self, info: FuncInfo) -> Tainter:
        seeds = self.module_seeds.copy()
        info.unknown_params = self._seed_params(info, seeds)
        tainter = self._tainter_for(seeds)
        tainter.absorb(list(info.node.body))
        return tainter

    def _local_env_tmp(self, info: FuncInfo, tainter: Tainter) -> bool:
        for node in ast.walk(info.node):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                attr = node.func.attr
                recv = node.func.value
                is_monkeypatch = isinstance(recv, ast.Name) and recv.id == "monkeypatch"
                is_os_chdir = isinstance(recv, ast.Name) and recv.id == "os" and attr == "chdir"
                redirects = (is_monkeypatch and attr in ENV_WRITE_ATTRS) or is_os_chdir
                if redirects and any(tainter.classify(a) == "tmp" for a in node.args):
                    return True
            if isinstance(node, ast.Assign) and node.value is not None:
                for tgt in node.targets:
                    if (
                        isinstance(tgt, ast.Subscript)
                        and "environ" in ast.dump(tgt.value)
                        and tainter.classify(node.value) == "tmp"
                    ):
                        return True
        return False

    def solve(self) -> None:
        module_body = [
            s
            for s in self.tree.body
            if not isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ]
        base = self._tainter_for(TaintSets())
        base.absorb(module_body)
        self.module_seeds = base.sets

        for _ in range(6):
            changed = False
            for info in self.functions.values():
                tainter = self.local_tainter(info)
                env = self._local_env_tmp(info, tainter)
                # A fixture that redirects the environment redirects every test
                # that requests it, and a helper inherits the context of any
                # caller that has one. Conservative in the safe direction: one
                # tainted caller is enough to refuse credit.
                for p in info.params:
                    fx = self.fixtures.get(p)
                    if fx is not None and fx.env_tmp:
                        env = True
                for other in self.functions.values():
                    if info.name in other.calls and other.env_tmp:
                        env = True
                returns_tmp = False
                returns_root = False
                for node in ast.walk(info.node):
                    if isinstance(node, (ast.Return, ast.Yield)) and node.value is not None:
                        kind = tainter.classify(node.value)
                        returns_tmp |= kind == "tmp"
                        returns_root |= kind == "root"
                if (env, returns_tmp, returns_root) != (
                    info.env_tmp,
                    info.returns_tmp,
                    info.returns_root,
                ):
                    info.env_tmp, info.returns_tmp, info.returns_root = (
                        env,
                        returns_tmp,
                        returns_root,
                    )
                    changed = True
            if not changed:
                break
        # Final local taint, now that the fixed point has settled.
        self.tainters = {name: self.local_tainter(info) for name, info in self.functions.items()}
        self.module_tainter = self._tainter_for(self.module_seeds)


# =============================================================================
# Findings
# =============================================================================


@dataclass
class Finding:
    kind: str  # "real" | "manufactured" | "unclassified"
    where: str
    detail: str


# =============================================================================
# Script-resident checkers
# =============================================================================


def discover_script_checks(root: Path) -> dict[str, Path]:
    """Return {module_stem: path} for every corpus checker under scripts/hooks."""
    found: dict[str, Path] = {}
    # Where CHECKERS live, not corpus trees -- deliberately not corpus_trees.
    for d in ("scripts", "hooks"):
        for p in sorted((root / d).glob("*.py")):
            src = p.read_text(encoding="utf-8", errors="replace")
            if CORPUS_RE.search(src) and CHECKER_RE.search(src) and ENUM_RE.search(src):
                found[p.stem] = p
    return found


def validator_symbols(tree: ast.AST, stem: str) -> tuple[set[str], set[str]]:
    """Return (function names imported from the checker, module aliases for it).

    Aliases cover the ``importlib.util.spec_from_file_location`` idiom this
    suite uses to load a hyphenated script as a module.
    """
    funcs: set[str] = set()
    aliases: set[str] = set()
    module_name = stem.replace("-", "_")
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == module_name:
            funcs |= {a.asname or a.name for a in node.names}
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name == module_name:
                    aliases.add(a.asname or a.name)
        if isinstance(node, ast.Assign):
            src = ast.dump(node.value)
            if "module_from_spec" in src and isinstance(node.targets[0], ast.Name):
                aliases.add(node.targets[0].id)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = ast.dump(node)
            if ("module_from_spec" in body or "spec_from_file_location" in body) and any(
                isinstance(n, ast.Return) for n in ast.walk(node)
            ):
                aliases.add(node.name)
    for _ in range(3):
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for ret in [n for n in ast.walk(node) if isinstance(n, ast.Return)]:
                    if ret.value is not None:
                        called = {
                            n.func.id
                            for n in ast.walk(ret.value)
                            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                        }
                        if called & aliases:
                            aliases.add(node.name)
    return funcs, aliases


def script_path_consts(tree: ast.AST, stem: str) -> set[str]:
    """Names bound to a path literal naming the checker script."""
    out: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Name)
            and f"{stem}.py" in ast.dump(node.value)
        ):
            out.add(node.targets[0].id)
    return out


def call_targets_validator(
    call: ast.Call, funcs: set[str], aliases: set[str], consts: set[str], stem: str
) -> bool:
    """True only for a call that actually drives the checker.

    Whitelist, never blacklist: module loading, sys.path plumbing and path
    joins all mention the script and all mean nothing about what was checked.
    """
    f = call.func
    if isinstance(f, ast.Name) and f.id in funcs:
        return True
    if (
        isinstance(f, ast.Attribute)
        and isinstance(f.value, ast.Name)
        and f.value.id in aliases
        and f.attr not in LOADER_ATTRS
    ):
        return True
    fname = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
    if fname in SUBPROCESS_FUNCS:
        names = {n.id for n in ast.walk(call) if isinstance(n, ast.Name)}
        if names & consts or f"{stem}.py" in ast.dump(call):
            return True
    return False


def arg_leaves(node: ast.AST) -> list[ast.AST]:
    """Split a container argument into the values that carry the taint.

    ``[sys.executable, str(SCRIPT)]`` and ``{"HOME": tmp, "SPELLBOOK_DIR":
    root}`` each hold one entry that decides what the checker was aimed at;
    judging the container as a whole loses it.
    """
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return [leaf for e in node.elts for leaf in arg_leaves(e)]
    if isinstance(node, ast.Dict):
        return [leaf for v in node.values if v is not None for leaf in arg_leaves(v)]
    if isinstance(node, ast.Starred):
        return arg_leaves(node.value)
    return [node]


def analyse_script_check(
    tf: Path,
    stem: str,
    model_cache: dict[Path, ModuleModel],
    conftests: dict[Path, dict[str, FuncInfo]],
) -> list[Finding]:
    tree = ast.parse(tf.read_text(encoding="utf-8", errors="replace"))
    funcs, aliases = validator_symbols(tree, stem)
    consts = script_path_consts(tree, stem)
    model = ModuleModel(tree, opaque=aliases | consts, external_fixtures=conftests.get(tf, {}))
    model_cache[tf] = model

    findings: list[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not call_targets_validator(node, funcs, aliases, consts, stem):
            continue
        enclosing = model.enclosing_function(node)
        tainter = model.tainters[enclosing.name] if enclosing else model.module_tainter
        env_tmp = enclosing.env_tmp if enclosing else False
        unknown = enclosing.unknown_params if enclosing else set()
        args = list(node.args) + [kw.value for kw in node.keywords]
        leaves = [leaf for a in args for leaf in arg_leaves(a)]
        kinds = [tainter.classify(x) for x in leaves]
        fn = node.func
        fname = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
        where = f"{tf.as_posix()}:{node.lineno}"
        if "root" in kinds:
            # One purely root-derived leaf is enough. A subprocess env dict
            # mixes {"HOME": tmp_path, "SPELLBOOK_DIR": REPO_ROOT}; the second
            # entry is what aims the checker at the real tree.
            findings.append(Finding("real", where, "root-derived argument"))
        elif "tmp" in kinds or env_tmp:
            findings.append(
                Finding(
                    "manufactured",
                    where,
                    "scratch path" if "tmp" in kinds else "scratch environment",
                )
            )
        elif unknown:
            findings.append(
                Finding(
                    "unclassified",
                    where,
                    f"fixture(s) {', '.join(sorted(unknown))} are defined nowhere this "
                    "check can read; the target of this call is unknown",
                )
            )
        elif fname in SUBPROCESS_FUNCS:
            # A launch with no scratch path and no scratch environment runs
            # against the checkout: the script resolves its own root from
            # __file__ or inherits cwd.
            findings.append(Finding("real", where, "subprocess launch, no scratch redirection"))
        else:
            findings.append(Finding("manufactured", where, "no real-tree argument"))
    return findings


def external_real_coverage(root: Path, stem: str) -> list[str]:
    out = []
    pc = root / ".pre-commit-config.yaml"
    if pc.is_file() and f"{stem}.py" in pc.read_text(encoding="utf-8"):
        out.append(".pre-commit-config.yaml")
    workflows = root / ".github" / "workflows"
    for wf in sorted(workflows.glob("*.yml")) + sorted(workflows.glob("*.yaml")):
        for line in wf.read_text(encoding="utf-8").splitlines():
            if f"{stem}.py" in line and ("run:" in line or "entry:" in line):
                out.append(rel_posix(wf, root))
                break
    return out


# =============================================================================
# Test-resident checks
# =============================================================================


def enumeration_sites(tree: ast.Module) -> list[tuple[ast.Call, ast.AST]]:
    """Return (call, subject) for every directory enumeration in the module.

    ``subject`` is the expression that names the directory being enumerated:
    the receiver of ``.rglob``/``.glob``/``.iterdir``, or the first argument of
    ``os.walk``/``os.listdir``/``os.scandir``.
    """
    out: list[tuple[ast.Call, ast.AST]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        attr = node.func.attr
        if attr not in ENUM_METHODS:
            continue
        recv = node.func.value
        if attr in {"walk", "listdir", "scandir"}:
            if not (isinstance(recv, ast.Name) and recv.id == "os"):
                continue
            if not node.args:
                continue
            out.append((node, node.args[0]))
        else:
            out.append((node, recv))
    return out


def first_party_packages(root: Path) -> set[str]:
    """Top-level importable packages of this repository."""
    return {
        p.name
        for p in root.iterdir()
        if p.is_dir() and (p / "__init__.py").is_file() and p.name != "tests"
    }


def has_a_subject(tree: ast.Module, subject_heads: set[str]) -> bool:
    """True when the module imports something of this project's own to test.

    A test-resident corpus CHECK has no subject but the corpus: it enumerates
    the tree and asserts on what it finds, using nothing but the standard
    library and pytest. A module that imports a first-party package or loads a
    ``scripts/``/``hooks/`` module is testing that subject, and the scratch
    trees it builds are that subject's INPUT or OUTPUT, not a manufactured
    corpus standing in for the real one.

    This is the narrowing that keeps installer tests out of the population.
    They build a fake ``rules/`` tree, hand it to the installer, and enumerate
    what the installer wrote -- corpus-shaped, tmp-derived, and not a corpus
    check. Stated blind spot: a genuine corpus check that factors its logic
    into an imported helper is invisible here.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] in subject_heads:
                    return True
        if (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.split(".")[0] in subject_heads
        ):
            return True
        if isinstance(node, ast.Attribute) and node.attr in LOADER_ATTRS:
            return True
    return False


def analyse_test_check(tf: Path, conftests: dict[Path, dict[str, FuncInfo]]) -> list[Finding]:
    """Classify every corpus enumeration a test module performs."""
    tree = ast.parse(tf.read_text(encoding="utf-8", errors="replace"))
    model = ModuleModel(tree, opaque=set(), external_fixtures=conftests.get(tf, {}))
    findings: list[Finding] = []
    for call, subject in enumeration_sites(tree):
        enclosing = model.enclosing_function(call)
        tainter = model.tainters[enclosing.name] if enclosing else model.module_tainter
        if not tainter.is_corpus(subject):
            continue
        kind = tainter.classify(subject)
        where = f"{tf.as_posix()}:{call.lineno}"
        if kind == "root":
            findings.append(Finding("real", where, "enumerates the checkout"))
        elif kind == "tmp":
            findings.append(Finding("manufactured", where, "enumerates a scratch tree"))
        else:
            unknown = enclosing.unknown_params if enclosing else set()
            detail = (
                f"fixture(s) {', '.join(sorted(unknown))} are defined nowhere this check "
                "can read; the enumerated tree is unknown"
                if unknown
                else "the enumerated tree flows from no source this check can trace"
            )
            findings.append(Finding("unclassified", where, detail))
    return findings


# =============================================================================
# conftest fixtures
# =============================================================================


def load_conftest_fixtures(root: Path, test_files: list[Path]) -> dict[Path, dict[str, FuncInfo]]:
    """Map each test file to the fixtures visible from its conftest ancestors."""
    cache: dict[Path, dict[str, FuncInfo]] = {}
    per_dir: dict[Path, dict[str, FuncInfo]] = {}

    def fixtures_in(conftest: Path) -> dict[str, FuncInfo]:
        if conftest in per_dir:
            return per_dir[conftest]
        out: dict[str, FuncInfo] = {}
        try:
            tree = ast.parse(conftest.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            per_dir[conftest] = out
            return out
        model = ModuleModel(tree, opaque=set(), external_fixtures={})
        for info in model.functions.values():
            if info.is_fixture:
                out[info.name] = info
        per_dir[conftest] = out
        return out

    for tf in test_files:
        visible: dict[str, FuncInfo] = {}
        for parent in reversed(tf.parents):
            if root not in parent.parents and parent != root:
                continue
            conftest = parent / "conftest.py"
            if conftest.is_file():
                visible.update(fixtures_in(conftest))
        cache[tf] = visible
    return cache


# =============================================================================
# Driver
# =============================================================================


@dataclass
class Verdict:
    name: str
    shape: str
    status: str
    evidence: str
    referenced_by: list[str] = field(default_factory=list)


def evaluate(root: Path) -> tuple[list[Verdict], dict[str, int]]:
    scripts = discover_script_checks(root)
    test_files = sorted((root / "tests").rglob("test_*.py"))
    conftests = load_conftest_fixtures(root, test_files)
    test_src = {tf: tf.read_text(encoding="utf-8", errors="replace") for tf in test_files}

    verdicts: list[Verdict] = []
    model_cache: dict[Path, ModuleModel] = {}

    for stem in sorted(scripts):
        module_name = stem.replace("-", "_")
        referencing = [tf for tf, s in test_src.items() if stem in s or module_name in s]
        findings: list[Finding] = []
        for tf in referencing:
            findings += analyse_script_check(tf, stem, model_cache, conftests)
        external = external_real_coverage(root, stem)
        real = [f for f in findings if f.kind == "real"]
        unclassified = [f for f in findings if f.kind == "unclassified"]
        rel = [rel_posix(tf, root) for tf in referencing]
        if real:
            verdicts.append(
                Verdict(stem, "script", "real", f"{real[0].where}: {real[0].detail}", rel)
            )
        elif external:
            verdicts.append(
                Verdict(stem, "script", "real", "external: " + ", ".join(external), rel)
            )
        elif unclassified:
            verdicts.append(
                Verdict(
                    stem,
                    "script",
                    "unclassified",
                    f"{unclassified[0].where}: {unclassified[0].detail}",
                    rel,
                )
            )
        elif referencing:
            verdicts.append(
                Verdict(stem, "script", "manufactured", "no call site names the checkout", rel)
            )
        else:
            verdicts.append(Verdict(stem, "script", "unreferenced", "no test mentions it", []))

    subject_heads = first_party_packages(root) | {s.replace("-", "_") for s in scripts}
    for tf in test_files:
        src = test_src[tf]
        if not CORPUS_RE.search(src) or not ENUM_RE.search(src):
            continue
        if has_a_subject(ast.parse(src), subject_heads):
            continue
        findings = analyse_test_check(tf, conftests)
        if not findings:
            continue
        name = rel_posix(tf, root)
        real = [f for f in findings if f.kind == "real"]
        unclassified = [f for f in findings if f.kind == "unclassified"]
        if real:
            verdicts.append(
                Verdict(name, "test", "real", f"{real[0].where}: {real[0].detail}", [name])
            )
        elif unclassified:
            verdicts.append(
                Verdict(
                    name,
                    "test",
                    "unclassified",
                    f"{unclassified[0].where}: {unclassified[0].detail}",
                    [name],
                )
            )
        else:
            verdicts.append(
                Verdict(
                    name,
                    "test",
                    "manufactured",
                    f"{findings[0].where}: {findings[0].detail}",
                    [name],
                )
            )

    counts = {
        status: sum(1 for v in verdicts if v.status == status)
        for status in ("real", "manufactured", "unclassified", "unreferenced")
    }
    return verdicts, counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_self_manufactured_evidence",
        description="Find corpus checks whose only evidence is input they built themselves.",
    )
    parser.add_argument("repo_root", nargs="?", default=None)
    parser.add_argument(
        "--shape",
        choices=("script", "test"),
        action="append",
        help="Restrict to one shape of corpus check.",
    )
    args = parser.parse_args(argv)

    root = (
        Path(args.repo_root).resolve() if args.repo_root else Path(__file__).resolve().parent.parent
    )
    verdicts, _ = evaluate(root)
    if args.shape:
        verdicts = [v for v in verdicts if v.shape in set(args.shape)]

    def section(status: str) -> list[Verdict]:
        return [v for v in verdicts if v.status == status]

    print(f"corpus checks discovered: {len(verdicts)}")
    for shape in ("script", "test"):
        n = sum(1 for v in verdicts if v.shape == shape)
        print(f"  {shape:7} {n}")
    print()

    real = section("real")
    print(f"[ok  ] REAL POPULATION EXERCISED: {len(real)}")
    for v in real:
        print(f"       {v.name}  <- {v.evidence}")
    print()

    unreferenced = section("unreferenced")
    print(f"[ok  ] NO TEST REFERENCES IT (plain gap, not self-manufactured): {len(unreferenced)}")
    for v in unreferenced:
        print(f"       {v.name}")
    print()

    unclassified = section("unclassified")
    manufactured = section("manufactured")

    print(
        f"[{'FAIL' if unclassified else 'ok  '}] UNCLASSIFIED: {len(unclassified)}",
        file=sys.stderr if unclassified else sys.stdout,
    )
    for v in unclassified:
        print(f"       {v.name}  <- {v.evidence}", file=sys.stderr)
    print()

    print(
        f"[{'FAIL' if manufactured else 'ok  '}] SELF-MANUFACTURED EVIDENCE ONLY: {len(manufactured)}",
        file=sys.stderr if manufactured else sys.stdout,
    )
    for v in manufactured:
        print(f"       {v.name}  <- {v.evidence}", file=sys.stderr)
        for ref in v.referenced_by:
            print(f"           referenced by {ref}", file=sys.stderr)

    if manufactured or unclassified:
        print(
            "\nA corpus check whose every input is self-manufactured is green on a "
            "population it has never read. Aim it at the real tree from a test, or "
            "register it in .pre-commit-config.yaml or a workflow. An UNCLASSIFIED "
            "call site is not a pass: this check could not determine what the call "
            "was aimed at, and refuses to credit it.",
            file=sys.stderr,
        )
        return 1

    print("\nOK: every corpus check is aimed at the real tree by something.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
