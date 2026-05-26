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
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path


def _resolved_str(p: Path | str) -> str:
    """Canonical POSIX-form resolved path string (cross-platform stable).

    Paths are stored and compared as strings in many places (corpus indexes,
    block.file, candidate file, suffix-match against backticked `.md` refs).
    On Windows ``str(Path(...).resolve())`` yields backslash-separated paths,
    which break every comparison and ``endswith`` lookup against markdown
    refs that use forward slashes. Normalizing via ``Path.as_posix()`` makes
    the resolved-string form identical across platforms while preserving the
    absolute-path semantics that the existing logic depends on.
    """
    return Path(p).resolve().as_posix()

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

# ---------------------------------------------------------------------------
# Apply-journal schema (design §5.3.1)
#
# The apply journal is the durable record of a human-approved consolidation. The
# COMMAND layer (the skill, via the Task tool) WRITES it; the `verify` subcommand
# READS it. This script NEVER edits source `.md` files -- it only reads/writes
# journals and emits JSON (Success Criterion #3 / design §9.4). The schema below
# documents the contract both sides share:
#
#   {
#     "version": "1",                       # JOURNAL_VERSION
#     "created_at": "<ISO-8601 timestamp>",
#     "findings": [
#       {
#         "finding_id": "<stable cluster id>",
#         "status": "pending" | "refs_created" | "sources_edited"
#                   | "verified" | "rolled_back",
#         "reference_files": ["<repo-relative path>", ...],
#         "edits": [
#           {
#             "file": "<repo-relative path of the edited source>",
#             "original_text": "<the duplicate block text that was replaced>",
#             "replacement_text": "<the pointer text that replaced it>",
#             "start_line": <1-based>,
#             "end_line": <1-based>,
#             "content_hash": "sha256:<hexdigest of original_text>"
#           }, ...
#         ]
#       }, ...
#     ]
#   }
#
# `content_hash` is the sha256 of `original_text` (see :func:`_content_hash`) so a
# journal entry can be tied back to the exact source text it consolidated.
# ---------------------------------------------------------------------------

# Journal status enum (design §5.3.1). Documented as the allowed `status` values;
# `verify` reads journals at any status and does not gate on it.
JOURNAL_STATUSES: tuple[str, ...] = (
    "pending",
    "refs_created",
    "sources_edited",
    "verified",
    "rolled_back",
)


def _content_hash(text: str) -> str:
    """The journal ``content_hash`` of a block: ``sha256:<hexdigest of text>``.

    Ties a journal edit to the exact ``original_text`` it consolidated (design
    §5.3.1). The command layer writes this; ``verify`` may use it to reconcile an
    edit with its source. Must match the test helper byte-for-byte.
    """
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()

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
# INLINE-MANDATORY predicate inputs (design §4.4, C6)
#
# These two denylists are the mechanical (non-LLM) basis for the
# INLINE-MANDATORY screen that bars safety content from Read-on-demand routing.
#
# _SAFETY_MARKERS: safety/criticality tokens (design §4.4). A block carrying any
# of these is INLINE-MANDATORY by Clause 1. Matched case-insensitively as
# whole-word tokens so "always"/"never" inside ordinary prose are still caught
# (these words ARE the imperative-safety signal) while substrings inside
# unrelated words are not (e.g. "always" matches, but "ne" inside "one" does
# not, because each marker is bounded by \b on both sides).
#
# _DANGER_DENYLIST: dangerous-action command/verb tokens (design §4.4). A line
# matching any of these is a "dangerous action" for Clause 3 (positional
# in-flow guard detection). Matched case-insensitively as whole-word/command
# tokens, NOT as substrings inside unrelated prose (so "force" matches but
# "reinforcements" does not; "rm" matches but "harm" does not).
#
# MVP override mechanism (post-review fix MINOR 9): _DANGER_DENYLIST is a
# MODULE-LEVEL CONSTANT and is the single point of customization for now. The
# `--danger-denylist` CLI flag described in design §4.4 is DEFERRED -- it is
# intentionally NOT added in this MVP. Operators who need a different denylist
# edit this constant. (Same applies to _SAFETY_MARKERS.)
# ---------------------------------------------------------------------------

_SAFETY_MARKERS: tuple[str, ...] = (
    "CRITICAL",
    "FORBIDDEN",
    "<RULE>",
    "</RULE>",
    "<CRITICAL>",
    "</CRITICAL>",
    "<FORBIDDEN>",
    "</FORBIDDEN>",
    "NEVER",
    "ALWAYS",
    "MUST NOT",
    "Inviolable",
    "Git Safety",
    "you MUST",
    "NEVER do",
    "ALWAYS check",
)

# Note: ``apply`` and ``drop`` are whole-word matches and may OVER-fire on benign
# prose ("apply the discount", "drop a note"). This conservative over-retention is
# intentional and accepted for the MVP: it errs toward keeping a block INLINE-
# MANDATORY (the SAFE direction -- never demotes safety content to Read-on-demand).
# Narrowing these to a command context (e.g. ``git apply`` / ``DROP TABLE``) is a
# DEFERRED follow-up, not done here.
_DANGER_DENYLIST: tuple[str, ...] = (
    "git push",
    "rm",
    "rm -rf",
    "apply",
    "delete",
    "--delete",
    "force",
    "--force",
    "-f",
    "reset --hard",
    "git commit",
    "git checkout",
    "git rebase",
    "git merge",
    "git stash",
    "drop",
    "destroy",
    "truncate",
    "chmod",
    "chown",
)


def _token_pattern(token: str) -> str:
    """Whole-token regex for one denylist/marker token, with adaptive boundaries.

    A token never matches a substring inside an unrelated word ("force" must not
    match "reinforcements"; "rm" must not match "harm"). Boundaries adapt to the
    token's own edges: a ``\\w``-lookaround is applied ONLY on an edge that is a
    word character. Tokens whose edge is non-word (``<RULE>`` ends in ``>``,
    ``--force`` / ``-f`` start with ``-``) get NO lookaround on that edge, so
    they still anchor correctly even when butted against word characters
    (``<RULE>do`` must match ``<RULE>``). The token body is escaped because the
    members contain ``-``, ``<``, ``>``, and spaces.

    Internal whitespace in a multi-word token (``git push``, ``you MUST``,
    ``reset --hard``) is widened to ``\\s+`` so the words match across ANY run of
    whitespace -- a double space, a tab, or a wrapped newline between them. A
    naive ``re.escape(token)`` only matches the single literal space in the
    source token, which silently escapes detection of ``git  push`` (two spaces),
    ``git\\tpush`` (tab), or a line-wrapped ``you\\nMUST`` -- a SAFETY
    false-negative for the danger/marker denylists. ``re.escape`` renders a space
    as ``\\ `` on some Python versions and as a bare space on others, so both
    forms (and runs of them) are folded to ``\\s+`` here.
    """
    body = re.sub(r"(?:\\ |\s)+", r"\\s+", re.escape(token))
    left = r"(?<!\w)" if token[:1].isalnum() or token[:1] == "_" else ""
    right = r"(?!\w)" if token[-1:].isalnum() or token[-1:] == "_" else ""
    return f"{left}{body}{right}"


