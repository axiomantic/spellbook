#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""Reverse gate: every declared reference to a repository artifact must resolve.

Three checks in this repository asserted only the FORWARD direction -- every
real item is documented -- and never the reverse -- every documented item is
real. Each reported green while rot accumulated behind it: dependabot watched
four directories that no longer existed, and prose across skills, commands, and
rules named modules and scripts that had been deleted. A reference that names
nothing fails at the moment a reader follows it, which is long after the commit
that broke it.

This module inverts the direction once, for every source at once. The gate is a
TABLE of ``Row(source, extractor, resolver)``. Adding a new source of references
is one row, not a new script.

Rows
----
``workflow-scripts``
    ``.github/workflows/*.yml`` -- ``run:`` script paths and local ``uses: ./``
    actions must exist as files.
``dependabot-directories``
    ``.github/dependabot.yml`` -- every ``directory:`` must be a real directory.
``extension-mcp-tools``
    ``extensions/**/*.ts`` -- every tool named by ``callTool('<name>')`` or by a
    ``/tool/<name>`` bridge URL must be registered in ``spellbook.mcp.tools``.
``prose-paths`` / ``prose-modules`` / ``prose-skills`` / ``prose-commands``
    ``skills/``, ``commands/``, ``agents/``, ``rules/``, and ``AGENTS.md`` --
    backticked repository paths, dotted ``spellbook.*`` module paths,
    ``skills/<name>`` mentions, and ``/<command>`` mentions.

Deliberately NOT a row: ``.pre-commit-config.yaml`` local hook ``entry:``
targets. ``tests/scripts/test_precommit_hook_entries_resolve.py`` already covers
that source, and it covers it BETTER than a row here could: it is a
parametrized pytest that reports one test id per hook, so a failure names the
offending hook directly in the test report. Folding it in would trade that
granularity for uniformity and would leave two implementations of the same
resolver to drift apart. The source is checked; it is checked elsewhere.

Stated blind spots
------------------
The prose extractors are narrowed on purpose. A wider match produced more false
positives than could be allowlisted honestly, and an allowlist that grows to
absorb noise stops being evidence of anything.

1. ``docs/`` paths in prose are NOT checked. Several commands review OTHER
   repositories and name *their* ``docs/coding-standards.md`` or
   ``docs/ai/testing-instructions.md``. Those references are correct and point
   outside this tree, and no extractor can tell them apart from a reference to
   this repository's own ``docs/`` mirror. The forward direction of the docs
   mirror is covered by ``scripts/check-readme-completeness.py``.
2. Only paths whose FIRST segment is a real top-level directory of this
   repository are checked (``ANCHOR_DIRS``). Illustrative example paths in
   teaching material -- ``src/auth/login.py``, ``exact/path/to/file.py``,
   ``doc-state/plan.json`` -- fall outside that set and are not matched. A
   reference to a genuinely missing ``src/`` file would therefore go unnoticed;
   this repository has no ``src/``.
3. Dotted module paths are checked only under the ``spellbook`` root. A
   trailing attribute is resolved against ``def``/``class``/assignment
   definitions by regex, not by import, so a name re-exported through
   ``__init__`` and not defined in its own module reads as unresolved.
4. Only fenced/backticked references are extracted. A path written as bare
   prose is invisible to every prose row.

Allowlisting
------------
Content-anchored, following ``scripts/check_removed_mode_tokens.py``: an entry
pairs a path glob with an ``anchor`` substring that MUST appear on the offending
line. Line numbers are NEVER anchors; they rot as files shift. A CHANGELOG entry
or deprecation notice that correctly describes a removal is suppressed by what
it SAYS, so the allowlist cannot silently widen to cover a real regression.

Usage:
    uv run scripts/check_reference_resolution.py [REPO_ROOT]
    uv run scripts/check_reference_resolution.py --row prose-paths

Exit codes:
    0 - every extracted reference resolves (or is allowlisted)
    1 - one or more references name something that does not exist
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable, Iterator

import yaml

