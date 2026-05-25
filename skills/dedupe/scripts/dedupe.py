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
import difflib
import hashlib
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
# Signal 2: SequenceMatcher confirm signal + drift delta + pair scoring
# (design §3.5, Signal 2)
#
# Signal 1 (Jaccard) is the cheap recall gate; Signal 2 (SequenceMatcher
# character-level ratio over the NORMALIZED text) is the confirm/order-sensitive
# signal. drift_delta = 1.0 - seqmatch_ratio. score_pair runs the cheap Jaccard
# gate first and only computes the SequenceMatcher confirm signal for pairs that
# clear it (cheap-then-confirm).
# ---------------------------------------------------------------------------


def seqmatch_ratio(a: str, b: str) -> float:
    """Character-level similarity ratio over the NORMALIZED forms of a and b.

    Wraps ``difflib.SequenceMatcher`` on ``normalize(a)`` / ``normalize(b)`` so
    case, emphasis markers, and whitespace differences do not depress the score.
    Identical normalized text -> 1.0.
    """
    # autojunk=False: with autojunk on, characters appearing in >1% of
    # positions in strings >=200 chars are treated as "popular junk", which can
    # subtly depress the ratio on long instruction blocks; disabling it keeps
    # the confirm/drift signal faithful to true similarity. (None is isjunk.)
    return difflib.SequenceMatcher(
        None, normalize(a), normalize(b), autojunk=False
    ).ratio()


def drift_delta(a: str, b: str) -> float:
    """How far two blocks have drifted apart: ``1.0 - seqmatch_ratio(a, b)``.

    0.0 means identical (post-normalization); larger means more divergence.
    """
    return 1.0 - seqmatch_ratio(a, b)


def score_pair(
    block_a: Block,
    block_b: Block,
    *,
    jaccard_threshold: float,
    confirm_threshold: float,
) -> Pair | None:
    """Score a candidate block pair with the two-signal similarity model.

    Cheap-then-confirm (design §3.5): compute Signal 1 (Jaccard) over the blocks'
    normalized text first; if it is below ``jaccard_threshold`` the pair cannot be
    a duplicate or drift candidate and ``None`` is returned (the Jaccard gate).
    Otherwise compute Signal 2 (SequenceMatcher confirm) and the drift delta, and
    return a populated ``Pair``.

    ``is_drift_candidate`` is ``(jaccard >= jaccard_threshold) and
    (seqmatch_ratio < 1.0)``: it cleared the recall gate but is not a byte-for-byte
    (post-normalization) match. A pair is a *confirmed* duplicate candidate when
    ``seqmatch_ratio >= confirm_threshold``; callers filter on that. ``score_pair``
    returns the ``Pair`` regardless so drift candidates with
    ``seqmatch_ratio < confirm_threshold`` remain available for the drift section.

    No boilerplate check is performed here: boilerplate is excluded exactly once,
    at segmentation time (the SOLE boilerplate guard), so every block reaching
    ``score_pair`` is already de-boilerplated.

    ``contains_safety_marker`` is a Task 4 placeholder (always ``False``); the real
    INLINE-MANDATORY / danger detection is wired in later (design §4.4).
    """
    j = jaccard(block_a.normalized_text, block_b.normalized_text)
    if j < jaccard_threshold:
        return None
    s = seqmatch_ratio(block_a.normalized_text, block_b.normalized_text)
    return Pair(
        a=block_a,
        b=block_b,
        jaccard=j,
        seqmatch_ratio=s,
        drift_delta=1.0 - s,
        is_drift_candidate=j >= jaccard_threshold and s < 1.0,
        contains_safety_marker=False,
    )