def _compile_token_alternation(tokens: tuple[str, ...]) -> re.Pattern[str]:
    """Compile a case-insensitive whole-token alternation over ``tokens``.

    Tokens are sorted longest-first so a longer token (``rm -rf``) is preferred
    over a contained shorter one (``rm``) at the same position, and each is
    wrapped with :func:`_token_pattern`'s adaptive whole-token boundaries.
    """
    ordered = sorted(set(tokens), key=len, reverse=True)
    alternation = "|".join(_token_pattern(tok) for tok in ordered)
    return re.compile(f"(?:{alternation})", re.IGNORECASE)


_SAFETY_MARKER_RE = _compile_token_alternation(_SAFETY_MARKERS)
_DANGER_DENYLIST_RE = _compile_token_alternation(_DANGER_DENYLIST)


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


# ---------------------------------------------------------------------------
# INLINE-MANDATORY predicate (design §4.4, C6)
#
# Three pure functions implement the mechanical (non-LLM) safety screen:
#   contains_safety_marker(text) -- Clause 1/2 marker test.
#   danger_lines(file, text)     -- the dangerous-action line map for Clause 3.
#   is_inline_mandatory(block, *, all_lines) -- the predicate itself.
# ---------------------------------------------------------------------------


def contains_safety_marker(text: str) -> bool:
    """True if ``text`` contains any ``_SAFETY_MARKERS`` token (design §4.4).

    Matched case-insensitively as whole-word/command tokens (see
    :func:`_compile_token_alternation`). Covers both the explicit criticality
    markers (``CRITICAL``, ``FORBIDDEN``, ``<RULE>``, ...) and the imperative
    safety phrasings (``you MUST``, ``NEVER``, ``ALWAYS``) of Clauses 1 and 2.
    """
    return _SAFETY_MARKER_RE.search(text) is not None


def danger_lines(file: str, text: str) -> dict[int, str]:
    """Map ``{1-based line number: line text}`` for every dangerous-action line.

    A line is dangerous when it contains any ``_DANGER_DENYLIST`` token (whole
    word/command token, case-insensitive). Numbering is 1-based over the WHOLE
    file (frontmatter included), matching :func:`segment`'s absolute line
    numbers so a Block's ``start_line``/``end_line`` can be compared directly
    against these keys in Clause 3. ``file`` is accepted for call-site symmetry
    with the rest of the pipeline (and future per-file reporting); the mapping
    is computed from ``text`` alone.
    """
    found: dict[int, str] = {}
    for lineno, line in enumerate(text.splitlines(), start=1):
        if _DANGER_DENYLIST_RE.search(line):
            found[lineno] = line
    return found


def is_inline_mandatory(block: Block, *, all_lines: dict[int, str]) -> bool:
    """Mechanical INLINE-MANDATORY predicate (design §4.4, C6).

    A block is INLINE-MANDATORY -- and therefore NEVER eligible for
    Read-on-demand routing -- if ANY of:

    1/2. **Clauses 1 and 2 (markers):** ``contains_safety_marker(block.raw_text)``
       -- the block carries a safety/criticality marker (Clause 1) or
       imperative-safety phrasing directed at the agent (Clause 2). Both clauses
       are folded into the single ``contains_safety_marker`` marker test, which is
       why there is no separate "2." below.
    3. **Clause 3 (positional in-flow guard):** the block *encloses* a dangerous
       action -- a danger line ``L`` from :func:`danger_lines` (``all_lines`` is
       its ``{line: text}`` output) falls within the block's own span
       (``start_line <= L <= end_line``). A heading-section block that contains a
       dangerous-action line is an in-flow guard for that action and must stay
       inline.

    NOTE (scope, plan §"Task 7" / design §4.4): design §4.4 also describes a
    strict child-level Clause 3 variant -- a child block whose ``parent_key``
    equals the *danger line's* enclosing-section block_id and whose ``end_line``
    strictly precedes the danger line. That cross-section disambiguation needs
    per-line parent membership, which the chosen ``all_lines={line: text}``
    boundary does not carry, so it is DEFERRED. The enclosing-section test above
    is the MVP behavior and is what the default segmenter exercises: a sub-floor
    guard paragraph is folded into its enclosing heading-section block, which
    then *encloses* the danger line (``start_line <= L <= end_line``).
    """
    if contains_safety_marker(block.raw_text):
        return True
    return any(
        block.start_line <= lineno <= block.end_line for lineno in all_lines
    )


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

    ``contains_safety_marker`` is the real INLINE-MANDATORY hint (design §4.4,
    wired here): ``True`` when EITHER block's ``raw_text`` carries a safety marker
    (``contains_safety_marker(a.raw_text) or contains_safety_marker(b.raw_text)``).
    A safety marker on either endpoint taints the pair so downstream routing
    cannot demote it to Read-on-demand (C6).
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
        contains_safety_marker=(
            contains_safety_marker(block_a.raw_text)
            or contains_safety_marker(block_b.raw_text)
        ),
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
# Pairing pipeline + union-find clustering (design §3.5, §3.6)
#
# pair_corpus generates every unordered block pair ACROSS DIFFERENT FILES
# (within-file pairs are never produced -- within-file dedup is out of scope,
# FU-1), scores each via score_pair (the cheap Jaccard gate precedes the
# SequenceMatcher confirm), keeps the non-None survivors, and applies
# child_in_parent_suppression so the widest coherent match wins. An optional
# max_pairs cost bound (design §3.6) truncates to the top-N by seqmatch_ratio.
#
# cluster_pairs runs union-find over the confirmed EXTRACT-eligible pairs so an
# instruction repeated N>2 times collapses into ONE cluster instead of a tangle
# of pairwise edges (design §3.5 "From pairs to clusters").
# ---------------------------------------------------------------------------