# ---------------------------------------------------------------------------
# Shared configuration
# ---------------------------------------------------------------------------

# Prose sources. AGENTS.md is a file; the rest are directories scanned for *.md.
PROSE_DIRS = ("skills", "commands", "agents", "rules")
PROSE_FILES = ("AGENTS.md",)

# A prose path reference is checked only when its first segment names one of
# these. See blind spot 1 and 2 in the module docstring for why `docs` is absent.
ANCHOR_DIRS = frozenset(
    {
        ".github",
        "agents",
        "commands",
        "extensions",
        "hooks",
        "installer",
        "patterns",
        "profiles",
        "rules",
        "scripts",
        "skills",
        "spellbook",
        "tests",
    }
)

# Vendored trees never contain this repository's own references.
SKIP_PARTS = frozenset({"node_modules", ".git", "__pycache__", ".venv", "venv"})


# ---------------------------------------------------------------------------
# Case-exact filesystem probes
# ---------------------------------------------------------------------------
#
# ``Path.exists`` answers the FILESYSTEM's question, not the repository's. On a
# case-insensitive volume -- the macOS and Windows default -- it accepts
# ``.github/PULL_REQUEST_TEMPLATE.md`` while only ``pull_request_template.md``
# is on disk. A reference that is broken for every Linux reader then resolves
# clean for the author who wrote it, and this checker reports zero violations
# for a repository that has one. Each component is matched against its parent's
# real directory listing instead, so a verdict does not depend on the volume the
# checkout happens to sit on.


@lru_cache(maxsize=None)
def _listing(directory: Path) -> frozenset[str]:
    try:
        return frozenset(entry.name for entry in directory.iterdir())
    except OSError:
        return frozenset()


def _cased_exactly(repo_root: Path, path: Path) -> bool:
    """Whether every component below ``repo_root`` matches the on-disk spelling.

    Components at or above ``repo_root`` are not checked: the checkout's own
    location is not a reference this repository controls.
    """
    resolved = Path(os.path.normpath(path))
    try:
        relative = resolved.relative_to(repo_root)
    except ValueError:
        return True
    current = repo_root
    for part in relative.parts:
        if part not in _listing(current):
            return False
        current = current / part
    return True


def exists_exact(repo_root: Path, path: Path) -> bool:
    """``Path.exists`` that does not accept a mis-cased spelling."""
    return path.exists() and _cased_exactly(repo_root, path)


def is_file_exact(repo_root: Path, path: Path) -> bool:
    """``Path.is_file`` that does not accept a mis-cased spelling."""
    return path.is_file() and _cased_exactly(repo_root, path)


def is_dir_exact(repo_root: Path, path: Path) -> bool:
    """``Path.is_dir`` that does not accept a mis-cased spelling."""
    return path.is_dir() and _cased_exactly(repo_root, path)


@dataclass(frozen=True)
class AllowEntry:
    """A content-anchored allowlist entry.

    ``path_glob`` is matched with ``fnmatch`` against the repo-relative POSIX
    path of the SOURCE file. ``anchor`` is a literal substring that must appear
    on the offending line for the reference to be suppressed. ``None`` suppresses
    every reference in the file and is reserved for wholly archival bodies.
    """

    path_glob: str
    anchor: str | None
    reason: str


@dataclass(frozen=True)
class Reference:
    """One extracted reference, with enough context to allowlist it by content."""

    source: str  # repo-relative POSIX path of the file that declares it
    lineno: int  # 1-based
    target: str  # the referenced thing, as written
    line: str  # the full source line, for content anchoring


# ---------------------------------------------------------------------------
# Row: workflow-scripts
# ---------------------------------------------------------------------------

_WORKFLOW_SCRIPT_RE = re.compile(
    r"(?<![\w/.-])"
    r"((?:scripts|hooks|installer|tests|spellbook|\.github)/[A-Za-z0-9_./-]+"
    r"\.(?:py|sh|yml|yaml|toml))"
)