# ---------------------------------------------------------------------------
# Segmentation: markdown body only, multi-granularity (design §3.3, §3.4, §3.7)
#
# segment() splits a markdown file's BODY (YAML frontmatter excluded) into Blocks
# at four granularities -- "heading-section", "paragraph", "list-item",
# "fenced-whole" -- each carrying absolute 1-based line numbers, normalized text,
# a parent_key linking it to its enclosing heading-section, and a stable
# block_id.
#
# BOILERPLATE CONTRACT (design §3.4, IMPORTANT 4): structural boilerplate is
# excluded HERE, at segmentation time. This is the SOLE boilerplate guard in the
# whole pipeline -- score_pair() does NOT re-check, because every block reaching
# pairing has already passed this filter. Below-floor blocks (normalized_text
# shorter than min_block_chars) are excluded here too, with the single exception
# of fenced-whole blocks, which are kept regardless of size.
# ---------------------------------------------------------------------------

# Fence openers/closers: ``` or ~~~ runs (design §3.3 "fenced-whole"). A fence is
# matched whole and never sub-segmented.
_FENCE_RE = re.compile(r"^(\s*)(`{3,}|~{3,})")
# ATX heading: 1-6 leading '#', a space, then the heading text (design §3.3).
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
# A top-level (non-indented) list item: -, *, +, or ordered "1." markers.
_LIST_ITEM_RE = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+\S")
# Horizontal rules: ---, ***, ___ (3+), optionally space-separated.
_HRULE_RE = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
# A <ROLE>-style scaffolding stub line (open or close tag on its own line).
_ROLE_STUB_RE = re.compile(r"^\s*</?[A-Z][A-Z_]*>\s*$")


