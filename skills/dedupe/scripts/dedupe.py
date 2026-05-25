#!/usr/bin/env python3
"""dedupe: detection-only instruction-deduplication helper for spellbook.

Single-file Python helper, stdlib only. This script is DETECTION-ONLY: it
never calls an LLM and never mutates source files. It emits JSON to stdout
(and reads/writes apply journals); all classification (Stage 2) and the
human-approved apply/verify flow (Stage 3) are orchestrated by the SKILL
via the Task tool, not by this script.

Importable: the module loads cleanly via ``importlib.util.spec_from_file_location``
without executing ``main`` and without any heavy/top-level model imports
(encodes constraint M5). No ``spellbook.*`` imports, no third-party packages.

See ``$SPELLBOOK_DIR/skills/dedupe/SKILL.md`` for the full protocol.
"""
from __future__ import annotations

import argparse
import difflib  # noqa: F401  -- used by later tasks (SequenceMatcher signal)
import hashlib  # noqa: F401  -- used by later tasks (stable block_id hashing)
import json
import os
import re
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path

# When this module is loaded via ``importlib.util.spec_from_file_location`` +
# ``exec_module`` (the test loader pattern, and any embedding harness), the
# loader does not register the module in ``sys.modules``. On Python 3.12+ the
# @dataclass machinery resolves ``str | None`` / ``list[...]`` annotations by
# looking up ``sys.modules.get(cls.__module__)`` and crashes with
# AttributeError when that returns None. Self-register under our own name so
# dataclass definitions below are robust regardless of how the module loaded.
if __name__ not in sys.modules:  # pragma: no branch - hit under exec_module loaders
    _self = types.ModuleType(__name__)
    _self.__dict__.update(globals())
    sys.modules[__name__] = _self

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "1"
JOURNAL_VERSION = "1"

DEFAULT_MAX_DEPTH = 3
DEFAULT_JACCARD_THRESHOLD = 0.7
DEFAULT_CONFIRM_THRESHOLD = 0.85
DEFAULT_EXTERNAL_THRESHOLD = 0.7
DEFAULT_MIN_BLOCK_CHARS = 80
DEFAULT_MAX_PAIRS = 200

# K constant: adjacency window (in whitespace tokens) for bare backticked
# reference detection during group expansion (design §3.1).
ADJACENCY_TOKEN_WINDOW = 8

# Stop-word set mirroring spellbook/forged/context_filtering.py STOP_WORDS.
# Word-set Jaccard with stop-word filtering is the proven Signal-1 semantics
# (design §3.5); this inlines the set rather than importing spellbook.* so the
# script stays stdlib-only (constraint M5, regression-locked by Task 2).
_STOP_WORDS: frozenset[str] = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
        "has", "have", "he", "in", "is", "it", "its", "of", "on", "or",
        "that", "the", "to", "was", "were", "will", "with",
    }
)

# Markdown emphasis / inline-code markers stripped during normalization so that
# "**bold**" and "bold" tokenize identically (design §3.5).
_EMPHASIS_RE = re.compile(r"[*_`]+")
_WHITESPACE_RE = re.compile(r"\s+")


# ---------------------------------------------------------------------------
# Signal 1: inline Jaccard + normalization (design §3.5)
#
# Mirrors spellbook/forged/context_filtering.py similarity() (lines 354-394)
# WITHOUT importing it: word-set Jaccard over stop-word-filtered token sets.
# The empty-set edge cases mirror similarity() EXACTLY:
#   - BOTH post-filter token sets empty  -> 1.0
#   - EXACTLY ONE post-filter set empty  -> 0.0
#   - else                               -> intersection / union
# _tokens intentionally OMITS the len(w) > 2 short-word filter (that filter
# lives in similarity()'s sibling _extract_keywords, NOT in similarity()), so
# short words such as "go"/"ox" are RETAINED.
# ---------------------------------------------------------------------------


def normalize(text: str) -> str:
    """Normalize markdown text for similarity comparison.

    Lowercases, strips markdown emphasis / inline-code markers (``*``, ``_``,
    backtick runs), collapses whitespace runs to single spaces, and strips
    leading/trailing whitespace. (Structural-boilerplate token dropping is
    layered on in Task 5; this is the lexical-normalization core.)
    """
    lowered = text.lower()
    no_emphasis = _EMPHASIS_RE.sub("", lowered)
    collapsed = _WHITESPACE_RE.sub(" ", no_emphasis)
    return collapsed.strip()