def _iter_yaml_values(node, keys: tuple[str, ...]) -> Iterator[tuple[str, str]]:
    """Yield ``(key, value)`` for every string-valued ``keys`` entry in ``node``."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in keys and isinstance(value, str):
                yield key, value
            else:
                yield from _iter_yaml_values(value, keys)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_yaml_values(item, keys)


def _lineno_of(text: str, needle: str) -> int:
    """Return the 1-based line of ``needle``'s first occurrence, or 0."""
    index = text.find(needle)
    if index < 0:
        return 0
    return text.count("\n", 0, index) + 1


def extract_workflow_scripts(repo_root: Path) -> list[Reference]:
    """Extract script paths from ``run:`` and local ``uses: ./`` in workflows."""
    refs: list[Reference] = []
    workflows = repo_root / ".github" / "workflows"
    if not workflows.is_dir():
        return refs

    for wf in sorted(workflows.glob("*.y*ml")):
        text = wf.read_text(encoding="utf-8")
        source = wf.relative_to(repo_root).as_posix()
        try:
            doc = yaml.safe_load(text)
        except yaml.YAMLError:
            continue

        for key, value in _iter_yaml_values(doc, ("run", "uses")):
            if key == "uses":
                if not value.startswith("./"):
                    continue
                targets = [value[2:]]
                anchors = [value]
            else:
                targets = sorted(set(_WORKFLOW_SCRIPT_RE.findall(value)))
                anchors = targets
            for target, anchor in zip(targets, anchors):
                lineno = _lineno_of(text, anchor)
                line = text.splitlines()[lineno - 1] if lineno else anchor
                refs.append(Reference(source, lineno, target, line))
    return refs


def resolve_repo_path(repo_root: Path, ref: Reference) -> bool:
    """A workflow-declared path must exist as a file or directory."""
    return exists_exact(repo_root, repo_root / ref.target)


# ---------------------------------------------------------------------------
# Row: dependabot-directories
# ---------------------------------------------------------------------------


def extract_dependabot_directories(repo_root: Path) -> list[Reference]:
    """Extract every ``directory:`` declared in ``.github/dependabot.yml``."""
    path = repo_root / ".github" / "dependabot.yml"
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    source = path.relative_to(repo_root).as_posix()

    refs: list[Reference] = []
    lines = text.splitlines()
    for lineno, line in enumerate(lines, start=1):
        match = re.match(r'\s*directory:\s*"?([^"\s]+)"?\s*$', line)
        if match:
            refs.append(Reference(source, lineno, match.group(1), line))
    return refs


def resolve_directory(repo_root: Path, ref: Reference) -> bool:
    """A dependabot ``directory:`` is repo-root-relative and must be a directory."""
    return is_dir_exact(repo_root, repo_root / ref.target.lstrip("/"))


# ---------------------------------------------------------------------------
# Row: extension-mcp-tools
# ---------------------------------------------------------------------------

# Extensions name an MCP tool in two shapes, and both are live in this tree:
# the SDK helper ``callTool('<name>')`` and the HTTP bridge's ``/tool/<name>``
# URL segment. Matching only the first read as a clean pass over zero
# references once the last ``callTool`` caller was deleted.
_CALL_TOOL_RE = re.compile(
    r"""callTool\(\s*['"]([A-Za-z_][A-Za-z0-9_]*)['"]"""
    r"""|/tool/([A-Za-z_][A-Za-z0-9_]*)"""
)
_TOOL_DEF_RE = re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_][A-Za-z0-9_]*)", re.M)


def registered_mcp_tools(repo_root: Path) -> set[str]:
    """Return every tool name registered via ``@mcp.tool()`` in the tools package.

    The decorator is applied immediately above the function, and FastMCP takes
    the function name as the tool name. Scanning the source rather than importing
    keeps this check runnable without the server's dependency tree.
    """
    tools_dir = repo_root / "spellbook" / "mcp" / "tools"
    names: set[str] = set()
    if not tools_dir.is_dir():
        return names
    for module in sorted(tools_dir.rglob("*.py")):
        text = module.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        for index, line in enumerate(lines):
            if "mcp.tool(" not in line:
                continue
            for candidate in lines[index + 1 : index + 4]:
                match = _TOOL_DEF_RE.match(candidate)
                if match:
                    names.add(match.group(1))
                    break
    return names