def split_file(text: str) -> tuple[str, str]:
    """Split ``text`` into ``(frontmatter, body)`` (design §3.3).

    A leading YAML frontmatter block fenced by ``---`` on its own first line and
    a matching ``---`` line is excluded from detection; ``frontmatter`` is the
    fenced block (including both fences), ``body`` is everything after. When no
    leading frontmatter is present, ``frontmatter`` is empty and ``body`` is the
    whole text. The body keeps trailing content verbatim so absolute line numbers
    are recoverable by the caller.
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return "", text
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            frontmatter = "".join(lines[: idx + 1])
            body = "".join(lines[idx + 1:])
            return frontmatter, body
    # Unterminated frontmatter fence: treat the whole file as body (no exclusion).
    return "", text


def _is_structural_boilerplate(line: str) -> bool:
    """True if ``line`` is structural scaffolding excluded from candidacy.

    Members (design §3.4): horizontal rules (``---``/``***``/``___``), bare ATX
    headings with no body text, and ``<ROLE>``-style tag stubs. Matched on the
    stripped line so leading/trailing whitespace does not defeat the check.

    NOTE: frontmatter-shaped ``key: value`` lines are deliberately NOT
    boilerplate. :func:`split_file` already strips the YAML frontmatter before
    segmentation, so the body should not contain genuine frontmatter keys.
    Treating ``key:`` lines as boilerplate silently dropped genuine instruction
    prose -- ``Important:``/``Note:``/``Rule:``/``WARNING:``/``Step:``/``TODO:``
    and, critically, ``INLINE-MANDATORY:`` lines all match that shape and are
    exactly the high-value safety content this tool exists to preserve.
    """
    stripped = line.strip()
    if not stripped:
        return True
    if _HRULE_RE.match(stripped):
        return True
    if _ROLE_STUB_RE.match(stripped):
        return True
    # An ATX heading LINE is structural scaffolding on its own (a label, not body
    # prose). A heading-SECTION block survives only when its span carries
    # non-boilerplate body lines too: the segment() filter drops a block whose
    # EVERY line is boilerplate, so a bare "## X" with no body is excluded while
    # "# Top Heading" + prose is kept.
    if _HEADING_RE.match(stripped):
        return True
    return False


def _block_id(file: str, start_line: int, end_line: int, granularity: str) -> str:
    """Stable 16-hex-char block id over ``(file, start_line, end_line, granularity)``
    (design §3.7). Deterministic across runs; unique per distinct block region."""
    key = f"{file}\x00{start_line}\x00{end_line}\x00{granularity}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def _make_block(
    file: str,
    granularity: str,
    start_line: int,
    end_line: int,
    raw_text: str,
    parent_key: str | None,
) -> Block:
    return Block(
        file=file,
        granularity=granularity,
        start_line=start_line,
        end_line=end_line,
        raw_text=raw_text,
        normalized_text=normalize(raw_text),
        parent_key=parent_key,
        block_id=_block_id(file, start_line, end_line, granularity),
    )


def segment(
    file: str,
    text: str,
    *,
    min_block_chars: int = DEFAULT_MIN_BLOCK_CHARS,
) -> list[Block]:
    """Segment a markdown file's body into multi-granularity Blocks (design §3.3).

    Frontmatter is excluded via :func:`split_file`. The body is scanned line by
    line with absolute 1-based line numbers (relative to the whole file including
    frontmatter, so journal ranges are correct). Emits, in source order:

    - **fenced-whole**: a complete ```` ``` ```` / ``~~~`` run as one indivisible
      block; fenced regions are masked so nothing inside is sub-segmented.
    - **heading-section**: an ATX heading; ``parent_key`` is ``None`` for the
      heading-section itself, and descendant paragraph/list-item blocks point at
      the enclosing heading-section's ``block_id``.
    - **paragraph**: a blank-line-delimited prose run.
    - **list-item**: a single top-level list item (with nested continuation).

    Filtering (the SOLE boilerplate guard, design §3.4): blocks whose
    ``normalized_text`` is shorter than ``min_block_chars`` are dropped EXCEPT
    fenced-whole (kept regardless of size); blocks that are structural
    boilerplate are dropped.

    Scope limits (known, intentional): only ATX headings (``#``..``######``)
    are recognized as headings; setext underlines (``===``/``---`` beneath a
    title) are NOT treated as headings. GFM tables are not modeled specially --
    a contiguous table is segmented as an ordinary paragraph run. Supporting
    setext headings or structured tables is out of scope for this helper.
    """
    frontmatter, body = split_file(text)
    offset = frontmatter.count("\n") if frontmatter else 0
    body_lines = body.splitlines()

    # Mask fenced regions first so heading/paragraph/list scanning skips them.
    is_fence: list[bool] = [False] * len(body_lines)
    fence_spans: list[tuple[int, int]] = []  # (start_idx, end_idx) inclusive, 0-based
    i = 0
    while i < len(body_lines):
        m = _FENCE_RE.match(body_lines[i])
        if m:
            marker = m.group(2)
            fence_char = marker[0]
            start = i
            is_fence[i] = True
            i += 1
            while i < len(body_lines):
                is_fence[i] = True
                close = body_lines[i].strip()
                if close and set(close) == {fence_char} and len(close) >= len(marker):
                    i += 1
                    break
                i += 1
            fence_spans.append((start, i - 1))
        else:
            i += 1

    blocks: list[Block] = []

    # fenced-whole blocks.
    for start, end in fence_spans:
        raw = "\n".join(body_lines[start:end + 1])
        blocks.append(
            _make_block(
                file, "fenced-whole",
                offset + start + 1, offset + end + 1,
                raw, None,
            )
        )

    # heading-section blocks + heading membership map (line_idx -> parent block_id).
    heading_lines: list[tuple[int, int]] = []  # (idx, level)
    for idx, line in enumerate(body_lines):
        if is_fence[idx]:
            continue
        m = _HEADING_RE.match(line)
        if m and m.group(2).strip():
            heading_lines.append((idx, len(m.group(1))))

    # Heading-section extent: from the heading to the line before the next heading
    # of equal-or-higher level (design §3.3). The membership map records the
    # heading-section block's OWN block_id so descendants' parent_key matches it.
    heading_block_id_by_line: dict[int, str] = {}
    for hpos, (idx, level) in enumerate(heading_lines):
        end_idx = len(body_lines) - 1
        for nxt_idx, nxt_level in heading_lines[hpos + 1:]:
            if nxt_level <= level:
                end_idx = nxt_idx - 1
                break
        raw = "\n".join(body_lines[idx:end_idx + 1])
        section = _make_block(
            file, "heading-section",
            offset + idx + 1, offset + end_idx + 1,
            raw, None,
        )
        blocks.append(section)
        for body_idx in range(idx, end_idx + 1):
            heading_block_id_by_line[body_idx] = section.block_id

    def _parent_for(idx: int) -> str | None:
        return heading_block_id_by_line.get(idx)

    # paragraph + list-item blocks (skip fences and heading lines).
    j = 0
    n = len(body_lines)
    while j < n:
        if is_fence[j]:
            j += 1
            continue
        line = body_lines[j]
        if not line.strip():
            j += 1
            continue
        heading_match = _HEADING_RE.match(line)
        if heading_match and heading_match.group(2).strip():
            j += 1
            continue
        if _LIST_ITEM_RE.match(line):
            start = j
            j += 1
            # Consume nested continuation: indented or blank-then-indented lines
            # that belong to this top-level item, stopping at the next top-level
            # marker, a heading, a fence, or a blank line followed by non-indent.
            while j < n and not is_fence[j]:
                nxt = body_lines[j]
                if not nxt.strip():
                    break
                if _LIST_ITEM_RE.match(nxt) and not nxt.startswith((" ", "\t")):
                    break
                if _HEADING_RE.match(nxt):
                    break
                if not nxt.startswith((" ", "\t")):
                    break
                j += 1
            raw = "\n".join(body_lines[start:j])
            blocks.append(
                _make_block(file, "list-item", offset + start + 1, offset + j,
                            raw, _parent_for(start))
            )
            continue
        # paragraph: a blank-line-delimited prose run that is not a list/heading.
        start = j
        j += 1
        while j < n and not is_fence[j]:
            nxt = body_lines[j]
            if not nxt.strip():
                break
            if _HEADING_RE.match(nxt) or _LIST_ITEM_RE.match(nxt):
                break
            j += 1
        raw = "\n".join(body_lines[start:j])
        blocks.append(
            _make_block(file, "paragraph", offset + start + 1, offset + j,
                        raw, _parent_for(start))
        )

    # Filter: SOLE boilerplate guard + below-floor (fenced-whole exempt from floor).
    kept: list[Block] = []
    for block in blocks:
        if block.granularity == "fenced-whole":
            kept.append(block)
            continue
        if all(_is_structural_boilerplate(ln) for ln in block.raw_text.splitlines()):
            continue
        if len(block.normalized_text) < min_block_chars:
            continue
        kept.append(block)

    kept.sort(key=lambda b: (b.start_line, b.end_line, b.granularity))
    return kept


def child_in_parent_suppression(pairs: list[Pair]) -> list[Pair]:
    """Drop child-granularity pairs fully contained in a matched parent pair
    (design §3.4): keep the largest coherent match.

    A child pair is suppressed when BOTH its endpoints fall within the line range
    of some other (parent) pair's corresponding endpoints in the same files. The
    parent (wider) pair is retained. (Exercised in Task 6 where pairs exist.)
    """
    def contains(outer: Block, inner: Block) -> bool:
        return (
            outer.file == inner.file
            and outer.start_line <= inner.start_line
            and outer.end_line >= inner.end_line
            and (outer.start_line, outer.end_line) != (inner.start_line, inner.end_line)
        )

    survivors: list[Pair] = []
    for pair in pairs:
        suppressed = False
        for other in pairs:
            if other is pair:
                continue
            if contains(other.a, pair.a) and contains(other.b, pair.b):
                suppressed = True
                break
            if contains(other.a, pair.b) and contains(other.b, pair.a):
                suppressed = True
                break
        if not suppressed:
            survivors.append(pair)
    return survivors


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