def pair_corpus(
    blocks: list[Block],
    *,
    jaccard_threshold: float,
    confirm_threshold: float,
    max_pairs: int | None = None,
) -> list[Pair]:
    """Score every cross-file block pair and return the surviving candidates.

    For every unordered pair of blocks whose two endpoints live in DIFFERENT
    files (within-file pairs are skipped -- design §3.5, FU-1), call
    :func:`score_pair`; collect the non-``None`` results; then apply
    :func:`child_in_parent_suppression` so a child-granularity match contained
    within a matched parent (heading-section) match is dropped in favor of the
    widest coherent match. Confirmed-duplicate filtering and drift filtering are
    the caller's job; both confirmed and drift candidates are returned here.

    ``max_pairs`` is the optional per-run cost ceiling (design §3.6). When set
    and the survivor count exceeds it, the survivors are truncated to the top
    ``max_pairs`` by ``seqmatch_ratio`` (descending) -- the strongest matches are
    kept and the weakest dropped, bounding the number of downstream classifier
    dispatches. ``None`` (the default) means no truncation. Ties at the
    truncation boundary are broken by corpus order: the sort is Python's stable
    ``sorted``, so when multiple pairs share the same ``seqmatch_ratio`` the
    one(s) appearing earlier in corpus/block order are kept.
    """
    survivors: list[Pair] = []
    n = len(blocks)
    for i in range(n):
        for k in range(i + 1, n):
            block_a = blocks[i]
            block_b = blocks[k]
            if block_a.file == block_b.file:
                continue
            pair = score_pair(
                block_a,
                block_b,
                jaccard_threshold=jaccard_threshold,
                confirm_threshold=confirm_threshold,
            )
            if pair is not None:
                survivors.append(pair)

    survivors = child_in_parent_suppression(survivors)

    if max_pairs is not None and len(survivors) > max_pairs:
        survivors = sorted(
            survivors, key=lambda p: p.seqmatch_ratio, reverse=True
        )[:max_pairs]
    return survivors


def cluster_pairs(confirmed_pairs: list[Pair]) -> list[set[str]]:
    """Union-find over confirmed pairs -> connected components of ``block_id``s.

    Each ``block_id`` is a node; every confirmed pair unions its two endpoints
    (design §3.5 "From pairs to clusters"). The returned connected components are
    the clusters: an instruction repeated N>2 times (overlapping A-B, B-C, A-C
    pairs) collapses into ONE cluster of N block_ids rather than a tangle of
    pairwise edges.

    Callers must pass only confirmed, EXTRACT-eligible pairs (non-drift,
    non-KEEP): drift and KEEP pairs are never auto-consolidated and therefore
    contribute no edges. This function unions every pair it is given, so
    excluding those pairs is the caller's responsibility.
    """
    parent: dict[str, str] = {}

    def find(node: str) -> str:
        parent.setdefault(node, node)
        root = node
        while parent[root] != root:
            root = parent[root]
        # Path compression keeps repeated finds near-constant time.
        while parent[node] != root:
            parent[node], node = root, parent[node]
        return root

    def union(left: str, right: str) -> None:
        parent[find(left)] = find(right)

    for pair in confirmed_pairs:
        union(pair.a.block_id, pair.b.block_id)

    components: dict[str, set[str]] = {}
    for node in parent:
        root = find(node)
        components.setdefault(root, set()).add(node)
    return list(components.values())


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
    # Sort by POSIX-form resolved path so platform-stable ordering matches the
    # POSIX-form strings used everywhere else (see _resolved_str).
    return sorted((p.resolve() for p in found), key=lambda p: p.as_posix())


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
    # Sort by POSIX-form path for cross-platform stable ordering.
    return sorted(resolved, key=lambda p: p.as_posix())


# ---------------------------------------------------------------------------
# Group expansion: empirical dependency grammar, seed resolution, transitive
# dependents (design §3.1). The index maps artifact NAME -> resolved file path;
# seed entries are resolved as PATHs (end in .md OR exist as a corpus file) or
# NAMEs (via the index); expansion follows the five reference shapes -- the four
# name/link/load/adjacency shapes from `_extract_references` plus the backticked
# `.md`-path shape from `_extract_path_references` (Shape 5, path-bypass
# resolution against the corpus root) -- bounded by --max-depth with a
# visited-set cycle guard. Unresolved reference-shaped strings are surfaced,
# never dropped (C1).
# ---------------------------------------------------------------------------


def build_corpus_index(corpus_files: list[Path]) -> dict[str, str]:
    """Map artifact NAME -> resolved file path over the resolved corpus.

    Operates on the file list returned by ``resolve_corpus`` (the ``--corpus``
    contract), NOT a raw glob. The ``name`` is derived per file:
    - ``skills/<name>/SKILL.md`` -> ``<name>`` (the parent directory name);
    - ``commands/<name>.md`` -> ``<name>`` (the filename stem under a
      ``commands`` directory);
    - any other resolved ``*.md`` (flat fixture files, ``shared-references``)
      -> the filename stem.
    This makes the index work for both the real nested layout and the flat
    unit-test fixture dirs. Later files win on a name collision (stable because
    ``corpus_files`` is sorted).
    """
    index: dict[str, str] = {}
    for path in corpus_files:
        resolved = _resolved_str(path)
        parent = path.parent.name
        if path.name == "SKILL.md" and parent:
            name = parent
        elif parent == "commands":
            name = path.stem
        else:
            name = path.stem
        index[name] = resolved
    return index


def resolve_seed_entry(
    entry: str,
    *,
    corpus_files: list[Path],
    corpus_index: dict[str, str],
) -> tuple[str | None, str | None]:
    """Resolve a single seed entry to ``(path_or_None, name_or_None)``.

    Seed-resolution contract (design §3.1, CRITICAL 2):
    - A seed entry is a **PATH** when it ends in ``.md`` OR exists as a file
      under a corpus root (matched against ``corpus_files`` by resolved path or
      basename). Path-seeds return ``(resolved_path, None)`` and the caller adds
      them to ``expanded_group`` DIRECTLY, bypassing name resolution.
    - Otherwise the entry is a **NAME** resolved via ``corpus_index``: returns
      ``(None, name)`` when the name resolves, else ``(None, None)`` so the
      caller can raise a clear empty/not-found error (design §8).
    """
    resolved_by_path = {_resolved_str(p): _resolved_str(p) for p in corpus_files}
    by_basename = {p.name: _resolved_str(p) for p in corpus_files}

    # ``resolved_by_path`` keys are absolute POSIX-normalized strings (via
    # ``_resolved_str``). Seed entries supplied by the user are often relative
    # (e.g., ``skills/dedupe/SKILL.md``). Normalize ``entry`` the same way for
    # the exact-path lookup so relative seeds match the resolved-keyed index
    # instead of silently falling through to basename matching or literal
    # cwd-relative resolution.
    resolved_entry = _resolved_str(entry)

    is_pathlike = entry.endswith(".md")
    candidate = Path(entry)
    if not is_pathlike:
        # exists-as-file: either the literal path is a real file, or the entry
        # matches a corpus file's resolved path / basename.
        if (
            candidate.is_file()
            or resolved_entry in resolved_by_path
            or entry in by_basename
        ):
            is_pathlike = True

    if is_pathlike:
        # Resolve the path-seed against the corpus: prefer an exact resolved-path
        # match, then a basename match, then the literal resolved path.
        if resolved_entry in resolved_by_path:
            return resolved_by_path[resolved_entry], None
        if entry in by_basename:
            return by_basename[entry], None
        if candidate.is_file():
            return _resolved_str(candidate), None
        # ends in .md but not in the corpus -> still a path, resolve literally.
        return _resolved_str(candidate), None

    # NAME path: resolve through the index.
    if entry in corpus_index:
        return None, entry
    return None, None