def extract_extension_tool_calls(repo_root: Path) -> list[Reference]:
    """Extract ``callTool('<name>')`` names from first-party extension sources."""
    refs: list[Reference] = []
    base = repo_root / "extensions"
    if not base.is_dir():
        return refs
    for source_file in sorted(base.rglob("*.ts")):
        if SKIP_PARTS & set(source_file.parts):
            continue
        text = source_file.read_text(encoding="utf-8", errors="replace")
        source = source_file.relative_to(repo_root).as_posix()
        for lineno, line in enumerate(text.splitlines(), start=1):
            for match in _CALL_TOOL_RE.finditer(line):
                target = match.group(1) or match.group(2)
                refs.append(Reference(source, lineno, target, line))
    return refs


def make_mcp_tool_resolver(repo_root: Path) -> Callable[[Path, Reference], bool]:
    """Build a resolver closed over the registered tool set (scanned once)."""
    registered = registered_mcp_tools(repo_root)

    def resolve(_root: Path, ref: Reference) -> bool:
        return ref.target in registered

    return resolve


# ---------------------------------------------------------------------------
# Prose rows: shared source iteration
# ---------------------------------------------------------------------------


def iter_prose_files(repo_root: Path) -> Iterator[Path]:
    """Yield every Markdown prose source, in deterministic order."""
    for name in PROSE_DIRS:
        base = repo_root / name
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.md")):
            if path.is_file() and not (SKIP_PARTS & set(path.parts)):
                yield path
    for name in PROSE_FILES:
        path = repo_root / name
        if path.is_file():
            yield path


def _extract_prose(repo_root: Path, pattern: re.Pattern) -> list[Reference]:
    refs: list[Reference] = []
    for path in iter_prose_files(repo_root):
        source = path.relative_to(repo_root).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for match in pattern.finditer(line):
                refs.append(Reference(source, lineno, match.group(1), line))
    return refs


# ---------------------------------------------------------------------------
# Row: prose-paths
# ---------------------------------------------------------------------------

_PROSE_PATH_RE = re.compile(
    r"`([A-Za-z0-9_.][A-Za-z0-9_./-]*\.(?:py|sh|ts|js|md|toml|yml|yaml|json))`"
)


def extract_prose_paths(repo_root: Path) -> list[Reference]:
    """Extract backticked paths that point into this repository's own tree."""
    return [
        ref
        for ref in _extract_prose(repo_root, _PROSE_PATH_RE)
        if "/" in ref.target and ref.target.split("/")[0] in ANCHOR_DIRS
    ]


def resolve_prose_path(repo_root: Path, ref: Reference) -> bool:
    """Resolve against the repo root, the declaring file's dir, and its skill root.

    Skill bodies routinely name sibling material relatively --
    ``references/verdict-taxonomy.md`` from ``skills/dedupe/SKILL.md``. Those are
    correct references, so the resolver understands them rather than the
    allowlist absorbing them.
    """
    source = Path(ref.source)
    candidates = [repo_root / ref.target, repo_root / source.parent / ref.target]
    if source.parts and source.parts[0] == "skills" and len(source.parts) > 2:
        candidates.append(repo_root / Path(*source.parts[:2]) / ref.target)
    return any(exists_exact(repo_root, candidate) for candidate in candidates)


# ---------------------------------------------------------------------------
# Row: prose-modules
# ---------------------------------------------------------------------------

_PROSE_MODULE_RE = re.compile(r"`(spellbook(?:\.[a-z_][a-z0-9_]*)+)`")


def extract_prose_modules(repo_root: Path) -> list[Reference]:
    """Extract backticked dotted ``spellbook.*`` module paths."""
    return _extract_prose(repo_root, _PROSE_MODULE_RE)