def _tokens(text: str) -> set[str]:
    """Tokenize ``normalize(text)`` into a stop-word-filtered set.

    Splits on whitespace, drops ``_STOP_WORDS`` and empty tokens. Short words
    (<= 2 chars) are deliberately RETAINED -- the ``len(w) > 2`` filter belongs
    to ``_extract_keywords`` in the exemplar, NOT to ``similarity()``, which is
    the function this mirrors.
    """
    return {w for w in normalize(text).split() if w and w not in _STOP_WORDS}


def jaccard(a: str, b: str) -> float:
    """Word-set Jaccard similarity over stop-word-filtered tokens.

    Edge cases are behaviorally equivalent to ``similarity()``'s post-filter
    edge cases, computed over the post-filter token sets: both empty -> 1.0;
    exactly one empty -> 0.0; else the intersection-over-union ratio. (The
    results coincide with ``similarity()``, though the structure differs:
    ``similarity()`` adds a pre-filter empty-input guard, whereas this relies
    only on these post-filter branches -- the three-branch form already
    guarantees a non-empty union in the else branch, so no separate
    divide-by-zero case is needed.)
    """
    ta = _tokens(a)
    tb = _tokens(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


# ---------------------------------------------------------------------------
# Data structures (design §3.7)
# ---------------------------------------------------------------------------


@dataclass
class Block:
    file: str            # repo-relative path
    granularity: str     # "heading-section" | "paragraph" | "list-item" | "fenced-whole"
    start_line: int
    end_line: int
    raw_text: str
    normalized_text: str
    parent_key: str | None   # enclosing heading-section block key, if any
    block_id: str            # stable hash(file, start_line, end_line, granularity)


@dataclass
class Pair:
    a: Block
    b: Block
    jaccard: float
    seqmatch_ratio: float
    drift_delta: float       # 1.0 - seqmatch_ratio
    is_drift_candidate: bool
    contains_safety_marker: bool   # precomputed hint for INLINE-MANDATORY (design §4.4)


@dataclass
class GroupResult:
    seed: list[str]
    corpus: list[str]                          # resolved file list
    expanded_group: list[str]
    unresolved_references: list[str]           # C1
    pairs: list[Pair] = field(default_factory=list)
    external_callers: list[dict] = field(default_factory=list)   # C5 (design §5.4)
    cost_ceiling_exceeded: bool = False
    candidate_count: int = 0


# ---------------------------------------------------------------------------
# Corpus resolution (the single source of truth for the corpus file set --
# design §3.2; depended on by Tasks 8, 9, 10, 12)
# ---------------------------------------------------------------------------


def _spellbook_dir() -> Path:
    """Resolve $SPELLBOOK_DIR, falling back to this script's repo root."""
    env = os.environ.get("SPELLBOOK_DIR")
    if env:
        return Path(env)
    # scripts/dedupe.py -> skills/dedupe/scripts -> repo root is parents[3].
    return Path(__file__).resolve().parents[3]


def _default_corpus_files(root: Path) -> list[Path]:
    """The design §3.2 safe-wide default globs under $SPELLBOOK_DIR.

    skills/**/SKILL.md + commands/**/*.md + CLAUDE.md +
    skills/shared-references/*.md. The default errs toward over-inclusion:
    the corpus is the external-caller scan set and must be a superset of any
    resolved group.
    """
    found: set[Path] = set()
    found.update(root.glob("skills/**/SKILL.md"))
    found.update(root.glob("commands/**/*.md"))
    found.update(root.glob("skills/shared-references/*.md"))
    claude = root / "CLAUDE.md"
    if claude.is_file():
        found.add(claude)
    return sorted(p.resolve() for p in found)


def resolve_corpus(corpus_arg: str | None) -> list[Path]:
    """Resolve the ``--corpus`` argument to a sorted, de-duplicated list of
    ``*.md`` file paths (design §3.2).

    Contract:
    - ``--corpus`` is a COMMA-SEPARATED LIST of entries; each entry is either
      a file path or a directory path (mixing allowed: ``dirA,fileB.md,dirC``).
    - Directory entries are walked recursively for ``*.md`` (every ``*.md`` at
      any depth under the dir -- NOT restricted to ``skills/**/SKILL.md``).
    - File entries are included as-is, but must end ``.md``; non-``.md`` file
      entries are skipped (design §8).
    - Returns the de-duplicated, sorted set of resolved ``*.md`` file paths.
    - DEFAULT (no ``--corpus``) = the design §3.2 safe-wide globs under
      $SPELLBOOK_DIR.
    """
    if corpus_arg is None:
        return _default_corpus_files(_spellbook_dir())

    resolved: set[Path] = set()
    for raw in corpus_arg.split(","):
        entry = raw.strip()
        if not entry:
            continue
        path = Path(entry)
        if path.is_dir():
            resolved.update(p.resolve() for p in path.rglob("*.md") if p.is_file())
        elif path.is_file():
            if path.suffix == ".md":
                resolved.add(path.resolve())
            # non-.md file entries are skipped (design §8).
    return sorted(resolved)


# ---------------------------------------------------------------------------
# Subcommand handlers (Task 1: stubs emitting a valid JSON shell; filled in
# by later tasks)
# ---------------------------------------------------------------------------


def _emit_shell() -> int:
    print(json.dumps({"version": SCHEMA_VERSION}, indent=2, ensure_ascii=False))
    return 0


def cmd_expand_group(args: argparse.Namespace) -> int:
    return _emit_shell()


def cmd_detect(args: argparse.Namespace) -> int:
    return _emit_shell()


def cmd_external_callers(args: argparse.Namespace) -> int:
    return _emit_shell()


def cmd_verify(args: argparse.Namespace) -> int:
    return _emit_shell()


# ---------------------------------------------------------------------------
# Usage + argparse plumbing
# ---------------------------------------------------------------------------

_USAGE = """\
dedupe: detection-only instruction-deduplication helper for spellbook.

USAGE
  dedupe.py <subcommand> [opts]

SUBCOMMANDS
  expand-group       Resolve seed -> transitive group; report unresolved refs.
  detect             Full pipeline: expand-group -> segment -> pair ->
                     external-caller scan; emit GroupResult JSON.
  external-callers   Standalone external-reference scan for a block list.
  verify             Post-apply re-detect; assert each replaced block resolves
                     to its reference.

All subcommands emit JSON to stdout. Human-facing rendering is the skill's job.
"""


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dedupe.py", add_help=False)
    sub = p.add_subparsers(dest="subcommand")

    sp_expand = sub.add_parser("expand-group", add_help=False)
    sp_expand.add_argument("--seed", nargs="+", required=True)
    sp_expand.add_argument("--corpus", default=None)
    sp_expand.add_argument(
        "--max-depth", dest="max_depth", type=int, default=DEFAULT_MAX_DEPTH
    )
    sp_expand.set_defaults(func=cmd_expand_group)

    sp_detect = sub.add_parser("detect", add_help=False)
    sp_detect.add_argument("--seed", nargs="+", required=True)
    sp_detect.add_argument("--corpus", default=None)
    sp_detect.add_argument(
        "--jaccard-threshold", dest="jaccard_threshold", type=float,
        default=DEFAULT_JACCARD_THRESHOLD,
    )
    sp_detect.add_argument(
        "--confirm-threshold", dest="confirm_threshold", type=float,
        default=DEFAULT_CONFIRM_THRESHOLD,
    )
    sp_detect.add_argument(
        "--external-threshold", dest="external_threshold", type=float,
        default=DEFAULT_EXTERNAL_THRESHOLD,
    )
    sp_detect.add_argument(
        "--min-block-chars", dest="min_block_chars", type=int,
        default=DEFAULT_MIN_BLOCK_CHARS,
    )
    sp_detect.add_argument(
        "--max-pairs", dest="max_pairs", type=int, default=DEFAULT_MAX_PAIRS
    )
    sp_detect.add_argument(
        "--max-depth", dest="max_depth", type=int, default=DEFAULT_MAX_DEPTH
    )
    sp_detect.set_defaults(func=cmd_detect)

    sp_external = sub.add_parser("external-callers", add_help=False)
    sp_external.add_argument("--blocks-json", dest="blocks_json", default=None)
    sp_external.add_argument("--corpus", default=None)
    sp_external.add_argument(
        "--external-threshold", dest="external_threshold", type=float,
        default=DEFAULT_EXTERNAL_THRESHOLD,
    )
    sp_external.set_defaults(func=cmd_external_callers)

    sp_verify = sub.add_parser("verify", add_help=False)
    sp_verify.add_argument("--journal", default=None)
    sp_verify.add_argument("--corpus", default=None)
    sp_verify.set_defaults(func=cmd_verify)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        print(_USAGE)
        return 0
    if argv[0] in ("-h", "--help"):
        print(_USAGE)
        return 0

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # argparse rejects unknown subcommands / bad flags by calling
        # sys.exit(2). Convert to a return code so callers that invoke main()
        # in-process (the importlib test loader) get a code instead of an
        # uncaught SystemExit. The error message was already written to stderr.
        return exc.code if isinstance(exc.code, int) else 2
    if not getattr(args, "func", None):
        print(_USAGE, file=sys.stderr)
        return 2
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