# Reference-extraction regexes (design §3.1, the four empirical shapes).
#
# Shapes 1 and 3 capture the backtick delimiters as explicit groups so the
# extractor can tell a backticked artifact name (e.g. ``invoked by `develop```)
# apart from a bare prose word (``invoked by the system``). The optional
# ``(?:the\s+)?`` article (I2) lets the real target be captured in phrasings
# like ``invoked by the develop skill``.
_DESC_INVOKED_RE = re.compile(
    r"\b(?:invoked\s+by|invokes)\s+(?:the\s+)?(`?)([a-z0-9][a-z0-9._-]*)(`?)",
    re.IGNORECASE,
)
_LINK_SKILL_RE = re.compile(r"\(([^)]*?skills/([a-z0-9._-]+)/SKILL\.md)\)", re.IGNORECASE)
_LINK_COMMAND_RE = re.compile(r"\(([^)]*?commands/([a-z0-9._-]+)\.md)\)", re.IGNORECASE)
_LOAD_SKILL_RE = re.compile(
    r"\bLoad\s+(?:the\s+)?(`?)([a-z0-9][a-z0-9._-]*)(`?)\s+skill\b",
    re.IGNORECASE,
)
# A backticked token capture, used for the bare-name adjacency shape.
_BACKTICK_TOKEN_RE = re.compile(r"`([a-z0-9][a-z0-9._-]*)`")
_SENTENCE_SPLIT_RE = re.compile(r"[.!?\n]")

# Shape 5 (Task 13): a backticked inline-code span whose content is a PATH
# ending in ``.md`` -- e.g. the nested form (a backticked ``commands/...md``) or
# the bare form (a backticked ``foo.md``). This is a HIGH-precision reference: it
# names a real file, so there is zero prose-stopword risk and no adjacency
# heuristic is needed. The captured group is the raw path string, kept VERBATIM
# (including any ``..`` or leading ``/`` components) so the resolver can decide
# SAFELY whether it maps to a corpus file. Allowed path chars are alphanumerics
# plus ``/ . - _ ~``; the span must end in ``.md`` immediately before the closing
# backtick. A bare backticked WORD with no ``.md`` suffix is NOT matched here --
# it stays a name-ref handled by Shape 4's adjacency rule (no regression). The
# ``~`` is matched literally and never expanduser()-expanded -- a captured
# ``~/foo.md`` is resolved as a literal path and (landing outside the corpus)
# surfaces as unresolved rather than escaping to the home directory.
_BACKTICK_PATH_RE = re.compile(r"`([A-Za-z0-9_./~-]+\.md)`")

# Common English stopwords that prose phrasings ("invoked by the system",
# "invokes a callback") would otherwise leak into unresolved_references. Belt
# and suspenders alongside the artifact-name-shape guard in ``_is_artifact_name``.
_REFERENCE_STOPWORDS = frozenset(
    {"the", "a", "an", "this", "it", "that", "these", "those", "your", "our"}
)


def _is_artifact_name(name: str, *, backticked: bool) -> bool:
    """Return True only for tokens that plausibly name a corpus artifact.

    A capture qualifies when it is backticked in the source OR is a hyphenated
    kebab token (contains a ``-``). A bare single English word that is neither
    backticked nor hyphenated is rejected so prose stopwords ("the", "system",
    "configuration") never reach ``unresolved_references`` (C1 integrity).
    Stopwords are additionally denied even when backticked.
    """
    if name.lower() in _REFERENCE_STOPWORDS:
        return False
    return backticked or "-" in name


def _extract_references(
    text: str, corpus_index: dict[str, str]
) -> tuple[set[str], set[str]]:
    """Parse one file's text against the empirical dependency grammar.

    Returns ``(resolved_names, unresolved_strings)``:
    - ``resolved_names``: reference targets that resolve to a corpus artifact
      (followed during expansion);
    - ``unresolved_strings``: reference-shaped strings that match structurally
      but resolve to nothing (C1: surfaced, never dropped).
    """
    resolved: set[str] = set()
    unresolved: set[str] = set()

    def record(name: str) -> None:
        if name in corpus_index:
            resolved.add(name)
        else:
            unresolved.add(name)

    # Shape 1: description conventions (invoked by / invokes <name>). Only a
    # backticked or hyphenated artifact name is recorded; bare prose words
    # ("invoked by the system", "invokes a callback") are skipped (I1/I2).
    for m in _DESC_INVOKED_RE.finditer(text):
        backticked = bool(m.group(1) and m.group(3))
        if _is_artifact_name(m.group(2), backticked=backticked):
            record(m.group(2))
    # Shape 2: markdown links to skills/<name>/SKILL.md and commands/<name>.md.
    for m in _LINK_SKILL_RE.finditer(text):
        record(m.group(2))
    for m in _LINK_COMMAND_RE.finditer(text):
        record(m.group(2))
    # Shape 3: Load <name> skill / Load the <name> skill imperatives. Same
    # artifact-name-shape guard as Shape 1 ("Load configuration skill" -> skip).
    for m in _LOAD_SKILL_RE.finditer(text):
        backticked = bool(m.group(1) and m.group(3))
        if _is_artifact_name(m.group(2), backticked=backticked):
            record(m.group(2))
    # Shape 4: bare backticked `name` adjacent to the word "skill"/"command".
    # Adjacency = same sentence OR within ADJACENCY_TOKEN_WINDOW whitespace
    # tokens, whichever boundary is hit first. A backticked token that is
    # reference-shaped (adjacent to skill/command) but does not resolve is
    # surfaced as unresolved (C1); a resolving one is followed.
    for sentence in _SENTENCE_SPLIT_RE.split(text):
        tokens = sentence.split()
        # Index of each whitespace token; find skill/command anchor positions.
        anchor_positions = [
            i for i, tok in enumerate(tokens)
            if tok.lower().strip(".,;:") in ("skill", "skills", "command", "commands")
        ]
        if not anchor_positions:
            continue
        for i, tok in enumerate(tokens):
            bt = _BACKTICK_TOKEN_RE.search(tok)
            if not bt:
                continue
            name = bt.group(1)
            # Same sentence is already guaranteed (we split on sentence
            # boundaries); additionally honor the K-token window as the tighter
            # of the two adjacency boundaries.
            within_window = any(
                abs(i - pos) <= ADJACENCY_TOKEN_WINDOW for pos in anchor_positions
            )
            if within_window:
                record(name)

    return resolved, unresolved