def resolve_prose_module(repo_root: Path, ref: Reference) -> bool:
    """Resolve the longest importable prefix, then any trailing attribute.

    ``spellbook.core.state.migrate_config_to_state`` resolves when
    ``spellbook/core/state.py`` exists AND defines ``migrate_config_to_state``.
    See blind spot 3: the attribute check is a source regex, not an import.
    """
    parts = ref.target.split(".")
    base: Path | None = None
    rest: list[str] = []
    for i in range(len(parts), 0, -1):
        candidate = repo_root / Path(*parts[:i])
        if is_dir_exact(repo_root, candidate) and is_file_exact(
            repo_root, candidate / "__init__.py"
        ):
            base, rest = candidate, parts[i:]
            break
        if is_file_exact(repo_root, candidate.with_suffix(".py")):
            base, rest = candidate.with_suffix(".py"), parts[i:]
            break
    if base is None:
        return False
    if not rest:
        return True
    if base.is_dir():
        return False
    text = base.read_text(encoding="utf-8", errors="replace")
    name = re.escape(rest[0])
    return (
        re.search(rf"^\s*(?:async\s+def|def|class)\s+{name}\b", text, re.M) is not None
        or re.search(rf"^{name}\s*[:=]", text, re.M) is not None
    )


# ---------------------------------------------------------------------------
# Row: prose-skills
# ---------------------------------------------------------------------------

_PROSE_SKILL_RE = re.compile(r"`skills/([a-z0-9][a-z0-9-]*)`")


def extract_prose_skills(repo_root: Path) -> list[Reference]:
    """Extract backticked ``skills/<name>`` mentions."""
    return _extract_prose(repo_root, _PROSE_SKILL_RE)


def resolve_skill(repo_root: Path, ref: Reference) -> bool:
    """A named skill must be a directory carrying a SKILL.md."""
    return is_file_exact(repo_root, repo_root / "skills" / ref.target / "SKILL.md")


# ---------------------------------------------------------------------------
# Row: prose-commands
# ---------------------------------------------------------------------------

_PROSE_COMMAND_RE = re.compile(r"`/([a-z0-9][a-z0-9:-]*)`")


def extract_prose_commands(repo_root: Path) -> list[Reference]:
    """Extract backticked ``/<name>`` slash-invocation mentions."""
    return _extract_prose(repo_root, _PROSE_COMMAND_RE)


def resolve_slash_name(repo_root: Path, ref: Reference) -> bool:
    """A ``/<name>`` invocation names either a command or a skill.

    Commands come in two shapes -- a flat ``commands/<name>.md`` and a directory
    ``commands/<name>/<name>.md`` -- and both are real. Skills are invocable by
    the same syntax, so a skill directory also resolves the reference.
    """
    name = ref.target
    if is_file_exact(repo_root, repo_root / "commands" / f"{name}.md"):
        return True
    if is_file_exact(repo_root, repo_root / "commands" / name / f"{name}.md"):
        return True
    return is_file_exact(repo_root, repo_root / "skills" / name / "SKILL.md")


# ---------------------------------------------------------------------------
# Allowlist
# ---------------------------------------------------------------------------
#
# Every entry is anchored on CONTENT. An entry that suppresses a real regression
# would have to quote the regression's own text, which makes widening visible in
# review rather than silent.

ALLOWLIST: dict[str, tuple[AllowEntry, ...]] = {
    "prose-paths": (
        AllowEntry(
            path_glob="commands/polish-repo-audit.md",
            anchor=".github/FUNDING.yml",
            reason="names a file in the TARGET repository being audited, not this one",
        ),
        AllowEntry(
            path_glob="rules/96-pr-conventions.md",
            anchor=".github/PULL_REQUEST_TEMPLATE.md",
            reason="enumerates candidate template paths to probe for in any repo",
        ),
        AllowEntry(
            path_glob="commands/advanced-code-review-context.md",
            anchor=".github/code-review-instructions.md",
            reason="names a standards file in the repository under review",
        ),
        AllowEntry(
            path_glob="commands/code-review-give.md",
            anchor=".github/code-review-instructions.md",
            reason="names a standards file in the repository under review",
        ),
        AllowEntry(
            path_glob="skills/writing-skills/anthropic-best-practices.md",
            anchor="scripts/helper.py",
            reason="illustrative script path in generic skill-authoring guidance",
        ),
        AllowEntry(
            path_glob="skills/executing-plans/SKILL.md",
            anchor="rules/files.py",
            reason="illustrative file path in a worked plan example",
        ),
        AllowEntry(
            path_glob="skills/reviewing-impl-plans/SKILL.md",
            anchor="rules/files.py",
            reason="illustrative file path in a worked plan example",
        ),
        AllowEntry(
            path_glob="skills/writing-plans/SKILL.md",
            anchor="rules/files.py",
            reason="illustrative file path in a worked plan example",
        ),
        AllowEntry(
            path_glob="skills/writing-plans/SKILL.md",
            anchor="tests/exact/path/to/test.py",
            reason="explicit placeholder demonstrating the required path format",
        ),
        AllowEntry(
            path_glob="skills/test-driven-development/SKILL.md",
            anchor="tests/test_login.py",
            reason="illustrative test path in a red-green worked example",
        ),
        AllowEntry(
            path_glob="skills/testing-strategy/SKILL.md",
            anchor="tests/test_login.py",
            reason="illustrative test path in a tier-classification example",
        ),
    ),
    "prose-commands": (
        AllowEntry(
            path_glob="*",
            anchor="`/command-name`",
            reason="explicit placeholder for a command name in authoring guidance",
        ),
        AllowEntry(
            path_glob="commands/writing-commands-paired.md",
            anchor="`/command-name-remove`",
            reason="explicit placeholder for the paired remove-command name",
        ),
        AllowEntry(
            path_glob="skills/develop/SKILL.md",
            anchor="`/skill:name`",
            reason="explicit placeholder for the harness skill-invocation syntax",
        ),
        AllowEntry(
            path_glob="commands/distill-session.md",
            anchor="`/compact`",
            reason="harness built-in command, not a spellbook artifact",
        ),
        AllowEntry(
            path_glob="skills/agent2agent/SKILL.md",
            anchor="`/compact`",
            reason="harness built-in command, not a spellbook artifact",
        ),
        AllowEntry(
            path_glob="commands/pr-dance.md",
            anchor="`/loop`",
            reason="harness built-in command, not a spellbook artifact",
        ),
        AllowEntry(
            path_glob="AGENTS.md",
            anchor="`/mcp`",
            reason="harness built-in command, not a spellbook artifact",
        ),
        AllowEntry(
            path_glob="AGENTS.md",
            anchor="Trigger by commenting `/ai-review` on a PR",
            reason="GitHub PR comment that triggers the external momus review bot, not a spellbook artifact",
        ),
    ),
}


# ---------------------------------------------------------------------------
# Rows
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Row:
    """One (source, extractor, resolver) triple.

    ``min_refs`` is the silent-no-op guard. An extractor whose pattern stops
    matching -- because the source changed shape -- would otherwise report a
    clean pass over zero references, which is indistinguishable from success.
    """

    name: str
    source: str
    extract: Callable[[Path], list[Reference]]
    resolve: Callable[[Path, Reference], bool]
    what: str
    min_refs: int