def _extract_path_references(text: str) -> set[str]:
    """Extract Shape-5 backticked ``.md``-PATH references from one file's text.

    A backticked inline-code span whose content is a path ending in ``.md`` (the
    nested form, a backticked ``commands/...md``, or the bare form, a backticked
    ``foo.md``) is a HIGH-precision PATH reference (design §3.1, Shape 5). Returns
    the set of raw path strings VERBATIM (caller resolves them via the path-bypass
    resolver, NOT
    the name index). Kept SEPARATE from :func:`_extract_references` so the
    existing ``(resolved, unresolved)`` 2-tuple contract -- and the tests that
    assert on it -- are unchanged: name-refs and path-refs are distinct shapes.
    """
    return {m.group(1) for m in _BACKTICK_PATH_RE.finditer(text)}


def resolve_path_reference(
    ref: str,
    *,
    from_file: str,
    corpus_by_resolved: dict[str, str],
) -> str | None:
    """Resolve a Shape-5 backticked ``.md``-PATH reference to a corpus file.

    A path-reference is resolved by PATH (mirroring :func:`resolve_seed_entry`'s
    path-bypass), NOT via the name index. Resolution tries, in order:

    1. **Repo-relative / common-prefix suffix match:** a corpus file whose
       resolved path ENDS WITH ``/<ref>`` (or equals ``<ref>``). This is the
       primary case -- well-authored skills reference family members by
       repo-relative path (``commands/dedupe-setup.md``), and the corpus files'
       resolved paths share that repo prefix.
    2. **Relative to the referencing file's directory:** resolve ``ref`` against
       ``dirname(from_file)`` and look up the result in the corpus.

    Absolute paths and ``..`` traversal are resolved SAFELY: the candidate is
    only accepted when it lands on a file that is actually IN the corpus
    (``corpus_by_resolved``). A path that resolves outside the corpus -- including
    ``/etc/shadow.md`` or ``../../../etc/passwd.md`` -- returns ``None`` so the
    caller records it as unresolved rather than following it. Returns the resolved
    corpus path string, or ``None`` when ``ref`` does not map to a corpus file.
    """
    # 1. Suffix match against resolved corpus paths (repo-relative refs).
    #    Corpus keys are ABSOLUTE, so the ``"/" + ref`` anchored ``endswith``
    #    already subsumes an exact ``resolved == ref`` comparison (a bare ref is
    #    never absolute); the anchoring also keeps component-boundary precision
    #    so ``evil/passwd.md`` cannot match a ``sswd.md`` ref. When a ref
    #    suffix-matches MULTIPLE corpus members (e.g. ``a/config.md`` and
    #    ``b/config.md`` both match a bare ``config.md``), pick a STABLE winner
    #    deterministically: shortest resolved path wins, ties broken
    #    lexicographically. ``corpus_by_resolved`` keys come from a set
    #    (hash-randomized iteration), so returning "first seen" would be
    #    nondeterministic across processes -- the rest of the module is sorted,
    #    so this keeps resolution consistent too.
    suffix = "/" + ref.lstrip("/")
    matches = [r for r in corpus_by_resolved if r.endswith(suffix)]
    if matches:
        return min(matches, key=lambda p: (len(p), p))
    # 2. Relative to the referencing file's directory (only for non-absolute
    #    refs; an absolute ref is anchored, not relative to from_file).
    if not ref.startswith("/"):
        try:
            candidate = (Path(from_file).parent / ref).resolve().as_posix()
        except (OSError, ValueError):
            candidate = None
        if candidate is not None and candidate in corpus_by_resolved:
            return candidate
    return None