def build_rows(repo_root: Path) -> tuple[Row, ...]:
    """Assemble the row table. A new reference source is one entry here."""
    return (
        Row(
            name="workflow-scripts",
            source=".github/workflows/*.yml",
            extract=extract_workflow_scripts,
            resolve=resolve_repo_path,
            what="script path or local action",
            min_refs=4,
        ),
        Row(
            name="dependabot-directories",
            source=".github/dependabot.yml",
            extract=extract_dependabot_directories,
            resolve=resolve_directory,
            what="directory",
            min_refs=5,
        ),
        Row(
            name="extension-mcp-tools",
            source="extensions/**/*.ts",
            extract=extract_extension_tool_calls,
            resolve=make_mcp_tool_resolver(repo_root),
            what="registered MCP tool",
            min_refs=2,
        ),
        Row(
            name="prose-paths",
            source="skills/, commands/, agents/, rules/, AGENTS.md",
            extract=extract_prose_paths,
            resolve=resolve_prose_path,
            what="repository file or directory",
            min_refs=100,
        ),
        Row(
            name="prose-modules",
            source="skills/, commands/, agents/, rules/, AGENTS.md",
            extract=extract_prose_modules,
            resolve=resolve_prose_module,
            what="importable module or attribute",
            min_refs=4,
        ),
        Row(
            name="prose-skills",
            source="skills/, commands/, agents/, rules/, AGENTS.md",
            extract=extract_prose_skills,
            resolve=resolve_skill,
            what="skill directory",
            min_refs=4,
        ),
        Row(
            name="prose-commands",
            source="skills/, commands/, agents/, rules/, AGENTS.md",
            extract=extract_prose_commands,
            resolve=resolve_slash_name,
            what="command or skill",
            min_refs=200,
        ),
    )


def is_allowlisted(row_name: str, ref: Reference) -> AllowEntry | None:
    """Return the allowlist entry suppressing ``ref``, or None."""
    for entry in ALLOWLIST.get(row_name, ()):
        if not fnmatch.fnmatch(ref.source, entry.path_glob):
            continue
        if entry.anchor is None or entry.anchor in ref.line:
            return entry
    return None


@dataclass(frozen=True)
class RowResult:
    """Outcome of running one row."""

    row: Row
    extracted: int
    allowlisted: int
    unresolved: list[Reference]


def run_row(repo_root: Path, row: Row) -> RowResult:
    """Extract, allowlist, and resolve every reference for one row."""
    refs = row.extract(repo_root)
    unresolved: list[Reference] = []
    allowlisted = 0
    for ref in refs:
        if row.resolve(repo_root, ref):
            continue
        if is_allowlisted(row.name, ref):
            allowlisted += 1
            continue
        unresolved.append(ref)
    return RowResult(row=row, extracted=len(refs), allowlisted=allowlisted, unresolved=unresolved)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_reference_resolution",
        description="Verify every declared reference to a repository artifact resolves.",
    )
    parser.add_argument("repo_root", nargs="?", default=None)
    parser.add_argument("--row", action="append", help="Run only the named row(s).")
    args = parser.parse_args(argv)

    repo_root = (
        Path(args.repo_root).resolve()
        if args.repo_root
        else Path(__file__).resolve().parent.parent
    )

    rows = build_rows(repo_root)
    if args.row:
        selected = set(args.row)
        unknown = selected - {row.name for row in rows}
        if unknown:
            parser.error(f"unknown row(s): {', '.join(sorted(unknown))}")
        rows = tuple(row for row in rows if row.name in selected)

    results = [run_row(repo_root, row) for row in rows]

    total_unresolved = 0
    for result in results:
        row = result.row
        count = len(result.unresolved)
        total_unresolved += count
        status = "FAIL" if count else "ok"
        print(
            f"[{status:4}] {row.name:24} {result.extracted:4d} refs, "
            f"{result.allowlisted} allowlisted, {count} unresolved  ({row.source})"
        )
        for ref in result.unresolved:
            print(
                f"         {ref.source}:{ref.lineno}: {ref.target!r} "
                f"names no {row.what} | {ref.line.strip()[:110]}",
                file=sys.stderr,
            )

    if total_unresolved:
        print(
            f"\n{total_unresolved} unresolved reference(s). Fix the reference, or -- only "
            "if it legitimately names something outside this repository -- add a "
            "CONTENT-anchored entry to ALLOWLIST in "
            "scripts/check_reference_resolution.py. Never anchor on a line number.",
            file=sys.stderr,
        )
        return 1

    print(f"\nOK: every reference resolves across {len(results)} row(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