def expand_group(
    seed: list[str],
    *,
    corpus_files: list[Path],
    corpus_index: dict[str, str],
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> tuple[list[str], list[str]]:
    """Expand seeds to the transitive dependents via the empirical grammar.

    Each seed entry is resolved via ``resolve_seed_entry``: path-seeds enter
    ``expanded_group`` directly (bypassing name resolution), name-seeds resolve
    through ``corpus_index``. From the resolved seeds, a breadth-first traversal
    with a visited-set (cycle guard) follows the five reference shapes -- the
    four name/link/load/adjacency shapes from ``_extract_references`` plus the
    backticked ``.md``-path shape from ``_extract_path_references`` (Shape 5,
    resolved via the path-bypass against the corpus root) -- bounded by
    ``max_depth`` and the corpus. Returns ``(expanded_group_paths,
    unresolved_references)`` -- both sorted/de-duplicated. A seed that resolves
    to neither a path nor a known name raises ``ValueError`` (design §8).

    Note: references INSIDE an out-of-corpus path-seed are intentionally not
    traversed -- only files that are part of the corpus are read and followed.
    """
    path_by_resolved = {_resolved_str(p) for p in corpus_files}
    # Same resolved-path set as a dict for the Shape-5 path-bypass resolver,
    # which membership-tests resolved candidates against the corpus.
    corpus_by_resolved = {p: p for p in path_by_resolved}

    expanded: set[str] = set()
    unresolved: set[str] = set()
    # frontier holds (path, depth). Paths only; names are mapped to paths first.
    # Use a deque so the BFS pop is O(1) at the head (popleft) instead of the
    # O(n) list.pop(0) shift; FIFO ordering and BFS semantics are unchanged.
    frontier: deque[tuple[str, int]] = deque()

    for entry in seed:
        path, name = resolve_seed_entry(
            entry, corpus_files=corpus_files, corpus_index=corpus_index
        )
        if path is not None:
            expanded.add(path)
            frontier.append((path, 0))
        elif name is not None:
            resolved_path = corpus_index[name]
            expanded.add(resolved_path)
            frontier.append((resolved_path, 0))
        else:
            raise ValueError(f"seed not found (no matching path or name): {entry!r}")

    visited: set[str] = set()
    while frontier:
        path, depth = frontier.popleft()
        if path in visited:
            continue
        visited.add(path)
        if depth >= max_depth:
            continue
        # Only traverse references inside files that are part of the corpus.
        if path not in path_by_resolved:
            continue
        try:
            text = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            # Surface skipped corpus reads so a file that should be in the
            # group but is unreadable does not vanish silently. Stderr keeps
            # the JSON-on-stdout contract intact.
            sys.stderr.write(
                f"dedupe: skipped {path}: {type(e).__name__}: {e}\n"
            )
            continue
        resolved_names, unresolved_strings = _extract_references(text, corpus_index)
        unresolved.update(unresolved_strings)
        for ref_name in resolved_names:
            ref_path = corpus_index[ref_name]
            if ref_path not in expanded:
                expanded.add(ref_path)
            if ref_path not in visited:
                frontier.append((ref_path, depth + 1))

        # Shape 5: backticked `.md`-PATH references resolve via the path-bypass
        # (against the corpus root), NOT the name index. A path that maps to a
        # corpus file is followed (cycle-guard + max_depth still apply); one that
        # does not map to any corpus file -- including unsafe absolute / `..`
        # paths -- is surfaced as unresolved (C1), never followed or crashed on.
        for path_ref in _extract_path_references(text):
            resolved_path = resolve_path_reference(
                path_ref, from_file=path, corpus_by_resolved=corpus_by_resolved
            )
            if resolved_path is None:
                unresolved.add(path_ref)
                continue
            if resolved_path not in expanded:
                expanded.add(resolved_path)
            if resolved_path not in visited:
                frontier.append((resolved_path, depth + 1))

    return sorted(expanded), sorted(unresolved)


# ---------------------------------------------------------------------------
# Subcommand handlers (Task 1: stubs emitting a valid JSON shell; filled in
# by later tasks)
# ---------------------------------------------------------------------------


def _emit_shell() -> int:
    print(json.dumps({"version": SCHEMA_VERSION}, indent=2, ensure_ascii=False))
    return 0


def cmd_expand_group(args: argparse.Namespace) -> int:
    corpus_files = resolve_corpus(args.corpus)
    corpus_index = build_corpus_index(corpus_files)
    try:
        expanded_group, unresolved_references = expand_group(
            args.seed,
            corpus_files=corpus_files,
            corpus_index=corpus_index,
            max_depth=args.max_depth,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    payload = {
        "version": SCHEMA_VERSION,
        "seed": list(args.seed),
        "corpus": [p.as_posix() for p in corpus_files],
        "expanded_group": expanded_group,
        "unresolved_references": unresolved_references,
        "group_size": len(expanded_group),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------------------
# External-caller scan (design §5.4, C5) + detect pipeline (design §3.6, §3.9)
#
# external_caller_scan answers the safety question for EXTRACT: before a block is
# recommended for replace-with-reference, scan the WHOLE corpus for blocks that
# live OUTSIDE the group and resemble the candidate. Any out-of-group match is a
# "load-bearing-for-externals" warning (design §5.4): the operator must see the
# blast radius. The match signal is INLINE Jaccard (Signal 1) -- robust to
# reorder/copy-paste-with-edits -- NOT the order-sensitive SequenceMatcher ratio,
# and the threshold is the dedicated, looser --external-threshold (default 0.7).
#
# group_files lets the SAME function serve two callers:
#   - the standalone `external-callers` subcommand passes no group_files, so it
#     scans the whole corpus minus each candidate's own file (group context is
#     unknown there);
#   - the integrated `detect` path passes the full expanded-group set, so the
#     scan only matches against the out-of-group files (corpus - group).
# ---------------------------------------------------------------------------


def external_caller_scan(
    candidate_blocks: list[Block],
    *,
    corpus_roots: list[Path],
    group_files: frozenset[str] = frozenset(),
    external_threshold: float = DEFAULT_EXTERNAL_THRESHOLD,
) -> list[dict]:
    """Scan out-of-group corpus files for blocks resembling the candidates.

    For each candidate block, segment every corpus file that is NOT in
    ``group_files`` AND is not the candidate's own ``file`` (so a block never
    reports itself), compute the INLINE **Jaccard** ``match_ratio`` against each
    such out-of-group block, and record a caller dict when
    ``match_ratio >= external_threshold`` (design §5.4: Jaccard is robust to
    reorder; the looser threshold widens the safety net).

    ``group_files`` is a set of resolved file-path strings; it defaults to empty
    so the standalone subcommand (no group context) scans the whole corpus minus
    self-file, while the integrated ``detect`` caller passes the full group set so
    only out-of-group files are scanned.

    Each caller dict is ``{block_id, caller_file, caller_start_line, match_ratio,
    match_signal: "jaccard"}`` (design §3.8/§3.9 external-callers shape). The
    returned list is sorted by ``(block_id, caller_file, caller_start_line)`` so
    output is deterministic and stable across runs.
    """
    callers: list[dict] = []
    resolved_corpus = [_resolved_str(p) for p in corpus_roots]
    # Cache per-file segmentation so each out-of-group file is parsed once even
    # when several candidates are compared against it.
    segmented: dict[str, list[Block]] = {}

    def _blocks_for(path_str: str) -> list[Block]:
        if path_str not in segmented:
            try:
                text = Path(path_str).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                segmented[path_str] = []
            else:
                segmented[path_str] = segment(path_str, text)
        return segmented[path_str]

    for candidate in candidate_blocks:
        candidate_file = _resolved_str(candidate.file)
        for path_str in resolved_corpus:
            if path_str in group_files:
                continue
            if path_str == candidate_file:
                continue
            for block in _blocks_for(path_str):
                ratio = jaccard(candidate.normalized_text, block.normalized_text)
                if ratio >= external_threshold:
                    callers.append(
                        {
                            "block_id": candidate.block_id,
                            "caller_file": path_str,
                            "caller_start_line": block.start_line,
                            "match_ratio": ratio,
                            "match_signal": "jaccard",
                        }
                    )

    callers.sort(
        key=lambda c: (c["block_id"], c["caller_file"], c["caller_start_line"])
    )
    return callers


def _block_endpoint(
    block: Block,
    *,
    danger_by_file: dict[str, dict[int, str]] | None = None,
) -> dict:
    """The compact §3.9 endpoint view of a Block (a/b in a pair JSON entry).

    Carries ``parent_key`` (enclosing heading-section block_id, or ``None`` for
    a heading-section root) so the analyze command can compute the INLINE-
    MANDATORY child-level Clause-3 variant downstream (commands/dedupe-analyze.md
    Phase 3). Also carries ``inline_mandatory`` -- the full predicate from
    :func:`is_inline_mandatory`, evaluated against the block's own file's
    ``danger_lines`` map so Clauses 1, 2, AND 3 are all reflected in detect
    output (the analyze command's INLINE-MANDATORY screen relies on this).

    When ``danger_by_file`` is omitted, the predicate falls back to
    ``all_lines={}`` so only Clauses 1 and 2 (marker-based) contribute. The
    integrated ``detect`` pipeline always passes the full map.
    """
    if danger_by_file is None:
        all_lines: dict[int, str] = {}
    else:
        all_lines = danger_by_file.get(block.file, {})
    return {
        "file": block.file,
        "granularity": block.granularity,
        "start_line": block.start_line,
        "end_line": block.end_line,
        "block_id": block.block_id,
        "parent_key": block.parent_key,
        "inline_mandatory": is_inline_mandatory(block, all_lines=all_lines),
    }


def _pair_to_json(
    pair: Pair,
    *,
    danger_by_file: dict[str, dict[int, str]] | None = None,
) -> dict:
    """Serialize a Pair to the §3.9 detect-schema entry (a_text/b_text carry the
    normalized block text so the skill builds classifier prompts without
    re-reading files)."""
    return {
        "a": _block_endpoint(pair.a, danger_by_file=danger_by_file),
        "b": _block_endpoint(pair.b, danger_by_file=danger_by_file),
        "jaccard": pair.jaccard,
        "seqmatch_ratio": pair.seqmatch_ratio,
        "drift_delta": pair.drift_delta,
        "is_drift_candidate": pair.is_drift_candidate,
        "contains_safety_marker": pair.contains_safety_marker,
        "a_text": pair.a.normalized_text,
        "b_text": pair.b.normalized_text,
    }


def cmd_detect(args: argparse.Namespace) -> int:
    """Full detect pipeline -> §3.9 GroupResult JSON (design §3.6, §3.9, §5.4).

    expand-group -> segment the group -> pair within the group -> partition the
    corpus into group vs out-of-group -> external-caller scan over the
    out-of-group files for EXTRACT-eligible candidates -> apply the --max-pairs
    cost ceiling -> emit the §3.9 schema with deterministic ordering.
    """
    corpus_files = resolve_corpus(args.corpus)
    corpus_index = build_corpus_index(corpus_files)
    try:
        expanded_group, unresolved_references = expand_group(
            args.seed,
            corpus_files=corpus_files,
            corpus_index=corpus_index,
            max_depth=args.max_depth,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    # group_files = the expanded group (what we may edit); the out-of-group set
    # (corpus - group) is everything the external scan must protect (§3.2/§5.4).
    group_files = frozenset(expanded_group)

    # Segment every file in the group, then pair within the group only.
    # Also collect each file's danger_lines map so the INLINE-MANDATORY
    # predicate (Clauses 1+2+3) can be evaluated per endpoint in
    # _block_endpoint -- the analyze command depends on this in Phase 3.
    group_blocks: list[Block] = []
    danger_by_file: dict[str, dict[int, str]] = {}
    for path_str in expanded_group:
        try:
            text = Path(path_str).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            sys.stderr.write(
                f"dedupe: skipped {path_str}: {type(e).__name__}: {e}\n"
            )
            continue
        group_blocks.extend(
            segment(path_str, text, min_block_chars=args.min_block_chars)
        )
        danger_by_file[path_str] = danger_lines(path_str, text)

    all_pairs = pair_corpus(
        group_blocks,
        jaccard_threshold=args.jaccard_threshold,
        confirm_threshold=args.confirm_threshold,
    )

    confirmed = [
        p for p in all_pairs if p.seqmatch_ratio >= args.confirm_threshold
    ]
    candidate_count = len(confirmed)

    # EXTRACT-eligible candidates: distinct endpoints of confirmed, non-drift,
    # non-safety in-group pairs (design §5.4). Safety-marked pairs are never
    # EXTRACT-eligible, so they seed no external scan.
    extract_blocks: dict[str, Block] = {}
    for pair in confirmed:
        if pair.is_drift_candidate or pair.contains_safety_marker:
            continue
        extract_blocks.setdefault(pair.a.block_id, pair.a)
        extract_blocks.setdefault(pair.b.block_id, pair.b)

    external_callers = external_caller_scan(
        list(extract_blocks.values()),
        corpus_roots=corpus_files,
        group_files=group_files,
        external_threshold=args.external_threshold,
    )

    # Cost ceiling (§3.6): `pairs` is CONFIRMED-ONLY in BOTH branches -- the
    # membership criterion does not change with the ceiling. When the confirmed
    # count exceeds --max-pairs, truncate to the top-N confirmed pairs by
    # seqmatch_ratio (descending); never silently drop -- flag it. Non-confirmed
    # jaccard-survivors (seqmatch_ratio < confirm_threshold) are never emitted.
    cost_ceiling_exceeded = candidate_count > args.max_pairs
    if cost_ceiling_exceeded:
        emitted_pairs = sorted(
            confirmed, key=lambda p: p.seqmatch_ratio, reverse=True
        )[: args.max_pairs]
    else:
        emitted_pairs = list(confirmed)

    # Deterministic ordering (Task 6 suggestion #3): sort the emitted pairs by
    # (a.block_id, b.block_id) so output diffs/journals are stable across runs.
    emitted_pairs.sort(key=lambda p: (p.a.block_id, p.b.block_id))

    payload = {
        "version": SCHEMA_VERSION,
        "seed": list(args.seed),
        "corpus": [p.as_posix() for p in corpus_files],
        "expanded_group": expanded_group,
        "unresolved_references": unresolved_references,
        "cost_ceiling_exceeded": cost_ceiling_exceeded,
        "candidate_count": candidate_count,
        "pairs": [
            _pair_to_json(p, danger_by_file=danger_by_file)
            for p in emitted_pairs
        ],
        "external_callers": external_callers,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def cmd_external_callers(args: argparse.Namespace) -> int:
    """Standalone external-reference scan over a supplied block list (design §5.4,
    §3.8). Loads --blocks-json (a JSON array of Block-shaped dicts), rehydrates
    Blocks, and scans the whole --corpus minus each candidate's own file (no group
    context). Emits {version, external_callers: [...]}."""
    corpus_files = resolve_corpus(args.corpus)
    if not args.blocks_json:
        print("--blocks-json is required for external-callers", file=sys.stderr)
        return 2
    try:
        raw = Path(args.blocks_json).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"cannot read --blocks-json: {exc}", file=sys.stderr)
        return 2
    try:
        records = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"invalid --blocks-json: {exc}", file=sys.stderr)
        return 2
    if not isinstance(records, list):
        print("--blocks-json must be a JSON array of Block objects", file=sys.stderr)
        return 2

    try:
        blocks = [Block(**record) for record in records]
    except TypeError as exc:
        print(f"invalid --blocks-json record shape: {exc}", file=sys.stderr)
        return 2
    external_callers = external_caller_scan(
        blocks,
        corpus_roots=corpus_files,
        external_threshold=args.external_threshold,
    )
    payload = {"version": SCHEMA_VERSION, "external_callers": external_callers}
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def _block_matches_text(blocks: list[Block], target_norm: str, threshold: float) -> bool:
    """True if any block's normalized text matches ``target_norm`` at/above
    ``threshold`` (SequenceMatcher confirm signal). ``target_norm`` is already
    normalized; each block carries its own ``normalized_text``."""
    return any(
        seqmatch_ratio(block.normalized_text, target_norm) >= threshold
        for block in blocks
    )


def _verify_finding(
    finding: dict, *, corpus_root: Path, threshold: float
) -> dict:
    """Verify a single journal finding against the on-disk corpus (design §5.3.1).

    A finding PASSES only when BOTH clauses hold for EVERY edit in it:

    - **Clause 1 (original duplicate absent):** re-segment the edited source file
      and confirm NO block matches the edit's ``original_text`` at/above the
      confirm threshold. Matching ``original_text`` (not requiring it to be a
      standalone block) avoids depending on the post-edit text re-segmenting the
      duplicate as one block.
    - **Clause 2 (pointer present + reference exists):** the edited source file's
      text contains the edit's ``replacement_text`` (the pointer), AND each of the
      finding's ``reference_files`` exists, is readable, and contains the
      consolidated block (a block matching ``original_text`` at/above the confirm
      threshold).

    Returns ``{finding_id, pass, reasons}``; ``reasons`` names which clause failed
    (empty when the finding passes).
    """
    finding_id = finding.get("finding_id")
    reference_files = finding.get("reference_files") or []
    edits = finding.get("edits") or []
    reasons: list[str] = []

    # A finding with no edits checks nothing; it must not vacuously pass (a green
    # mirage reporting a consolidation "landed" while verifying nothing).
    if not edits:
        reasons.append("no edits recorded for finding")

    # Reference-file resolution is shared across every edit in the finding: each
    # reference file must exist, be readable, and carry the consolidated block.
    def _reference_ok(original_norm: str) -> tuple[bool, list[str]]:
        problems: list[str] = []
        if not reference_files:
            problems.append("clause2: finding lists no reference_files")
            return False, problems
        all_ok = True
        for ref_rel in reference_files:
            ref_path = (corpus_root / ref_rel).resolve()
            try:
                ref_text = ref_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                problems.append(
                    f"clause2: reference file missing/unreadable: {ref_rel}"
                )
                all_ok = False
                continue
            # Design §5.3.1 clause 2 requires the reference to CONTAIN the
            # consolidated block: a re-segmented block matching original_text at
            # or above the confirm threshold. A whole-file seqmatch fallback can
            # false-PASS a reference where the canonical content is fragmented
            # across non-contiguous blocks, so we rely on per-block matching only.
            ref_blocks = segment(str(ref_path), ref_text, min_block_chars=0)
            if not _block_matches_text(ref_blocks, original_norm, threshold):
                problems.append(
                    f"clause2: reference file does not contain the consolidated "
                    f"block: {ref_rel}"
                )
                all_ok = False
        return all_ok, problems

    for edit in edits:
        original_text = edit.get("original_text", "")
        replacement_text = edit.get("replacement_text", "")
        source_rel = edit.get("file", "")
        original_norm = normalize(original_text)

        source_path = (corpus_root / source_rel).resolve()
        try:
            source_text = source_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            reasons.append(f"clause1/2: source file missing/unreadable: {source_rel}")
            continue

        # Clause 1: the original duplicate must be ABSENT from the edited source.
        source_blocks = segment(str(source_path), source_text, min_block_chars=0)
        if _block_matches_text(source_blocks, original_norm, threshold):
            reasons.append(
                f"clause1: original duplicate still present in {source_rel}"
            )

        # Clause 2a: the pointer (replacement_text) must be PRESENT in the source.
        if replacement_text and replacement_text not in source_text:
            reasons.append(
                f"clause2: pointer (replacement_text) absent from {source_rel}"
            )

        # Clause 2b: each reference file exists and holds the consolidated block.
        ref_ok, ref_problems = _reference_ok(original_norm)
        if not ref_ok:
            reasons.extend(ref_problems)

    return {"finding_id": finding_id, "pass": not reasons, "reasons": reasons}


def _verify_corpus_root(corpus_arg: str | None) -> Path:
    """Derive the single root that repo-relative journal paths resolve against.

    Honors the comma-separated --corpus contract: a lone directory is the root;
    multiple entries use their common ancestor; a lone file uses its parent;
    omitted falls back to the spellbook dir.
    """
    if not corpus_arg:
        return _spellbook_dir()
    entries = [Path(e.strip()).resolve() for e in corpus_arg.split(",") if e.strip()]
    if not entries:
        return _spellbook_dir()
    if len(entries) == 1:
        return entries[0] if entries[0].is_dir() else entries[0].parent
    return Path(os.path.commonpath([str(e) for e in entries]))


def cmd_verify(args: argparse.Namespace) -> int:
    """Post-apply verification of an apply journal (design §5.3.1, §3.8, §9.4).

    Reads ``--journal`` (the apply journal written by the command layer) and, for
    each finding, asserts the consolidation actually landed: the original
    duplicate is gone from each edited source (Clause 1) and the pointer plus its
    canonical reference file are present (Clause 2). The corpus root from
    ``--corpus`` resolves the journal's repo-relative ``file`` / ``reference_files``
    paths.

    The confirm gate is the module ``DEFAULT_CONFIRM_THRESHOLD`` (0.85), NOT a CLI
    flag. This subcommand reads journals and emits JSON ONLY -- it NEVER edits any
    source ``.md`` file (Success Criterion #3). Emits
    ``{version, results: [{finding_id, pass, reasons}]}``.
    """
    if not args.journal:
        print("--journal is required for verify", file=sys.stderr)
        return 2
    try:
        raw = Path(args.journal).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"cannot read --journal: {exc}", file=sys.stderr)
        return 2
    try:
        journal = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"invalid --journal: {exc}", file=sys.stderr)
        return 2
    if not isinstance(journal, dict) or not isinstance(journal.get("findings"), list):
        print("--journal must be an object with a 'findings' array", file=sys.stderr)
        return 2

    corpus_root = _verify_corpus_root(args.corpus)

    results = [
        _verify_finding(
            finding, corpus_root=corpus_root, threshold=DEFAULT_CONFIRM_THRESHOLD
        )
        for finding in journal["findings"]
    ]
    payload = {"version": SCHEMA_VERSION, "results": results}
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


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
