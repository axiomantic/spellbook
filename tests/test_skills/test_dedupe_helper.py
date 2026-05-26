"""Unit tests for skills/dedupe/scripts/dedupe.py.

Loads the helper as a module via importlib (without executing main) and
exercises each subcommand against seeded fixture corpora. Default suite --
no integration marker; pure stdlib, no QMD/Serena.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

HELPER_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "skills" / "dedupe" / "scripts" / "dedupe.py"
)
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "dedupe"


@pytest.fixture
def dedupe():
    spec = importlib.util.spec_from_file_location("_dedupe_helper_test", HELPER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _run(module, *argv: str) -> tuple[int, str, str]:
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = module.main(list(argv))
    return rc, out.getvalue(), err.getvalue()


# ---------------------------------------------------------------------------
# Task 1: skeleton smoke tests (plan §"Task 1" Step 1)
# ---------------------------------------------------------------------------


def test_module_loads_and_exposes_main(dedupe):
    assert callable(dedupe.main)


def test_no_args_returns_zero_with_usage(dedupe):
    rc, stdout, _ = _run(dedupe)
    assert rc == 0
    assert "dedupe" in stdout.lower()


def test_unknown_subcommand_is_error(dedupe):
    rc, _, _ = _run(dedupe, "bogus-subcommand")
    assert rc != 0


# ---------------------------------------------------------------------------
# Task 1: the subcommands are registered and dispatchable. NOTE: every
# subcommand is now implemented -- ``expand-group`` (Task 8), ``detect`` and
# ``external-callers`` (Task 9), and ``verify`` (Task 10) -- so their real
# behavior is covered by their respective ``test_*`` blocks below. The former
# stub parametrization (which asserted a bare ``{"version": "1"}`` shell) is
# retired; ``verify`` with no ``--journal`` now validates its input and returns 2
# like the sibling subcommands.
# ---------------------------------------------------------------------------


def test_schema_version_constant(dedupe):
    assert dedupe.SCHEMA_VERSION == "1"


def test_verify_requires_journal(dedupe):
    """``verify`` is no longer a stub: with no ``--journal`` it validates its input
    and returns 2 with a one-line stderr message, matching the sibling
    subcommands' validation style (it does NOT emit a bare version shell)."""
    rc, stdout, stderr = _run(dedupe, "verify")
    assert rc == 2
    assert stdout == ""
    assert "journal" in stderr


# ---------------------------------------------------------------------------
# Task 1: resolve_corpus contract (the single source of truth for the
# corpus/seed file set -- plan §"--corpus contract").
# ---------------------------------------------------------------------------


def _md(path: Path, name: str) -> Path:
    f = path / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("# heading\n\nbody text\n", encoding="utf-8")
    return f


def test_resolve_corpus_flat_dir_of_md_files(dedupe, tmp_path):
    """A directory entry is walked recursively for *.md and returns the
    de-duplicated, sorted list of resolved file paths."""
    a = _md(tmp_path, "file_a.md")
    b = _md(tmp_path, "file_b.md")
    nested = _md(tmp_path, "sub/nested.md")
    (tmp_path / "ignore.txt").write_text("not markdown\n", encoding="utf-8")

    result = dedupe.resolve_corpus(str(tmp_path))

    assert result == sorted([a.resolve(), b.resolve(), nested.resolve()])


def test_resolve_corpus_comma_separated_list_of_files(dedupe, tmp_path):
    """A comma-separated list of explicit file paths resolves to exactly those
    files (mixing files is allowed), de-duplicated and sorted."""
    a = _md(tmp_path, "file_a.md")
    b = _md(tmp_path, "file_b.md")
    _md(tmp_path, "file_c.md")  # NOT listed -> must NOT appear

    arg = f"{a},{b}"
    result = dedupe.resolve_corpus(arg)

    assert result == sorted([a.resolve(), b.resolve()])


def test_resolve_corpus_mixes_dir_and_file_entries(dedupe, tmp_path):
    """Mixing dir and file entries is allowed (dirA,fileB.md)."""
    dir_a = tmp_path / "dirA"
    inner = _md(dir_a, "inner.md")
    file_b = _md(tmp_path, "file_b.md")

    arg = f"{dir_a},{file_b}"
    result = dedupe.resolve_corpus(arg)

    assert result == sorted([inner.resolve(), file_b.resolve()])


def test_resolve_corpus_skips_non_md_file_entries(dedupe, tmp_path):
    """Explicit non-*.md file entries are skipped (must end .md)."""
    a = _md(tmp_path, "file_a.md")
    txt = tmp_path / "notes.txt"
    txt.write_text("plain text\n", encoding="utf-8")

    arg = f"{a},{txt}"
    result = dedupe.resolve_corpus(arg)

    assert result == [a.resolve()]


def test_resolve_corpus_dedupes_overlapping_entries(dedupe, tmp_path):
    """A file reachable via both a dir walk and an explicit entry appears once."""
    a = _md(tmp_path, "file_a.md")

    arg = f"{tmp_path},{a}"
    result = dedupe.resolve_corpus(arg)

    assert result == [a.resolve()]


def test_resolve_corpus_default_glob_under_spellbook_dir(dedupe, tmp_path, monkeypatch):
    """DEFAULT (no --corpus) = safe-wide globs under $SPELLBOOK_DIR:
    skills/**/SKILL.md + commands/**/*.md + CLAUDE.md + skills/shared-references/*.md."""
    skill = _md(tmp_path, "skills/alpha/SKILL.md")
    command = _md(tmp_path, "commands/beta.md")
    claude = _md(tmp_path, "CLAUDE.md")
    shared = _md(tmp_path, "skills/shared-references/gamma.md")
    # Files that must NOT be swept by the default globs:
    _md(tmp_path, "skills/alpha/references/extra.md")  # not SKILL.md, not shared-references
    _md(tmp_path, "docs/unrelated.md")

    monkeypatch.setenv("SPELLBOOK_DIR", str(tmp_path))
    result = dedupe.resolve_corpus(None)

    expected = sorted(
        [skill.resolve(), command.resolve(), claude.resolve(), shared.resolve()]
    )
    assert result == expected


# ---------------------------------------------------------------------------
# Task 2: stdlib-only import check (encodes the no-new-deps + M5 constraint:
# no spellbook.*, no third-party). Parses dedupe.py's own import statements via
# ast and verifies every imported top-level module is part of the standard
# library (sys.stdlib_module_names is the source of truth, so os/types/dataclasses
# and any future stdlib addition are accepted automatically) while a
# spellbook.* or third-party import would FAIL the test.
# ---------------------------------------------------------------------------


def _imported_roots() -> tuple[set[str], bool]:
    source = HELPER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    roots: set[str] = set()
    has_relative = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            # level == 0 means absolute import; relative imports (level > 0)
            # have no module root to allowlist and are never stdlib.
            if node.module and node.level == 0:
                roots.add(node.module.split(".")[0])
            elif node.level > 0:
                has_relative = True
    return roots, has_relative


def test_dedupe_imports_stdlib_only():
    """dedupe.py must import ONLY stdlib modules: no spellbook.*, no third-party."""
    imported_roots, has_relative = _imported_roots()

    assert "argparse" in imported_roots, (
        "no imports parsed — HELPER_PATH or _imported_roots likely broken"
    )

    assert not has_relative, (
        "dedupe.py must not use relative imports (must be importlib-loadable standalone)"
    )

    forbidden = {root for root in imported_roots if root.startswith("spellbook")}
    assert not forbidden, f"dedupe.py must not import spellbook.*: {sorted(forbidden)}"

    non_stdlib = {root for root in imported_roots if root not in sys.stdlib_module_names}
    assert not non_stdlib, (
        "dedupe.py imported non-stdlib modules "
        f"(no new runtime deps allowed): {sorted(non_stdlib)}"
    )


# ---------------------------------------------------------------------------
# Task 3: inline Jaccard signal + normalization (plan §"Task 3" Step 1).
# The edge-case contract mirrors spellbook/forged/context_filtering.py
# similarity() (lines 354-394) EXACTLY:
#   - BOTH post-filter token sets empty  -> 1.0
#   - EXACTLY ONE post-filter set empty  -> 0.0
#   - else                               -> intersection / union
# _tokens intentionally OMITS the len(w) > 2 short-word filter (that filter
# lives in _extract_keywords, NOT in similarity()), so short words are RETAINED.
# ---------------------------------------------------------------------------


def test_jaccard_identical_is_one(dedupe):
    assert dedupe.jaccard("the quick brown fox", "the quick brown fox") == 1.0


def test_jaccard_disjoint_is_zero(dedupe):
    # No shared non-stop-word tokens -> intersection empty -> 0.0.
    assert dedupe.jaccard("alpha beta gamma", "delta epsilon zeta") == 0.0


def test_jaccard_both_empty_is_one(dedupe):
    assert dedupe.jaccard("", "") == 1.0


def test_jaccard_one_empty_is_zero(dedupe):
    assert dedupe.jaccard("something here", "") == 0.0
    assert dedupe.jaccard("", "something here") == 0.0


def test_jaccard_both_all_stop_words_is_one(dedupe):
    # Both reduce to empty token sets AFTER stop-word filtering -> mirrors the
    # similarity() post-filter both-empty branch -> 1.0 (not a pre-filter empty).
    assert dedupe.jaccard("the and or", "of to in") == 1.0


def test_jaccard_one_all_stop_words_is_zero(dedupe):
    # One side reduces to empty after stop-word filtering, the other does not
    # -> mirrors the similarity() post-filter exactly-one-empty branch -> 0.0.
    assert dedupe.jaccard("the and or", "alpha beta gamma") == 0.0
    assert dedupe.jaccard("alpha beta gamma", "the and or") == 0.0


def test_jaccard_partial_overlap_exact_ratio(dedupe):
    # tokens(a) = {alpha, beta, gamma, delta}; tokens(b) = {alpha, beta, gamma, omega}
    # (no stop words present). intersection = {alpha, beta, gamma} = 3;
    # union = {alpha, beta, gamma, delta, omega} = 5 -> 3/5 = 0.6.
    score = dedupe.jaccard("alpha beta gamma delta", "alpha beta gamma omega")
    assert score == 3 / 5


def test_jaccard_stop_words_filtered(dedupe):
    # "the cat" and "a cat" share only the non-stop-word token {cat}; the stop
    # words "the"/"a" are filtered out, so both reduce to {cat} -> identical -> 1.0.
    assert dedupe.jaccard("the cat", "a cat") == 1.0


def test_jaccard_short_words_retained(dedupe):
    # Short words (<=2 chars) are NOT stop words here and must be RETAINED by
    # _tokens (the len(w) > 2 filter lives in _extract_keywords, not here).
    # tokens(a) = {go, ox}; tokens(b) = {go, ax}. intersection = {go} = 1;
    # union = {go, ox, ax} = 3 -> 1/3. If short words were dropped both sets
    # would be empty and this would wrongly be 1.0.
    assert dedupe.jaccard("go ox", "go ax") == 1 / 3


def test_tokens_retains_short_words(dedupe):
    # Direct check of _tokens: a 2-char non-stop word is kept verbatim.
    assert dedupe._tokens("go ox now") == {"go", "ox", "now"}


def test_tokens_drops_stop_words(dedupe):
    # Stop words removed; remaining (including short ones) retained.
    assert dedupe._tokens("the go and ox") == {"go", "ox"}


def test_normalize_lowercases_and_collapses_ws(dedupe):
    assert dedupe.normalize("  The   QUICK  fox  ") == "the quick fox"


def test_normalize_strips_emphasis(dedupe):
    assert dedupe.normalize("**bold** and _italic_ text") == "bold and italic text"
    assert "*" not in dedupe.normalize("**bold** and _italic_ text")
    assert "_" not in dedupe.normalize("**bold** and _italic_ text")


def test_normalize_strips_backticks(dedupe):
    assert dedupe.normalize("run `git push` now") == "run git push now"


# ---------------------------------------------------------------------------
# Task 4: SequenceMatcher confirm signal + drift delta + pair scoring
# (plan §"Task 4" Step 1, §3.5 Signal 2).
#   seqmatch_ratio(a, b) = difflib.SequenceMatcher(None, normalize(a),
#                                                   normalize(b)).ratio()
#   drift_delta(a, b)    = 1.0 - seqmatch_ratio(a, b)
#   score_pair gates on jaccard (returns None below the floor), then computes
#   the SequenceMatcher confirm signal and drift delta. Contracts asserted:
#     - is_drift_candidate = (j >= jaccard_threshold) and (seqmatch_ratio < 1.0)
#     - NO boilerplate check in score_pair (boilerplate is excluded once, at
#       segmentation time -- Task 5; the SOLE boilerplate guard).
#     - contains_safety_marker reflects REAL detection (wired in Task 7): a pair
#       is True iff either block's raw_text matches a _SAFETY_MARKERS token.
# ---------------------------------------------------------------------------


def _block(dedupe, raw_text: str, *, file: str = "x.md", granularity: str = "paragraph",
           start_line: int = 1, end_line: int = 1, parent_key=None, block_id=None):
    """Construct a Block directly (segment() arrives in Task 5).

    normalized_text is populated via the real normalize() so score_pair's
    jaccard/seqmatch operate on the same normalized form the pipeline uses.
    """
    return dedupe.Block(
        file=file,
        granularity=granularity,
        start_line=start_line,
        end_line=end_line,
        raw_text=raw_text,
        normalized_text=dedupe.normalize(raw_text),
        parent_key=parent_key,
        block_id=block_id if block_id is not None else f"id-{start_line}-{end_line}",
    )


def test_seqmatch_identical_is_one(dedupe):
    assert dedupe.seqmatch_ratio("identical text here", "identical text here") == 1.0


def test_seqmatch_normalizes_before_compare(dedupe):
    # Differs only by case + emphasis + whitespace, all removed by normalize() ->
    # the normalized forms are byte-identical -> ratio is exactly 1.0. A
    # raw (non-normalizing) SequenceMatcher would score < 1.0 here.
    assert dedupe.seqmatch_ratio("**Hello**   World", "hello world") == 1.0


def test_seqmatch_disjoint_is_zero(dedupe):
    # No characters in common at all -> ratio 0.0.
    assert dedupe.seqmatch_ratio("aaaa", "bbbb") == 0.0


def test_seqmatch_both_empty_is_one(dedupe):
    # Both inputs normalize to "" -> SequenceMatcher ratio is 1.0, converging
    # with jaccard's both-empty -> 1.0 convention (the two signals agree on the
    # empty-input edge case).
    assert dedupe.seqmatch_ratio("   ", "") == 1.0


def test_drift_delta_zero_for_identical(dedupe):
    a = "the rule is do not push to main"
    assert dedupe.drift_delta(a, a) == 0.0


def test_drift_delta_is_one_minus_seqmatch(dedupe):
    # drift_delta is defined EXACTLY as 1.0 - seqmatch_ratio; assert the identity
    # holds for an arbitrary non-trivial pair (catches a sign flip / wrong base).
    a = "the rule is do not push to main"
    b = "the rule is do not push to master"
    assert dedupe.drift_delta(a, b) == 1.0 - dedupe.seqmatch_ratio(a, b)


def test_drift_delta_positive_for_one_word_change(dedupe):
    a = "the rule is do not push to main"
    b = "the rule is do not push to master"
    delta = dedupe.drift_delta(a, b)
    assert 0.0 < delta < 0.3


def test_score_pair_identical_not_drift_candidate(dedupe):
    text = "always confirm with the operator before running any destructive command here"
    a = _block(dedupe, text, file="a.md", start_line=1, end_line=1)
    b = _block(dedupe, text, file="b.md", start_line=1, end_line=1)
    pair = dedupe.score_pair(a, b, jaccard_threshold=0.7, confirm_threshold=0.85)
    assert pair is not None
    assert pair.a is a
    assert pair.b is b
    assert pair.jaccard == 1.0
    assert pair.seqmatch_ratio == 1.0
    assert pair.drift_delta == 0.0
    # Identical text: seqmatch_ratio == 1.0 -> NOT a drift candidate.
    assert pair.is_drift_candidate is False
    # Task 7 wired real detection: this block's text contains the imperative
    # safety marker "always" ("ALWAYS" in _SAFETY_MARKERS), so the pair carries
    # contains_safety_marker == True. (Was an always-False Task 4 placeholder.)
    assert pair.contains_safety_marker is True


def test_score_pair_high_jaccard_not_identical_is_drift_candidate(dedupe):
    # One word changed: token Jaccard stays >= 0.7 (gate passes) but the
    # SequenceMatcher ratio is < 1.0 -> is_drift_candidate is True.
    a = _block(dedupe, "the rule is do not ever push to the protected main branch",
               file="a.md")
    b = _block(dedupe, "the rule is do not ever push to the protected master branch",
               file="b.md")
    pair = dedupe.score_pair(a, b, jaccard_threshold=0.7, confirm_threshold=0.85)
    assert pair is not None
    assert pair.jaccard >= 0.7
    assert pair.seqmatch_ratio < 1.0
    assert pair.drift_delta == 1.0 - pair.seqmatch_ratio
    assert pair.is_drift_candidate is True
    # Task 7 wired real detection: neither block carries a safety marker
    # ("do not"/"push" are not in _SAFETY_MARKERS), so this ordinary drift pair
    # stays contains_safety_marker == False. (Was an always-False Task 4 placeholder.)
    assert pair.contains_safety_marker is False


def test_score_pair_low_jaccard_returns_none(dedupe):
    # Disjoint vocabulary -> jaccard 0.0 < 0.7 gate -> score_pair returns None
    # (the cheap Jaccard gate precedes the SequenceMatcher confirm, §3.5).
    a = _block(dedupe, "alpha beta gamma delta epsilon zeta eta theta iota kappa",
               file="a.md")
    b = _block(dedupe, "lambda mu nu xi omicron pi rho sigma tau upsilon phi chi",
               file="b.md")
    pair = dedupe.score_pair(a, b, jaccard_threshold=0.7, confirm_threshold=0.85)
    assert pair is None


def test_score_pair_at_jaccard_floor_is_drift_candidate(dedupe):
    # is_drift_candidate uses `j >= jaccard_threshold` (inclusive at the floor).
    # Construct a pair whose token Jaccard is exactly 0.5, gate at 0.5: the pair
    # passes the gate (returned, not None) and -- being non-identical -- is a
    # drift candidate. With a gate of 0.7 the SAME pair would be dropped (None),
    # proving the gate is inclusive at its own threshold.
    a = _block(dedupe, "alpha beta gamma delta", file="a.md")  # tokens {alpha,beta,gamma,delta}
    b = _block(dedupe, "alpha beta omega psi", file="b.md")    # tokens {alpha,beta,omega,psi}
    # intersection {alpha,beta}=2, union 6 -> jaccard 1/3 ... recompute below.
    j = dedupe.jaccard(a.normalized_text, b.normalized_text)
    assert j == 1 / 3  # {alpha,beta} / {alpha,beta,gamma,delta,omega,psi}
    # Gate at exactly j: inclusive -> returned and is a drift candidate.
    at_floor = dedupe.score_pair(a, b, jaccard_threshold=j, confirm_threshold=0.85)
    assert at_floor is not None
    assert at_floor.is_drift_candidate is True
    # Gate just above j: dropped.
    above = dedupe.score_pair(a, b, jaccard_threshold=j + 0.01, confirm_threshold=0.85)
    assert above is None


def test_score_pair_no_boilerplate_check(dedupe):
    # score_pair must NOT contain a boilerplate guard. A boilerplate-shaped block
    # (a bare horizontal rule "---" repeated) still tokenizes to a non-empty
    # identical set here; if score_pair silently dropped boilerplate it would
    # return None. The SOLE boilerplate guard is segmentation (Task 5), so
    # score_pair returns a normal Pair for these inputs.
    a = _block(dedupe, "step one then step two then step three then step four done",
               file="a.md")
    b = _block(dedupe, "step one then step two then step three then step four done",
               file="b.md")
    pair = dedupe.score_pair(a, b, jaccard_threshold=0.7, confirm_threshold=0.85)
    assert pair is not None
    assert pair.seqmatch_ratio == 1.0
    assert pair.is_drift_candidate is False


# ---------------------------------------------------------------------------
# Task 5: multi-granularity markdown segmentation + noise control
# (plan §"Task 5" Step 2, design §3.3, §3.4, §3.7).
#
# segment() splits a markdown file's BODY (frontmatter excluded) into Blocks at
# four granularities -- "heading-section", "paragraph", "list-item",
# "fenced-whole" -- with absolute 1-based start_line/end_line, normalized_text,
# parent_key linkage to the enclosing heading-section, and a stable block_id.
#
# CRITICAL boilerplate contract (design §3.4): structural boilerplate (bare
# headings with no body, horizontal rules, frontmatter-key lines, <ROLE> stubs)
# is excluded AT SEGMENTATION TIME. This is the SOLE boilerplate guard in the
# whole pipeline -- score_pair (Task 4) does NOT re-check. Below-floor blocks
# (normalized_text shorter than min_block_chars) are excluded too, EXCEPT
# fenced-whole, which is kept regardless of size.
#
# Fixture line map (tests/test_skills/fixtures/dedupe/seg_sample.md), 1-based:
#    1: ---                  (frontmatter open)
#    2: name: seg-sample
#    3: description: "..."
#    4: ---                  (frontmatter close)
#    5: (blank)
#    6: # Top Heading
#    7: (blank)
#    8: prose paragraph (>80 normalized chars)
#    9: (blank)
#   10: ## Sub
#   11: (blank)
#   12: - item one ... (>80 normalized chars)
#   13: (blank)
#   14: ```bash              (fence open)
#   15: git status
#   16: git status
#   17: ```                  (fence close)
#   18: (blank)
#   19: ---                  (horizontal rule, boilerplate)
#   20: (blank)
#   21: ## X                 (bare heading, boilerplate)
# ---------------------------------------------------------------------------


def _seg_sample_text() -> str:
    return (FIXTURE_DIR / "seg_sample.md").read_text(encoding="utf-8")


def test_segment_excludes_frontmatter(dedupe):
    blocks = dedupe.segment("seg_sample.md", _seg_sample_text())
    assert all("description:" not in b.raw_text for b in blocks)
    assert all("name: seg-sample" not in b.raw_text for b in blocks)


def test_segment_four_granularities_present(dedupe):
    grans = {b.granularity for b in dedupe.segment("seg_sample.md", _seg_sample_text())}
    assert {"heading-section", "paragraph", "list-item", "fenced-whole"} <= grans


def test_segment_fence_matched_whole(dedupe):
    fences = [
        b
        for b in dedupe.segment("seg_sample.md", _seg_sample_text())
        if b.granularity == "fenced-whole"
    ]
    assert len(fences) == 1
    fence = fences[0]
    # The two ``` markers are both inside the single fenced-whole block: the
    # fence is matched whole and NEVER sub-segmented into the duplicate
    # "git status" one-liners it contains.
    assert fence.raw_text.count("```") == 2
    assert fence.start_line == 14
    assert fence.end_line == 17
    # The fence body is NEVER sub-segmented into paragraph/list-item one-liners.
    # (A heading-section legitimately CONTAINS its fence in its span -- that is by
    # design; only paragraph/list-item granularities must not carve up the fence.)
    sub_blocks = [
        b
        for b in dedupe.segment("seg_sample.md", _seg_sample_text())
        if b.granularity in ("paragraph", "list-item")
    ]
    assert all("git status" not in b.raw_text for b in sub_blocks)


def test_segment_min_block_floor(dedupe):
    blocks = dedupe.segment("seg_sample.md", _seg_sample_text(), min_block_chars=80)
    # Every emitted block clears the 80-char floor EXCEPT fenced-whole, which is
    # kept regardless of size (design §3.4).
    assert all(
        len(b.normalized_text) >= 80 or b.granularity == "fenced-whole"
        for b in blocks
    )
    # The short fence body (two `git status` lines, well under 80 chars) survives
    # precisely because of the fenced-whole exception.
    assert any(b.granularity == "fenced-whole" for b in blocks)


def test_segment_denies_boilerplate(dedupe):
    blocks = dedupe.segment("seg_sample.md", _seg_sample_text())
    # The horizontal rule (line 19) and the bare one-word heading "## X"
    # (line 21) are structural boilerplate and must NOT appear as blocks.
    assert all(b.raw_text.strip() not in ("---", "## X", "X") for b in blocks)
    assert not any(b.start_line == 19 for b in blocks)  # horizontal rule line
    assert not any(b.start_line == 21 for b in blocks)  # bare heading "## X"


def test_segment_block_ids_unique(dedupe):
    blocks = dedupe.segment("seg_sample.md", _seg_sample_text())
    ids = [b.block_id for b in blocks]
    assert len(ids) == len(set(ids)), "block_id must be unique per block"


def test_segment_block_id_stable(dedupe):
    a = dedupe.segment("seg_sample.md", _seg_sample_text())
    b = dedupe.segment("seg_sample.md", _seg_sample_text())
    assert [x.block_id for x in a] == [y.block_id for y in b]


def test_segment_paragraph_block_lines_and_parent(dedupe):
    blocks = dedupe.segment("seg_sample.md", _seg_sample_text())
    paras = [b for b in blocks if b.granularity == "paragraph"]
    assert len(paras) == 1
    para = paras[0]
    # The prose paragraph occupies exactly line 8 (1-based, absolute).
    assert para.start_line == 8
    assert para.end_line == 8
    # Its enclosing heading-section is "# Top Heading" (line 6).
    headings = {b.start_line: b.block_id for b in blocks
                if b.granularity == "heading-section"}
    assert para.parent_key == headings[6]


def test_segment_list_item_block_lines_and_parent(dedupe):
    blocks = dedupe.segment("seg_sample.md", _seg_sample_text())
    items = [b for b in blocks if b.granularity == "list-item"]
    assert len(items) == 1
    item = items[0]
    # The list item occupies exactly line 12 (1-based, absolute).
    assert item.start_line == 12
    assert item.end_line == 12
    # Its enclosing heading-section is "## Sub" (line 10).
    headings = {b.start_line: b.block_id for b in blocks
                if b.granularity == "heading-section"}
    assert item.parent_key == headings[10]


def test_segment_heading_section_block(dedupe):
    blocks = dedupe.segment("seg_sample.md", _seg_sample_text())
    headings = {b.start_line: b for b in blocks if b.granularity == "heading-section"}
    # "# Top Heading" (line 6) and "## Sub" (line 10) each have body content that
    # clears the floor, so both survive as heading-section blocks. The bare
    # "## X" (line 21) is boilerplate and excluded.
    assert set(headings) == {6, 10}
    # The top heading-section is its own parent root (parent_key None).
    assert headings[6].parent_key is None


def test_segment_normalized_text_populated(dedupe):
    blocks = dedupe.segment("seg_sample.md", _seg_sample_text())
    para = next(b for b in blocks if b.granularity == "paragraph")
    assert para.normalized_text == dedupe.normalize(para.raw_text)
    assert para.normalized_text == para.normalized_text.strip().lower()


def test_segment_boilerplate_is_sole_guard_predicate(dedupe):
    # The denylist predicate is exposed for the SOLE-guard contract: a bare ATX
    # heading and a horizontal rule are boilerplate; ordinary prose is not.
    assert dedupe._is_structural_boilerplate("## X")
    assert dedupe._is_structural_boilerplate("---")
    assert dedupe._is_structural_boilerplate("***")
    assert dedupe._is_structural_boilerplate("___")
    assert not dedupe._is_structural_boilerplate(
        "This is a real prose paragraph with several content words in it."
    )


def test_is_structural_boilerplate_keeps_key_prefixed_instruction_lines(dedupe):
    # REGRESSION (review defect): frontmatter-shaped "key: value" / "Prefix:"
    # lines are NOT boilerplate. split_file already strips the YAML frontmatter
    # before segmentation, so the body should not carry genuine frontmatter
    # keys; treating these lines as boilerplate silently dropped exactly the
    # high-value instruction prose this tool exists to preserve.
    assert not dedupe._is_structural_boilerplate(
        "Important: never push to a protected branch without explicit permission first."
    )
    assert not dedupe._is_structural_boilerplate("INLINE-MANDATORY: do X")
    assert not dedupe._is_structural_boilerplate("Note: this matters")
    assert not dedupe._is_structural_boilerplate("Rule: one test at a time")
    assert not dedupe._is_structural_boilerplate("WARNING: destructive operation")
    assert not dedupe._is_structural_boilerplate("Step: run the migration")
    assert not dedupe._is_structural_boilerplate("TODO: wire this up")
    assert not dedupe._is_structural_boilerplate("name: seg-sample")
    # Genuine structural boilerplate is still excluded (no coverage weakened).
    assert dedupe._is_structural_boilerplate("---")
    assert dedupe._is_structural_boilerplate("## X")


def test_segment_keeps_single_line_instruction_paragraph(dedupe):
    # A single-line paragraph whose only line is an "Important:"-prefixed
    # instruction (> min_block_chars) must SURVIVE segmentation -- previously it
    # was dropped wholesale because its sole line matched the key regex.
    text = (
        "# Heading\n\n"
        "INLINE-MANDATORY: never push to a protected branch without explicit "
        "operator permission, even in autonomous mode here.\n"
    )
    blocks = dedupe.segment("inline.md", text)
    survivor = [
        b for b in blocks
        if b.granularity == "paragraph" and "INLINE-MANDATORY" in b.raw_text
    ]
    assert len(survivor) == 1


def test_segment_keeps_heading_section_with_single_key_value_body(dedupe):
    # A heading-section whose body is a single long "key: value" line must
    # SURVIVE -- previously heading boilerplate + key-line boilerplate meant
    # EVERY line was boilerplate and the whole section was dropped.
    text = (
        "## Config\n\n"
        "Important: this single key value line is well past the eighty character "
        "normalized floor so it survives on its own merits.\n"
    )
    blocks = dedupe.segment("kv.md", text)
    assert any(
        "Important:" in b.raw_text and b.granularity in ("heading-section", "paragraph")
        for b in blocks
    )


def test_segment_still_excludes_genuine_boilerplate(dedupe):
    # Confirm the fix did not weaken genuine boilerplate coverage: a horizontal
    # rule and a bare "## X" heading are still excluded from emitted blocks.
    text = (
        "Real prose paragraph with plenty of content words to clear the eighty "
        "character normalized floor comfortably here.\n\n"
        "---\n\n"
        "## X\n"
    )
    blocks = dedupe.segment("bp.md", text)
    assert all(b.raw_text.strip() not in ("---", "## X", "X") for b in blocks)


# ---------------------------------------------------------------------------
# Task 6: pairing pipeline + union-find clustering + fixture corpus
# (plan §"Task 6"; design §3.4, §3.5, §3.6)
# ---------------------------------------------------------------------------


def _load_fixture_blocks(dedupe, names: list[str]):
    """Segment each named core fixture file and concatenate the block lists.

    The Task 6 core corpus (``file_a.md``/``file_b.md``/``file_c.md``) is a flat
    set of fixture files at ``FIXTURE_DIR``; this mirrors how the integrated
    ``detect`` path will feed segmented blocks into ``pair_corpus``.
    """
    blocks = []
    for name in names:
        text = (FIXTURE_DIR / name).read_text(encoding="utf-8")
        blocks.extend(dedupe.segment(name, text))
    return blocks


def test_pairs_only_across_different_files(dedupe):
    """Pairing is BETWEEN files only: no Pair may have both endpoints in the same
    file (design §3.5 -- within-file dedup is out of scope, FU-1)."""
    blocks = _load_fixture_blocks(dedupe, ["file_a.md", "file_b.md", "file_c.md"])
    pairs = dedupe.pair_corpus(
        blocks, jaccard_threshold=0.7, confirm_threshold=0.85
    )
    assert pairs, "the fixture corpus must produce at least one cross-file pair"
    assert all(p.a.file != p.b.file for p in pairs), \
        "no pair may have both endpoints in the same file"


def test_pairs_flag_known_duplicate(dedupe):
    """A byte-identical (post-normalization) paragraph across two files is flagged
    with seqmatch_ratio == 1.0 and is NOT a drift candidate (design §9.2)."""
    blocks = _load_fixture_blocks(dedupe, ["file_a.md", "file_b.md"])
    pairs = dedupe.pair_corpus(
        blocks, jaccard_threshold=0.7, confirm_threshold=0.85
    )
    known = [
        p for p in pairs
        if "onboarding checklist" in p.a.raw_text
        and "onboarding checklist" in p.b.raw_text
    ]
    assert len(known) == 1, "the known duplicate must produce exactly one survivor pair"
    assert known[0].seqmatch_ratio == 1.0
    assert known[0].is_drift_candidate is False


def test_pairs_flag_drift(dedupe):
    """The one-word-drift paragraph across file_b/file_c is a drift candidate with
    0.0 < drift_delta < 1.0 (design §9.2, §6)."""
    blocks = _load_fixture_blocks(dedupe, ["file_b.md", "file_c.md"])
    pairs = dedupe.pair_corpus(
        blocks, jaccard_threshold=0.7, confirm_threshold=0.85
    )
    drift = [
        p for p in pairs
        if "incident commander" in p.a.raw_text
        and "incident commander" in p.b.raw_text
    ]
    assert len(drift) == 1, "the one-word-drift paragraph must produce one survivor pair"
    assert drift[0].is_drift_candidate is True
    assert drift[0].seqmatch_ratio < 1.0
    assert 0.0 < drift[0].drift_delta < 1.0


def test_paraphrase_not_flagged(dedupe):
    """M3: the paraphrase blocks share meaning but few tokens; no pair links them.
    Regression-locks the known lexical false-negative (design §9.2)."""
    blocks = _load_fixture_blocks(dedupe, ["file_a.md", "file_b.md"])
    pairs = dedupe.pair_corpus(
        blocks, jaccard_threshold=0.7, confirm_threshold=0.85
    )
    assert not any(
        ("PARAPHRASE_A" in p.a.raw_text and "PARAPHRASE_B" in p.b.raw_text)
        or ("PARAPHRASE_B" in p.a.raw_text and "PARAPHRASE_A" in p.b.raw_text)
        for p in pairs
    )


def test_injection_block_segments_as_ordinary_data(dedupe):
    """Design §9.2/§4.5: an embedded directive is segmented as an ordinary DATA
    Block with no special handling. The script never interprets block content."""
    blocks = _load_fixture_blocks(dedupe, ["file_a.md"])
    inj = [b for b in blocks if "INJECTION_BLOCK" in b.raw_text]
    assert len(inj) == 1, "the injection paragraph must segment as exactly one ordinary block"
    assert inj[0].granularity == "paragraph"
    assert "IGNORE PRIOR INSTRUCTIONS" in inj[0].raw_text


def test_union_find_clusters_three_occurrences(dedupe):
    """The genuine 3-occurrence TRIPLE_BLOCK (present in file_a/b/c) produces
    confirmed A-B, B-C, A-C pairs that collapse to ONE cluster of >= 3 block_ids
    (design §3.5, Minor finding 8). No escape branch: union-find must merge them.
    """
    blocks = _load_fixture_blocks(dedupe, ["file_a.md", "file_b.md", "file_c.md"])
    pairs = dedupe.pair_corpus(
        blocks, jaccard_threshold=0.7, confirm_threshold=0.85
    )
    confirmed = [
        p for p in pairs
        if p.seqmatch_ratio >= 0.85 and not p.is_drift_candidate
    ]
    clusters = dedupe.cluster_pairs(confirmed)
    # The TRIPLE_BLOCK is a bare top-level paragraph in each of the three files,
    # so it segments to exactly one paragraph block per file; pairing connects
    # those three block_ids into a single union-find component.
    triple_ids = {
        b.block_id
        for b in blocks
        if "TRIPLE_BLOCK" in b.raw_text and b.granularity == "paragraph"
    }
    assert len(triple_ids) == 3, "fixture must seed TRIPLE_BLOCK in all three files"
    merged = [c for c in clusters if triple_ids & c]
    assert len(merged) == 1, "the three occurrences must all land in one cluster"
    assert triple_ids <= merged[0], \
        "the single cluster must contain all three TRIPLE_BLOCK block_ids"
    assert len(merged[0]) >= 3, \
        "union-find must collapse the 3 TRIPLE_BLOCK occurrences into one cluster of >= 3"


def test_pair_corpus_respects_cost_bound(dedupe):
    """The cost bound caps the returned pairs to the top-N by seqmatch_ratio
    (design §3.6): with max_pairs set below the survivor count, exactly max_pairs
    pairs are returned and they are the strongest matches."""
    blocks = _load_fixture_blocks(dedupe, ["file_a.md", "file_b.md", "file_c.md"])
    full = dedupe.pair_corpus(
        blocks, jaccard_threshold=0.7, confirm_threshold=0.85
    )
    assert len(full) >= 2, "the corpus must produce multiple pairs for this bound to bite"
    top_ratio = max(p.seqmatch_ratio for p in full)
    # The fixture has multiple ratio-1.0 pairs, so asserting only the top ratio
    # would not pin WHICH pair survives a tie. Compute the deterministic survivor
    # by applying the same stable sort the implementation uses (seqmatch_ratio
    # desc over the uncapped corpus order) and taking element 0.
    assert (
        sum(1 for p in full if p.seqmatch_ratio == top_ratio) >= 2
    ), "fixture must contain a tie at the top ratio to exercise the tiebreak"
    expected = sorted(full, key=lambda p: p.seqmatch_ratio, reverse=True)[0]
    capped = dedupe.pair_corpus(
        blocks, jaccard_threshold=0.7, confirm_threshold=0.85, max_pairs=1
    )
    assert len(capped) == 1
    assert capped[0].seqmatch_ratio == top_ratio
    # Lock the tiebreak: the surviving pair's identity must be the stable-sort
    # winner. A future switch to a non-stable sort would break this.
    assert (
        capped[0].a.block_id == expected.a.block_id
        and capped[0].b.block_id == expected.b.block_id
    ), "the capped survivor must be the deterministic stable-sort winner"
    # A bound at or above the survivor count is a no-op (returns every survivor).
    uncapped = dedupe.pair_corpus(
        blocks, jaccard_threshold=0.7, confirm_threshold=0.85, max_pairs=len(full) + 5
    )
    assert len(uncapped) == len(full)


def test_cluster_pairs_excludes_drift_edges(dedupe):
    """Drift pairs never contribute union-find edges (design §3.5): the drifted
    file_b/file_c paragraph must NOT merge into any cluster of size >= 2."""
    blocks = _load_fixture_blocks(dedupe, ["file_b.md", "file_c.md"])
    pairs = dedupe.pair_corpus(
        blocks, jaccard_threshold=0.7, confirm_threshold=0.85
    )
    drift = next(
        p for p in pairs
        if "incident commander" in p.a.raw_text and p.is_drift_candidate
    )
    confirmed = [p for p in pairs if p.seqmatch_ratio >= 0.85 and not p.is_drift_candidate]
    clusters = dedupe.cluster_pairs(confirmed)
    drift_ids = {drift.a.block_id, drift.b.block_id}
    assert not any(len(c & drift_ids) >= 2 for c in clusters), \
        "a drift pair's endpoints must not be unioned into the same cluster"


def test_child_in_parent_suppression_drops_contained_pair(dedupe):
    """child_in_parent_suppression keeps the widest match and drops a child pair
    fully contained within a matched parent pair on BOTH sides (design §3.4).
    Deferred TEST from Task 5; the function was added there.
    """
    def block(file: str, granularity: str, start: int, end: int, text: str):
        return dedupe._make_block(file, granularity, start, end, text, None)

    parent_text = (
        "## Guard\n\nThe widest coherent match spans the whole heading section "
        "including its nested child paragraph below it here.\n\nThe contained "
        "child paragraph is itself a confirmed duplicate inside the section.\n"
    )
    child_text = (
        "The contained child paragraph is itself a confirmed duplicate inside "
        "the section."
    )
    parent_a = block("file_a.md", "heading-section", 1, 6, parent_text)
    child_a = block("file_a.md", "paragraph", 5, 6, child_text)
    parent_b = block("file_b.md", "heading-section", 1, 6, parent_text)
    child_b = block("file_b.md", "paragraph", 5, 6, child_text)

    def pair(a, b):
        return dedupe.Pair(
            a=a, b=b,
            jaccard=1.0, seqmatch_ratio=1.0, drift_delta=0.0,
            is_drift_candidate=False, contains_safety_marker=False,
        )

    parent_pair = pair(parent_a, parent_b)
    child_pair = pair(child_a, child_b)
    survivors = dedupe.child_in_parent_suppression([parent_pair, child_pair])
    assert survivors == [parent_pair], \
        "the child pair contained in the parent pair on both sides must be dropped"


def test_child_in_parent_suppression_keeps_non_contained(dedupe):
    """A pair NOT contained within another pair survives suppression unchanged."""
    def block(file: str, start: int, end: int, text: str):
        return dedupe._make_block(file, "paragraph", start, end, text, None)

    text_one = "First standalone duplicated paragraph with enough words to be a block."
    text_two = "Second unrelated duplicated paragraph living elsewhere in the file."
    a1 = block("file_a.md", 1, 2, text_one)
    b1 = block("file_b.md", 1, 2, text_one)
    a2 = block("file_a.md", 20, 21, text_two)
    b2 = block("file_b.md", 20, 21, text_two)

    def pair(a, b):
        return dedupe.Pair(
            a=a, b=b,
            jaccard=1.0, seqmatch_ratio=1.0, drift_delta=0.0,
            is_drift_candidate=False, contains_safety_marker=False,
        )

    p1 = pair(a1, b1)
    p2 = pair(a2, b2)
    survivors = dedupe.child_in_parent_suppression([p1, p2])
    assert survivors == [p1, p2], "non-overlapping pairs are both retained"


# ---------------------------------------------------------------------------
# Task 7: INLINE-MANDATORY predicate + safety-marker + dangerous-action denylist
# (plan §"Task 7" Step 1, design §4.4 -- C6).
#   contains_safety_marker(text)         -> True iff any _SAFETY_MARKERS token
#                                           matches (case-insensitive).
#   danger_lines(file, text)             -> {1-based-line: line_text} for every
#                                           line matching _DANGER_DENYLIST.
#   is_inline_mandatory(block, all_lines)-> True if the block carries a safety
#                                           marker OR positionally encloses a
#                                           dangerous action (Clause 3).
#   score_pair wires contains_safety_marker = marker(a.raw_text) or
#                                             marker(b.raw_text) (real, not the
#                                             Task 4 always-False placeholder).
# _DANGER_DENYLIST is a MODULE CONSTANT in the MVP; the --danger-denylist CLI
# flag is DEFERRED (post-review fix MINOR 9).
# ---------------------------------------------------------------------------


def test_safety_marker_detected(dedupe):
    # Exact True/False per marker class: CRITICAL token, imperative "MUST",
    # <RULE> tag -> True; calm prose with no marker -> False.
    assert dedupe.contains_safety_marker("This is CRITICAL: never push to main") is True
    assert dedupe.contains_safety_marker("You MUST validate input") is True
    assert dedupe.contains_safety_marker("<RULE>do not delete</RULE>") is True
    assert dedupe.contains_safety_marker(
        "a calm descriptive paragraph about colors"
    ) is False


def test_safety_marker_full_token_set(dedupe):
    # Construct the complete expected boolean map over a representative input per
    # marker class plus negatives; assert the whole dict at once (Full Assertion).
    cases = {
        "this rule is CRITICAL to obey": True,
        "this action is FORBIDDEN": True,
        "<CRITICAL>guard</CRITICAL>": True,
        "you must NEVER force push": True,
        "ALWAYS check the operator first": True,
        "this MUST NOT be skipped": True,
        "Inviolable Rules apply here": True,
        "see the Git Safety section": True,
        "you MUST validate the payload": True,
        # negatives: ordinary descriptive prose with no marker token.
        "the sky is a pleasant shade of blue today": False,
        "engineers record the rationale for each tradeoff": False,
    }
    result = {text: dedupe.contains_safety_marker(text) for text in cases}
    assert result == cases


def test_danger_lines_exact_map(dedupe):
    # danger_lines returns {1-based whole-file line: line_text} for EVERY line
    # matching _DANGER_DENYLIST. Construct the complete expected dict.
    text = (
        "## Steps\n"           # line 1 - no danger token
        "\n"                   # line 2
        "First confirm with the operator.\n"   # line 3 - no token
        "Then run git push to publish.\n"      # line 4 - "git push"
        "Optionally rm -rf the scratch dir.\n" # line 5 - "rm -rf" / "rm"
        "A calm sentence with no danger.\n"    # line 6 - none
    )
    expected = {
        4: "Then run git push to publish.",
        5: "Optionally rm -rf the scratch dir.",
    }
    assert dedupe.danger_lines("x.md", text) == expected


def test_danger_lines_whole_token_not_substring(dedupe):
    # "force" must match as a whole word, NOT inside "reinforcements" / "enforce".
    # "rm" must not match inside "harm" / "form". The denylist is whole-token.
    text = (
        "Send reinforcements to enforce the policy.\n"  # line 1 - no whole token
        "This will not harm the form at all.\n"          # line 2 - no whole token
        "Use --force only when instructed.\n"            # line 3 - "--force" / "force"
    )
    expected = {3: "Use --force only when instructed."}
    assert dedupe.danger_lines("x.md", text) == expected


def test_inline_mandatory_on_safety_block(dedupe):
    # A segmented block whose body carries safety markers (MUST/NEVER/CRITICAL)
    # is INLINE-MANDATORY by Clause 1, independent of any danger line. The body
    # is long enough to clear the default min-block-chars floor so segment()
    # yields the heading-section block.
    block = dedupe.segment(
        "x.md",
        "## Guard\n\nYou MUST NEVER force push to the protected main branch under "
        "any circumstance, this is CRITICAL and non-negotiable for every "
        "contributor.\n",
    )[0]
    assert dedupe.is_inline_mandatory(block, all_lines={}) is True


def test_inline_mandatory_ordinary_block_is_false(dedupe):
    # An ordinary descriptive block with neither a safety marker nor an enclosed
    # danger line is NOT inline-mandatory.
    block = dedupe.segment(
        "x.md",
        "## Notes\n\nThis paragraph calmly describes the release calendar cadence "
        "and the soak window for candidate builds before promotion to production.\n",
    )[0]
    assert dedupe.is_inline_mandatory(block, all_lines={}) is False


def test_inline_mandatory_clause3_positional(dedupe):
    """Block enclosing a dangerous-action line in the same heading-section is in-flow."""
    text = (
        "## Apply\n\n"
        "Always confirm with the operator before proceeding with the operation.\n\n"
        "Then run git push to publish.\n"
    )
    blocks = dedupe.segment("x.md", text)
    guard = next(b for b in blocks if "confirm with the operator" in b.raw_text)
    assert dedupe.is_inline_mandatory(
        guard, all_lines=dedupe.danger_lines("x.md", text)
    ) is True


def test_inline_mandatory_clause3_no_danger_line_is_false(dedupe):
    # The same guard block, but with NO danger lines in scope, is NOT in-flow by
    # Clause 3 (it has no safety marker either: "always" IS a marker, so use a
    # marker-free guard to isolate Clause 3). End-to-end: an enclosing section
    # with no danger action and no marker is not inline-mandatory.
    text = (
        "## Review\n\n"
        "First confirm with the operator before proceeding with the operation.\n\n"
        "Then read the published summary document.\n"
    )
    blocks = dedupe.segment("x.md", text)
    guard = next(b for b in blocks if "confirm with the operator" in b.raw_text)
    assert dedupe.danger_lines("x.md", text) == {}
    assert dedupe.is_inline_mandatory(
        guard, all_lines=dedupe.danger_lines("x.md", text)
    ) is False


def test_pair_carries_safety_marker(dedupe):
    blocks = _load_fixture_blocks(dedupe, ["file_a.md", "file_c.md"])
    pairs = dedupe.pair_corpus(blocks, jaccard_threshold=0.7, confirm_threshold=0.85)
    # The load-bearing CRITICAL/NEVER repeat (file_a/file_c "Load Bearing Safety
    # Section") must set contains_safety_marker on its surviving pair(s); the
    # ordinary TRIPLE_BLOCK release-cadence pair must NOT.
    safety = [p for p in pairs if "credential vault" in p.a.raw_text]
    ordinary = [p for p in pairs if "TRIPLE_BLOCK" in p.a.raw_text]
    assert safety, "the load-bearing CRITICAL repeat must produce a surviving pair"
    assert ordinary, "the TRIPLE_BLOCK release-cadence repeat must produce a pair"
    assert all(p.contains_safety_marker is True for p in safety), \
        "every safety pair must set contains_safety_marker True"
    assert all(p.contains_safety_marker is False for p in ordinary), \
        "the ordinary (non-safety) pair must leave contains_safety_marker False"


# ---------------------------------------------------------------------------
# Safety regression locks (review findings C1, I1, I2, Clause 3 boundary).
#
# C1: a multi-word marker / danger token must match across ANY internal
# whitespace -- a double space, a tab, OR a line-wrapped newline -- not only the
# single literal space in the source token. A naive ``re.escape(token)`` matches
# only one ASCII space, silently escaping detection of ``git  push`` /
# ``git\tpush`` / a wrapped ``you\nMUST`` -- a SAFETY false-negative. The
# _token_pattern fix widens internal whitespace to ``\s+``.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sep",
    ["  ", "\t", "\n", " \t "],
    ids=["double-space", "tab", "newline", "mixed"],
)
def test_multiword_safety_marker_matches_any_whitespace(dedupe, sep):
    # "you MUST" and "MUST NOT" are multi-word _SAFETY_MARKERS. A run of any
    # whitespace between the words (incl. a wrapped newline) MUST still detect.
    assert dedupe.contains_safety_marker(f"you{sep}MUST validate input") is True
    assert dedupe.contains_safety_marker(f"this MUST{sep}NOT be skipped") is True


@pytest.mark.parametrize(
    "sep",
    ["  ", "\t", " \t "],
    ids=["double-space", "tab", "mixed"],
)
def test_multiword_danger_token_matches_any_whitespace(dedupe, sep):
    # "git push" and "rm -rf" are multi-word _DANGER_DENYLIST tokens. On a single
    # line, a run of any whitespace between the words MUST still flag the line.
    # (danger_lines is a per-line map, so the newline separator is exercised by
    # the marker test above, not here -- a danger token split across two lines is
    # legitimately two separate lines.)
    assert dedupe.danger_lines("x.md", f"then run git{sep}push to publish") == {
        1: f"then run git{sep}push to publish"
    }
    assert dedupe.danger_lines("x.md", f"optionally rm{sep}-rf the dir") == {
        1: f"optionally rm{sep}-rf the dir"
    }


def test_multiword_marker_single_space_still_matches(dedupe):
    # Regression guard: the \s+ widening must not REGRESS the ordinary single-space
    # form that already worked before the fix.
    assert dedupe.contains_safety_marker("you MUST validate input") is True
    assert dedupe.danger_lines("x.md", "run git push now") == {1: "run git push now"}


def test_safety_marker_closing_and_forbidden_tags(dedupe):
    # I1/I2: closing tag forms (</RULE>, </CRITICAL>) and both FORBIDDEN tag forms
    # (<FORBIDDEN>, </FORBIDDEN>) are safety markers. A closing tag is just as
    # load-bearing as its opener -- a block ending a <CRITICAL> section is still
    # safety content.
    assert dedupe.contains_safety_marker("</RULE>") is True
    assert dedupe.contains_safety_marker("</CRITICAL>") is True
    assert dedupe.contains_safety_marker("<FORBIDDEN>") is True
    assert dedupe.contains_safety_marker("</FORBIDDEN>") is True


def test_destroy_is_whole_word_danger_token(dedupe):
    # I2: "destroy" is a danger token (terraform destroy / kubectl ... destroy),
    # matched as a WHOLE WORD -- "destroyer" and "indestructible" must NOT match.
    assert dedupe.danger_lines("x.md", "terraform destroy the stack") == {
        1: "terraform destroy the stack"
    }
    assert dedupe.danger_lines("x.md", "the destroyer arrives at dawn") == {}
    assert dedupe.danger_lines("x.md", "this material is indestructible") == {}


def test_inline_mandatory_clause3_span_boundary_inclusive(dedupe):
    # Lock Clause 3's inclusive ``start_line <= L <= end_line`` bounds. A danger
    # line AT the block's end_line taints it; a danger line at end_line+1 (one row
    # outside the span) does NOT. Build the block by hand for an exact span.
    block = dedupe._make_block(
        "x.md", "heading-section", start_line=10, end_line=20,
        raw_text="## Guard\n\nA calm marker-free paragraph describing the steps.",
        parent_key=None,
    )
    # Danger line exactly at end_line (inside, inclusive) -> inline-mandatory.
    assert dedupe.is_inline_mandatory(block, all_lines={20: "git push"}) is True
    # Danger line exactly at start_line (inside, inclusive) -> inline-mandatory.
    assert dedupe.is_inline_mandatory(block, all_lines={10: "git push"}) is True
    # Danger line at end_line + 1 (just outside the span) -> NOT tainted.
    assert dedupe.is_inline_mandatory(block, all_lines={21: "git push"}) is False
    # Danger line at start_line - 1 (just outside the span) -> NOT tainted.
    assert dedupe.is_inline_mandatory(block, all_lines={9: "git push"}) is False


# ---------------------------------------------------------------------------
# Task 8: group expansion (empirical dependency grammar), seed resolution
# (names vs paths -- CRITICAL 2), and unresolved-reference reporting (C1).
# ---------------------------------------------------------------------------


def test_build_corpus_index_maps_names_to_paths(dedupe):
    """build_corpus_index keys the resolved corpus by artifact NAME:
    skills/<name>/SKILL.md -> <name>, commands/<name>.md -> <name>, and any
    other resolved *.md (flat fixtures, shared-references) -> filename stem.
    Assert the COMPLETE name->path mapping, not membership."""
    root = FIXTURE_DIR / "group"
    corpus_files = dedupe.resolve_corpus(str(root))
    index = dedupe.build_corpus_index(corpus_files)
    expected = {
        "seed": (root / "skills" / "seed" / "SKILL.md").resolve().as_posix(),
        "orchestrator": (
            (root / "skills" / "orchestrator" / "SKILL.md").resolve().as_posix()
        ),
        "helper": (root / "skills" / "helper" / "SKILL.md").resolve().as_posix(),
        "analyzer": (root / "skills" / "analyzer" / "SKILL.md").resolve().as_posix(),
    }
    assert index == expected


def test_build_corpus_index_command_and_stem_names(dedupe, tmp_path):
    """commands/<name>.md keys on <name>; a flat *.md keys on its stem."""
    (tmp_path / "commands").mkdir()
    cmd = tmp_path / "commands" / "do-thing.md"
    cmd.write_text("# do-thing\n\nA command.\n", encoding="utf-8")
    flat = tmp_path / "loose_ref.md"
    flat.write_text("# loose\n\nA flat reference file.\n", encoding="utf-8")
    corpus_files = dedupe.resolve_corpus(str(tmp_path))
    index = dedupe.build_corpus_index(corpus_files)
    assert index == {
        "do-thing": cmd.resolve().as_posix(),
        "loose_ref": flat.resolve().as_posix(),
    }


def test_resolve_seed_entry_dot_md_is_path(dedupe):
    """A seed ending in `.md` is a PATH: resolved against corpus_files and
    returned as (path, None), bypassing name resolution (CRITICAL 2)."""
    root = FIXTURE_DIR  # flat core corpus: file_a.md at root
    corpus_files = dedupe.resolve_corpus(str(root))
    index = dedupe.build_corpus_index(corpus_files)
    path, name = dedupe.resolve_seed_entry(
        "file_a.md", corpus_files=corpus_files, corpus_index=index
    )
    assert path == (root / "file_a.md").resolve().as_posix()
    assert name is None


def test_resolve_seed_entry_existing_file_is_path(dedupe):
    """A seed that has no `.md` suffix but IS an existing corpus file is a PATH
    (CRITICAL 2: exists-as-file OR ends-in-.md => path)."""
    root = FIXTURE_DIR
    corpus_files = dedupe.resolve_corpus(str(root))
    index = dedupe.build_corpus_index(corpus_files)
    full = (root / "file_a.md").resolve().as_posix()
    path, name = dedupe.resolve_seed_entry(
        full, corpus_files=corpus_files, corpus_index=index
    )
    assert path == full
    assert name is None


def test_resolve_seed_entry_bare_name_via_index(dedupe):
    """A bare name (no `.md`, not an existing file) resolves through the index and
    is returned as (None, name)."""
    root = FIXTURE_DIR / "group"
    corpus_files = dedupe.resolve_corpus(str(root))
    index = dedupe.build_corpus_index(corpus_files)
    path, name = dedupe.resolve_seed_entry(
        "helper", corpus_files=corpus_files, corpus_index=index
    )
    assert path is None
    assert name == "helper"


def test_resolve_seed_entry_unknown_name_returns_none_none(dedupe):
    """A bare name that does not resolve in the index returns (None, None) so the
    caller can raise a clear empty/not-found seed error (design §8)."""
    root = FIXTURE_DIR / "group"
    corpus_files = dedupe.resolve_corpus(str(root))
    index = dedupe.build_corpus_index(corpus_files)
    path, name = dedupe.resolve_seed_entry(
        "nonexistent-skill", corpus_files=corpus_files, corpus_index=index
    )
    assert path is None
    assert name is None


def test_expand_group_resolves_four_shapes(dedupe):
    """All four reference shapes (description `invoked by`, markdown link, `Load
    the X skill`, bare backticked-name adjacency) reach their targets."""
    root = FIXTURE_DIR / "group"
    rc, stdout, _ = _run(
        dedupe, "expand-group", "--seed", "seed",
        "--corpus", str(root), "--max-depth", "3",
    )
    assert rc == 0
    data = json.loads(stdout)
    names = " ".join(data["expanded_group"])
    assert "helper" in names
    assert "analyzer" in names
    assert "orchestrator" in names


def test_expand_group_reports_unresolved(dedupe):
    """C1: a reference-shaped typo (`sharpening-promts` adjacent to "skill") that
    resolves to nothing is surfaced in unresolved_references, never dropped."""
    root = FIXTURE_DIR / "group"
    rc, stdout, _ = _run(
        dedupe, "expand-group", "--seed", "seed", "--corpus", str(root)
    )
    assert rc == 0
    data = json.loads(stdout)
    assert any("sharpening-promts" in u for u in data["unresolved_references"])


def test_expand_group_reports_group_size(dedupe):
    """group_size equals the count of expanded_group paths (design §3.1)."""
    root = FIXTURE_DIR / "group"
    rc, stdout, _ = _run(
        dedupe, "expand-group", "--seed", "seed", "--corpus", str(root)
    )
    assert rc == 0
    data = json.loads(stdout)
    assert data["group_size"] == len(data["expanded_group"])


def test_expand_group_emits_full_schema(dedupe):
    """expand-group emits exactly the §3.8 keys; the seed file itself is part of
    expanded_group and the four targets are all present (complete-output check)."""
    root = FIXTURE_DIR / "group"
    rc, stdout, _ = _run(
        dedupe, "expand-group", "--seed", "seed", "--corpus", str(root),
        "--max-depth", "3",
    )
    assert rc == 0
    data = json.loads(stdout)
    assert set(data.keys()) == {
        "version", "seed", "corpus", "expanded_group",
        "unresolved_references", "group_size",
    }
    assert data["version"] == "1"
    assert data["seed"] == ["seed"]
    skill_path = lambda n: (  # noqa: E731 - terse local for readability
        (root / "skills" / n / "SKILL.md").resolve().as_posix()
    )
    assert set(data["expanded_group"]) == {
        skill_path("seed"), skill_path("orchestrator"),
        skill_path("helper"), skill_path("analyzer"),
    }
    assert data["unresolved_references"] == ["sharpening-promts"]
    assert data["group_size"] == 4


def test_expand_group_path_seed_lands_in_group(dedupe):
    """CRITICAL 2 regression: a bare `.md` filename seed is treated as a PATH and
    lands in expanded_group DIRECTLY, bypassing name resolution. This is the mode
    the flat-file fixtures in Tasks 9/10 rely on (`--seed file_a.md`)."""
    root = FIXTURE_DIR  # flat core corpus: file_a.md at root
    rc, stdout, _ = _run(
        dedupe, "expand-group", "--seed", "file_a.md", "--corpus", str(root)
    )
    assert rc == 0
    data = json.loads(stdout)
    assert any(p.endswith("file_a.md") for p in data["expanded_group"]), \
        "path-seed must resolve to the fixture file and enter expanded_group"


def test_expand_group_unknown_seed_is_error(dedupe):
    """An empty/not-found bare-name seed is a clear error: non-zero exit and a
    stderr message (design §8). It must NOT silently emit an empty group."""
    root = FIXTURE_DIR / "group"
    rc, stdout, stderr = _run(
        dedupe, "expand-group", "--seed", "no-such-skill", "--corpus", str(root)
    )
    assert rc != 0
    assert "no-such-skill" in stderr
    assert stdout == ""


# ---------------------------------------------------------------------------
# I1/I2 regression: dependency-grammar capture must not leak prose stopwords
# into unresolved_references, and the optional article must not eat the real
# target. These guard the C1 unresolved-report integrity.
# ---------------------------------------------------------------------------


def test_extract_references_skips_prose_stopwords(dedupe):
    """I1: bare prose after `invoked by`/`invokes`/`Load ... skill` (no backtick,
    no hyphen) is NOT recorded -- neither resolved nor unresolved. Guards the
    C1 report from prose pollution ("the", "a", "system", "configuration")."""
    text = (
        "This skill is invoked by the system at startup.\n"
        "It invokes a callback when finished.\n"
        "Load configuration skill from disk, then Load data skill.\n"
    )
    resolved, unresolved = dedupe._extract_references(text, {})
    leaked = resolved | unresolved
    for token in ("the", "a", "an", "system", "configuration", "data"):
        assert token not in leaked, f"prose stopword/word leaked: {token!r}"
    assert leaked == set(), f"no reference should be recorded, got {leaked}"


def test_extract_references_optional_article_captures_real_target(dedupe):
    """I2: `invoked by the <name>` must capture <name>, not `the`. With a
    backticked target the real name is recorded; resolved when in corpus, else a
    single clean unresolved entry (never `the`)."""
    text = "This is invoked by the `develop` skill during planning."
    # Out of corpus: surfaces as a clean single unresolved entry, not `the`.
    resolved, unresolved = dedupe._extract_references(text, {})
    assert "the" not in (resolved | unresolved)
    assert unresolved == {"develop"}
    assert resolved == set()
    # In corpus: resolved, never unresolved.
    resolved2, unresolved2 = dedupe._extract_references(
        text, {"develop": "/some/path.md"}
    )
    assert resolved2 == {"develop"}
    assert unresolved2 == set()


def test_extract_references_hyphenated_bare_name_is_recorded(dedupe):
    """A hyphenated kebab name needs no backticks to qualify as artifact-shaped:
    the `sharpening-promts` typo is still surfaced as a clean unresolved entry."""
    text = "When done, Load sharpening-promts skill to polish the output."
    resolved, unresolved = dedupe._extract_references(text, {})
    assert resolved == set()
    assert unresolved == {"sharpening-promts"}


# ---------------------------------------------------------------------------
# Task 13: backticked `.md`-path reference shape (Shape 5). A backticked
# inline-code span whose content is a path ending in `.md` is a HIGH-precision
# PATH reference -- it names a real file (zero stopword risk) -- and must be
# followed during expansion via the path-bypass resolver, NOT the name index.
# Distinguishing a path-ref from a name-ref: a bare backticked WORD that is not
# a path (`finding-dead-code`) still resolves through the name index as before.
# ---------------------------------------------------------------------------


def test_expand_group_follows_backticked_md_paths(dedupe, tmp_path):
    """A SKILL.md that references siblings via backticked `.md` paths (nested and
    bare forms) pulls those siblings into expanded_group; a backticked `.md` path
    NOT in the corpus is surfaced in unresolved_references; a control sibling
    referenced by an existing shape (markdown link) is also pulled in."""
    root = tmp_path
    (root / "skills" / "lead").mkdir(parents=True)
    (root / "skills" / "sib").mkdir(parents=True)
    (root / "refs").mkdir(parents=True)
    # Nested-path backtick form, bare-path backtick form, an existing-shape
    # control (markdown link), and a backticked `.md` path with no corpus file.
    (root / "skills" / "lead" / "SKILL.md").write_text(
        "---\nname: lead\n---\n\n"
        "# Lead\n\n"
        "The family lives in several files described below.\n\n"
        "See `refs/nested-ref.md` for the nested-path reference shape.\n\n"
        "Also consult `bare-ref.md` for the bare-path reference shape.\n\n"
        "For the control, see [the sibling](skills/sib/SKILL.md) via a link.\n\n"
        "A dangling pointer to `refs/does-not-exist.md` resolves to nothing.\n",
        encoding="utf-8",
    )
    (root / "refs" / "nested-ref.md").write_text(
        "# Nested ref\n\nNested reference target body content here for size.\n",
        encoding="utf-8",
    )
    (root / "bare-ref.md").write_text(
        "# Bare ref\n\nBare reference target body content here for size.\n",
        encoding="utf-8",
    )
    (root / "skills" / "sib" / "SKILL.md").write_text(
        "---\nname: sib\n---\n\n# Sib\n\nControl sibling reached via link shape.\n",
        encoding="utf-8",
    )
    rc, stdout, _ = _run(
        dedupe, "expand-group", "--seed", "lead",
        "--corpus", str(root), "--max-depth", "3",
    )
    assert rc == 0
    data = json.loads(stdout)
    group = data["expanded_group"]
    assert any(p.endswith("refs/nested-ref.md") for p in group), \
        "nested-path backticked `.md` ref must be followed into the group"
    assert any(p.endswith("bare-ref.md") for p in group), \
        "bare-path backticked `.md` ref must be followed into the group"
    assert any(p.endswith("sib/SKILL.md") for p in group), \
        "control markdown-link sibling must still be followed"
    assert any("does-not-exist.md" in u for u in data["unresolved_references"]), \
        "a backticked `.md` path with no corpus file is unresolved, not dropped"


def test_extract_references_nonpath_backtick_word_uses_name_index(dedupe):
    """REGRESSION: a backticked bare WORD that is NOT a path (no `/`, no `.md`)
    must still resolve via the name index when adjacent to skill/command -- it is
    NOT treated as a path. `finding-dead-code` is a name-ref, never a path-ref."""
    text = "When pruning, reach for the `finding-dead-code` skill to scan."
    # In corpus: resolves through the name index (Shape 4), no path involvement.
    resolved, unresolved = dedupe._extract_references(
        text, {"finding-dead-code": "/some/path.md"}
    )
    assert resolved == {"finding-dead-code"}
    assert unresolved == set()


def test_expand_group_backticked_path_does_not_crash_on_traversal(dedupe, tmp_path):
    """A backticked `.md` path containing `..`/absolute components must resolve
    SAFELY (recorded unresolved when it does not map to a corpus file), never
    crash or escape the corpus."""
    root = tmp_path
    (root / "skills" / "lead").mkdir(parents=True)
    (root / "skills" / "lead" / "SKILL.md").write_text(
        "---\nname: lead\n---\n\n# Lead\n\n"
        "A traversal pointer `../../../../etc/passwd.md` must resolve safely.\n"
        "An absolute pointer `/etc/shadow.md` must resolve safely too.\n",
        encoding="utf-8",
    )
    rc, stdout, _ = _run(
        dedupe, "expand-group", "--seed", "lead", "--corpus", str(root)
    )
    assert rc == 0
    data = json.loads(stdout)
    # Neither escapes into the group; both are surfaced as unresolved.
    assert all("passwd" not in p for p in data["expanded_group"])
    assert all("shadow" not in p for p in data["expanded_group"])
    assert any("passwd.md" in u for u in data["unresolved_references"])
    assert any("shadow.md" in u for u in data["unresolved_references"])


def test_expand_group_backticked_md_path_e2e_real_dedupe(dedupe):
    """END-TO-END on the REAL dedupe artifacts: expanding `--seed dedupe` over the
    dedupe family corpus must now pull in the command + reference files that
    SKILL.md names by backticked `.md` path, not just SKILL.md alone (pre-fix
    behavior was group_size == 1, so this is a non-vacuous regression lock)."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    corpus = ",".join(
        str(repo_root / rel)
        for rel in (
            "skills/dedupe/SKILL.md",
            "commands/dedupe-setup.md",
            "commands/dedupe-analyze.md",
            "commands/dedupe-report.md",
            "commands/dedupe-apply.md",
            "skills/dedupe/references/verdict-taxonomy.md",
            "skills/dedupe/references/counterfactual-prompt.md",
        )
    )
    rc, stdout, _ = _run(
        dedupe, "expand-group", "--seed", "dedupe",
        "--corpus", corpus, "--max-depth", "3",
    )
    assert rc == 0
    data = json.loads(stdout)
    group = data["expanded_group"]
    # Pre-fix this was exactly [SKILL.md]; the fix must reach further.
    assert data["group_size"] > 1, "backticked `.md` paths must expand the group"
    basenames = {Path(p).name for p in group}
    assert "dedupe-setup.md" in basenames
    assert "verdict-taxonomy.md" in basenames
    assert "counterfactual-prompt.md" in basenames


def test_resolve_path_reference_ambiguous_is_deterministic(dedupe):
    """A bare path-ref that suffix-matches MULTIPLE corpus members must resolve to
    a STABLE, deterministic winner under the (len, lexicographic) tie-break --
    shortest resolved path wins, ties broken lexicographically. ``corpus_by_resolved``
    keys come from a set (hash-randomized iteration), so the pre-fix
    "first-in-iteration-order" logic could return either member nondeterministically
    across processes; this asserts the specific (len, lex)-min winner, which the old
    code could not guarantee."""
    # Two corpus members share the basename ``config.md``. Under (len, lex), the
    # shorter path wins; on equal length, the lexicographically smaller path wins.
    short_winner = "/repo/a/config.md"      # len 17
    long_loser = "/repo/zzz/b/config.md"    # len 21
    corpus_by_resolved = {long_loser: long_loser, short_winner: short_winner}
    result = dedupe.resolve_path_reference(
        "config.md", from_file="/repo/lead/SKILL.md",
        corpus_by_resolved=corpus_by_resolved,
    )
    assert result == short_winner, "shortest path must win the ambiguous suffix match"

    # Stability across many iteration orders: shuffle the dict insertion order and
    # confirm the SAME winner every time (the old set-iteration logic could flip).
    import random
    items = [(short_winner, short_winner), (long_loser, long_loser),
             ("/repo/m/n/config.md", "/repo/m/n/config.md")]
    for _ in range(50):
        random.shuffle(items)
        shuffled = dict(items)
        again = dedupe.resolve_path_reference(
            "config.md", from_file="/repo/lead/SKILL.md",
            corpus_by_resolved=shuffled,
        )
        assert again == short_winner

    # Lexicographic tie-break on EQUAL-length paths.
    tie_a = "/repo/aaa/config.md"
    tie_b = "/repo/bbb/config.md"
    assert len(tie_a) == len(tie_b)
    tied = dedupe.resolve_path_reference(
        "config.md", from_file="/repo/x.md",
        corpus_by_resolved={tie_b: tie_b, tie_a: tie_a},
    )
    assert tied == tie_a, "equal-length paths must break ties lexicographically"


def test_resolve_path_reference_handles_posix_form_corpus_keys(dedupe):
    """REGRESSION (Windows path handling): backticked `.md`-PATH refs are written
    with forward slashes (``refs/nested-ref.md``), but ``str(Path(p).resolve())``
    on Windows yields backslashes. The resolver MUST compare in POSIX form so a
    repo-relative ref ending in ``refs/nested-ref.md`` matches a corpus path that
    was stored in canonical POSIX form. Exercises the contract directly so the
    test passes on macOS/Linux while locking the cross-platform behavior."""
    # corpus_by_resolved is populated with POSIX-form keys (the canonical form
    # used everywhere in dedupe.py after _resolved_str / as_posix normalization).
    posix_key = "/repo/skills/lead/refs/nested-ref.md"
    corpus_by_resolved = {posix_key: posix_key}
    # Bare-form path-ref (filename only): suffix-matches by ``/<ref>``.
    assert dedupe.resolve_path_reference(
        "nested-ref.md", from_file="/repo/skills/lead/SKILL.md",
        corpus_by_resolved=corpus_by_resolved,
    ) == posix_key
    # Nested-form path-ref (POSIX-style ref): exact suffix match.
    assert dedupe.resolve_path_reference(
        "refs/nested-ref.md", from_file="/repo/skills/lead/SKILL.md",
        corpus_by_resolved=corpus_by_resolved,
    ) == posix_key


def test_resolve_path_reference_ambiguous_e2e_deterministic_across_hashseed(dedupe):
    """E2E proof of non-vacuity: run the full ``expand-group`` path under several
    PYTHONHASHSEED values via subprocess; the chosen ambiguous member must be
    identical across all seeds. The pre-fix set-iteration resolver would return
    different members under different seeds."""
    import os
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "a").mkdir()
        (root / "zzz" / "b").mkdir(parents=True)
        # Lead references a bare ``config.md`` that suffix-matches BOTH members.
        (root / "lead.md").write_text(
            "---\nname: lead\n---\n\n# Lead\n\n"
            "See `config.md` for shared configuration details here.\n",
            encoding="utf-8",
        )
        (root / "a" / "config.md").write_text(
            "# Config A\n\nShort-path config target body content here.\n",
            encoding="utf-8",
        )
        (root / "zzz" / "b" / "config.md").write_text(
            "# Config B\n\nLong-path config target body content here.\n",
            encoding="utf-8",
        )
        winner_basename_path = (root / "a" / "config.md").resolve().as_posix()

        chosen: set[str] = set()
        for seed in ("0", "1", "42", "1000"):
            env = dict(os.environ)
            env["PYTHONHASHSEED"] = seed
            env["PYTEST_ADDOPTS"] = ""
            proc = subprocess.run(
                [sys.executable, str(HELPER_PATH), "expand-group",
                 "--seed", "lead", "--corpus", str(root), "--max-depth", "3"],
                capture_output=True, text=True, env=env, check=True,
            )
            data = json.loads(proc.stdout)
            config_members = [p for p in data["expanded_group"]
                              if p.endswith("config.md")]
            assert config_members == [winner_basename_path], (
                f"seed={seed}: ambiguous ref must resolve to the (len,lex) winner; "
                f"got {config_members}"
            )
            chosen.add(tuple(config_members) and config_members[0])
        assert chosen == {winner_basename_path}, \
            "ambiguous resolution must be identical across all PYTHONHASHSEED values"


# ---------------------------------------------------------------------------
# Task 9: detect + external-callers subcommands + cost ceiling (C5, §3.6, §3.9,
# §5.4). The standalone external scan and the INTEGRATED detect -> external scan
# path are both exercised; the integrated path is the IMPORTANT-3 regression
# (external_callers populated NON-EMPTY end-to-end, not just by the standalone
# subcommand).
# ---------------------------------------------------------------------------


def test_external_callers_multishape_recall(dedupe, tmp_path):
    """§5.4/§9.5: the standalone external-callers scan reports an out-of-group
    caller for each of the three shapes (identical, whitespace-variant,
    one-word-drift). match_signal is pinned to "jaccard" and every match_ratio is
    at or above the 0.7 external threshold; the outsider file is among callers."""
    root = FIXTURE_DIR / "external"
    # Build a blocks-json for the in-group EXTRACT candidate by segmenting
    # ingroup_a.md and serializing its blocks (dataclasses.asdict on each Block).
    import dataclasses
    ingroup = root / "ingroup_a.md"
    blocks = dedupe.segment("ingroup_a.md", ingroup.read_text(encoding="utf-8"))
    blocks_json = tmp_path / "candidate_blocks.json"
    blocks_json.write_text(
        json.dumps([dataclasses.asdict(b) for b in blocks]), encoding="utf-8"
    )
    rc, stdout, _ = _run(
        dedupe, "external-callers",
        "--blocks-json", str(blocks_json), "--corpus", str(root),
        "--external-threshold", "0.7",
    )
    assert rc == 0
    data = json.loads(stdout)
    assert data["version"] == "1"
    assert data["external_callers"], "out-of-group caller must be reported"
    assert all(c["match_signal"] == "jaccard" for c in data["external_callers"])
    assert all(c["match_ratio"] >= 0.7 for c in data["external_callers"])
    # Each caller dict carries the full §3.8 external-callers shape.
    for caller in data["external_callers"]:
        assert set(caller) == {
            "block_id", "caller_file", "caller_start_line",
            "match_ratio", "match_signal",
        }
    # outsider.md must be among the callers (the standalone scan has no group
    # context, so it may also report ingroup_b.md, which legitimately shares the
    # block; the integrated detect path, which knows the group, excludes
    # ingroup_b.md).
    assert any("outsider.md" in c["caller_file"] for c in data["external_callers"])


def test_detect_emits_group_result_schema(dedupe):
    """§3.9: detect emits the full GroupResult schema. The core fixture files are
    a flat corpus with no cross-references, so seed all three as path-seeds to
    form a multi-file group with real cross-file pairs."""
    root = FIXTURE_DIR  # the core fixture corpus from Task 6
    rc, stdout, _ = _run(
        dedupe, "detect", "--seed", "file_a.md", "file_b.md", "file_c.md",
        "--corpus", str(root), "--max-pairs", "200",
    )
    assert rc == 0
    data = json.loads(stdout)
    assert set(data) == {
        "version", "seed", "corpus", "expanded_group",
        "unresolved_references", "cost_ceiling_exceeded",
        "candidate_count", "pairs", "external_callers",
    }
    assert data["version"] == "1"
    assert data["seed"] == ["file_a.md", "file_b.md", "file_c.md"]
    assert data["cost_ceiling_exceeded"] is False
    assert data["pairs"], "the core fixture has known duplicates; pairs must be non-empty"
    for pair in data["pairs"]:
        assert set(pair) == {
            "a", "b", "jaccard", "seqmatch_ratio", "drift_delta",
            "is_drift_candidate", "contains_safety_marker", "a_text", "b_text",
        }
        for endpoint in (pair["a"], pair["b"]):
            assert set(endpoint) == {
                "file", "granularity", "start_line", "end_line", "block_id",
                "parent_key", "inline_mandatory",
            }
            # parent_key is the enclosing heading-section block_id (str) or None
            # for a heading-section root; inline_mandatory is the full Clauses
            # 1+2+3 predicate from is_inline_mandatory (commands/dedupe-analyze.md
            # Phase 3 depends on this carrying the full predicate, not only the
            # marker-based clauses).
            assert endpoint["parent_key"] is None or isinstance(endpoint["parent_key"], str)
            assert isinstance(endpoint["inline_mandatory"], bool)


def test_detect_cost_ceiling(dedupe):
    """§3.6: a --max-pairs below the confirmed-candidate count sets
    cost_ceiling_exceeded True and truncates pairs to the ceiling. Seeding all
    three files makes candidate_count > 1 so the assertion is non-vacuous."""
    root = FIXTURE_DIR
    rc, stdout, _ = _run(
        dedupe, "detect", "--seed", "file_a.md", "file_b.md", "file_c.md",
        "--corpus", str(root), "--max-pairs", "1",
    )
    assert rc == 0
    data = json.loads(stdout)
    assert data["candidate_count"] > 1, \
        "fixture must yield >1 confirmed candidate to test the ceiling"
    assert data["cost_ceiling_exceeded"] is True
    assert len(data["pairs"]) == 1


def test_detect_pairs_only_within_group(dedupe):
    """The corpus partition: detect pairs are scored ONLY over the expanded group
    (group_files), never over out-of-group corpus files. Seeding the two ingroup
    files with outsider.md in the corpus must keep every pair endpoint inside the
    group; outsider.md never appears as a pair endpoint (it is the out-of-group
    external-scan set, not part of pairing)."""
    root = FIXTURE_DIR / "external"
    rc, stdout, _ = _run(
        dedupe, "detect", "--seed", "ingroup_a.md", "ingroup_b.md",
        "--corpus", str(root),
    )
    assert rc == 0
    data = json.loads(stdout)
    group = set(data["expanded_group"])
    assert any(p.endswith("ingroup_a.md") for p in group)
    assert any(p.endswith("ingroup_b.md") for p in group)
    assert not any(p.endswith("outsider.md") for p in group), \
        "outsider.md is in the corpus but NOT the group"
    assert data["pairs"], "the two in-group files share an identical candidate block"
    for pair in data["pairs"]:
        assert pair["a"]["file"] in group
        assert pair["b"]["file"] in group
        assert "outsider.md" not in pair["a"]["file"]
        assert "outsider.md" not in pair["b"]["file"]


def test_detect_populates_external_callers_end_to_end(dedupe):
    """IMPORTANT 3: the integrated detect -> external_caller_scan path must
    populate external_callers NON-EMPTY, not just the standalone external-callers
    subcommand. Uses the external/ fixture: ingroup_a.md + ingroup_b.md form the
    (path-)seed group with a confirmed in-group EXTRACT-eligible duplicate;
    outsider.md is in the corpus but out of the group and carries matching shapes
    of the candidate. The group-aware path excludes ingroup_b.md, so every caller
    lives in outsider.md."""
    root = FIXTURE_DIR / "external"
    rc, stdout, _ = _run(
        dedupe, "detect", "--seed", "ingroup_a.md", "ingroup_b.md",
        "--corpus", str(root), "--external-threshold", "0.7",
    )
    assert rc == 0
    data = json.loads(stdout)
    assert data["external_callers"], \
        "detect must surface the out-of-group caller via the integrated external scan"
    assert all(c["match_signal"] == "jaccard" for c in data["external_callers"])
    assert all(c["match_ratio"] >= 0.7 for c in data["external_callers"])
    # The caller lives outside the edited group; ingroup_b.md (in the group) is
    # excluded by the group_files partition even though it shares the block.
    assert all("outsider.md" in c["caller_file"] for c in data["external_callers"])
    assert not any("ingroup_" in c["caller_file"] for c in data["external_callers"])


def test_detect_no_external_callers_without_confirmed_duplicate(dedupe):
    """When the group has no confirmed in-group duplicate there are no
    EXTRACT-eligible candidates, so external_callers is correctly EMPTY. Seeding a
    single file means no cross-file in-group pair can form -> no candidates ->
    empty external scan (proves external_callers is candidate-driven, not a blind
    whole-corpus dump)."""
    root = FIXTURE_DIR / "external"
    rc, stdout, _ = _run(
        dedupe, "detect", "--seed", "ingroup_a.md",
        "--corpus", str(root), "--external-threshold", "0.7",
    )
    assert rc == 0
    data = json.loads(stdout)
    assert data["pairs"] == [], "a single-file group cannot form a cross-file pair"
    assert data["external_callers"] == [], \
        "no confirmed in-group duplicate -> no EXTRACT candidate -> no external callers"


def test_detect_deterministic_ordering(dedupe):
    """Task 6 suggestion #3 (applied here): detect serializes pairs and
    external_callers in a DETERMINISTIC order so output diffs/journals are stable.
    Two runs over the same corpus produce byte-identical JSON, and the pair order
    is the documented sort key (by a.block_id, then b.block_id)."""
    root = FIXTURE_DIR
    argv = (
        "detect", "--seed", "file_a.md", "file_b.md", "file_c.md",
        "--corpus", str(root), "--max-pairs", "200",
    )
    rc1, out1, _ = _run(dedupe, *argv)
    rc2, out2, _ = _run(dedupe, *argv)
    assert rc1 == 0 and rc2 == 0
    assert out1 == out2, "detect output must be byte-stable across runs"
    data = json.loads(out1)
    pair_keys = [(p["a"]["block_id"], p["b"]["block_id"]) for p in data["pairs"]]
    assert pair_keys == sorted(pair_keys), \
        "pairs must be sorted by (a.block_id, b.block_id)"
    caller_keys = [
        (c["block_id"], c["caller_file"], c["caller_start_line"])
        for c in data["external_callers"]
    ]
    assert caller_keys == sorted(caller_keys), \
        "external_callers must be sorted by (block_id, caller_file, caller_start_line)"


# ---------------------------------------------------------------------------
# Task 9 review (IMPORTANT 1): cost-ceiling branches must emit a CONSISTENT
# pair population. `pairs` is CONFIRMED-ONLY (seqmatch_ratio >= confirm_threshold)
# in BOTH branches -- whether or not the cost ceiling trips. A non-confirmed
# jaccard-survivor (high Jaccard but seqmatch_ratio < confirm_threshold, e.g. a
# heavily reordered near-duplicate) must NEVER appear in `pairs`. (design §3.6,
# §3.9, §4)
# ---------------------------------------------------------------------------


def _confirm_ceiling_corpus(tmp_path):
    """Seed a 3-file corpus with TWO confirmed cross-file duplicates plus ONE
    non-confirmed jaccard-survivor (a reordered near-duplicate: identical token
    set -> Jaccard 1.0, scrambled order -> seqmatch_ratio well below the 0.85
    confirm threshold). Returns (root, reorder_marker)."""
    root = tmp_path / "corpus"
    root.mkdir()
    confirmed = (
        "The deployment runbook says operators must verify the staging smoke "
        "suite is fully green before promoting any build to the production trunk."
    )
    confirmed2 = (
        "Every contributor should record the rationale behind each architectural "
        "decision so future maintainers understand the tradeoffs that were chosen."
    )
    # Reordered near-duplicate: same words, scrambled order. The "alpha"/"omega"
    # token is the stable marker we assert on.
    reorder_a = (
        "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda omicron "
        "sigma tau"
    )
    reorder_b = (
        "tau sigma omicron lambda kappa iota theta eta zeta epsilon delta gamma "
        "beta alpha"
    )
    (root / "file_a.md").write_text(
        f"---\nname: a\n---\n\n{confirmed}\n\n{confirmed2}\n\n{reorder_a}\n",
        encoding="utf-8",
    )
    (root / "file_b.md").write_text(
        f"---\nname: b\n---\n\n{confirmed}\n\n{reorder_b}\n", encoding="utf-8"
    )
    (root / "file_c.md").write_text(
        f"---\nname: c\n---\n\n{confirmed2}\n", encoding="utf-8"
    )
    return root, "alpha"


def _reorder_in_pairs(data, marker):
    return any(
        marker in pair["a_text"] or marker in pair["b_text"]
        for pair in data["pairs"]
    )


def test_detect_pairs_confirmed_only_no_ceiling(dedupe, tmp_path):
    """IMPORTANT 1: with a high --max-pairs (ceiling NOT exceeded), `pairs` is
    confirmed-only -- the non-confirmed reordered near-duplicate is absent and
    candidate_count equals len(pairs)."""
    root, marker = _confirm_ceiling_corpus(tmp_path)
    rc, stdout, _ = _run(
        dedupe, "detect", "--seed", "file_a.md", "file_b.md", "file_c.md",
        "--corpus", str(root), "--max-pairs", "200",
    )
    assert rc == 0
    data = json.loads(stdout)
    assert data["cost_ceiling_exceeded"] is False
    assert data["pairs"], "the two confirmed duplicates must populate pairs"
    # (a) the non-confirmed reordered pair never appears in pairs.
    assert not _reorder_in_pairs(data, marker), \
        "non-confirmed reordered near-duplicate must be excluded from pairs"
    # (b) candidate_count == len(pairs) when the ceiling is not exceeded.
    assert data["candidate_count"] == len(data["pairs"]), \
        "candidate_count must equal len(pairs) when no ceiling truncation occurs"


def test_detect_pairs_confirmed_only_ceiling_tripped(dedupe, tmp_path):
    """IMPORTANT 1: with --max-pairs 1 (ceiling exceeded), pair membership is
    still drawn ONLY from the confirmed set -- the non-confirmed reordered
    near-duplicate stays absent, and pairs is truncated to <= 1."""
    root, marker = _confirm_ceiling_corpus(tmp_path)
    rc, stdout, _ = _run(
        dedupe, "detect", "--seed", "file_a.md", "file_b.md", "file_c.md",
        "--corpus", str(root), "--max-pairs", "1",
    )
    assert rc == 0
    data = json.loads(stdout)
    assert data["candidate_count"] > 1, \
        "fixture must yield >1 confirmed candidate so the ceiling is non-vacuous"
    assert data["cost_ceiling_exceeded"] is True
    assert len(data["pairs"]) <= 1
    # (c) membership is confirmed-only even under truncation.
    assert not _reorder_in_pairs(data, marker), \
        "non-confirmed reordered near-duplicate must stay absent under the ceiling"


# ---------------------------------------------------------------------------
# Task 9 review (IMPORTANT 2): standalone external-callers must fail gracefully
# on a malformed --blocks-json record (extra/unexpected key) -- a one-line
# stderr message and rc 2, matching the sibling validation branches, not an
# uncaught TypeError traceback.
# ---------------------------------------------------------------------------


def test_external_callers_malformed_record_shape_returns_two(dedupe, tmp_path):
    """A --blocks-json record with an unexpected key must yield rc 2 and a
    one-line stderr message (not a TypeError traceback)."""
    blocks_json = tmp_path / "bad_blocks.json"
    blocks_json.write_text(
        json.dumps([{"file": "x.md", "not_a_real_field": 1}]), encoding="utf-8"
    )
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "any.md").write_text("# h\n\nbody\n", encoding="utf-8")
    rc, _, stderr = _run(
        dedupe, "external-callers",
        "--blocks-json", str(blocks_json), "--corpus", str(corpus),
    )
    assert rc == 2
    assert stderr.strip(), "a malformed record must produce a one-line stderr message"
    assert "blocks-json" in stderr


# ---------------------------------------------------------------------------
# Task 10: verify subcommand + apply-journal schema + zero-auto-edit invariant
# (plan §"Task 10"; design §5.3.1, §3.8, §9.4 / Success Criterion #3).
# ---------------------------------------------------------------------------


def _corpus_hashes(root: Path) -> dict[Path, str]:
    """sha256 of every *.md file under root, keyed by path (relative to root so
    two corpora rooted at different tmp dirs are comparable in spirit, though
    here each map is only ever compared to a before/after snapshot of itself)."""
    return {
        p.relative_to(root): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*.md"))
    }


def test_script_never_edits_corpus(dedupe, tmp_path):
    """Zero-auto-edit (Success Criterion #3): ALL THREE read-only subcommands --
    detect, external-callers, AND verify -- leave their corpus byte-identical.

    detect and external-callers share one copied snapshot of the core fixture
    corpus (the external scan segments a corpus file into a --blocks-json exactly
    as test_external_callers_multishape_recall does, then runs against the same
    corpus). verify needs the journal-shaped corpus produced by
    _build_verify_corpus, so it gets its own before/after snapshot. The point is
    that external-callers and verify are each PROVEN non-mutating, not just detect.
    """
    import dataclasses
    import shutil

    # --- detect + external-callers over a shared copy of the core fixture corpus.
    work = tmp_path / "corpus"
    shutil.copytree(FIXTURE_DIR, work)
    before = _corpus_hashes(work)

    rc, _, _ = _run(dedupe, "detect", "--seed", "file_a.md", "--corpus", str(work))
    assert rc == 0
    assert _corpus_hashes(work) == before, "detect must not mutate any source file"

    blocks = dedupe.segment("file_a.md", (work / "file_a.md").read_text(encoding="utf-8"))
    blocks_json = tmp_path / "candidate_blocks.json"
    blocks_json.write_text(
        json.dumps([dataclasses.asdict(b) for b in blocks]), encoding="utf-8"
    )
    rc, _, _ = _run(
        dedupe, "external-callers",
        "--blocks-json", str(blocks_json), "--corpus", str(work),
        "--external-threshold", "0.7",
    )
    assert rc == 0
    assert _corpus_hashes(work) == before, \
        "external-callers must not mutate any source file"

    # --- verify over its own journal-shaped corpus (distinct structure/root).
    verify_tmp = tmp_path / "verify"
    verify_tmp.mkdir()
    vwork, journal = _build_verify_corpus(
        verify_tmp,
        source_body="# Apply\n\n" + _VERIFY_POINTER + "\nThen run the apply.\n",
        reference_body=_VERIFY_ORIGINAL,
    )
    vbefore = _corpus_hashes(vwork)
    rc, _, _ = _run(dedupe, "verify", "--journal", str(journal), "--corpus", str(vwork))
    assert rc == 0
    assert _corpus_hashes(vwork) == vbefore, "verify must not mutate any source file"


# Shared arrange material for the verify tests. The "original" duplicate block is a
# real >80-char paragraph; the pointer replaces it; the reference file holds the
# canonical copy. content_hash is computed from original_text exactly as the script does.
_VERIFY_ORIGINAL = (
    "Always create the canonical reference file before deleting any duplicate "
    "occurrence so the consolidated content is never lost during apply.\n"
)
_VERIFY_POINTER = "Load `apply-ordering` from `skills/shared-references/apply-ordering.md`\n"


def _content_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _build_verify_corpus(tmp_path, *, source_body: str, reference_body: str | None):
    """Create a tiny corpus (one source file + optional reference file) and a journal
    whose single finding/edit records _VERIFY_ORIGINAL -> _VERIFY_POINTER. Returns
    (work_dir, journal_path)."""
    work = tmp_path / "corpus"
    (work / "skills" / "shared-references").mkdir(parents=True)
    (work / "commands").mkdir(parents=True)
    source = work / "commands" / "edited.md"
    source.write_text(source_body, encoding="utf-8")
    ref_rel = "skills/shared-references/apply-ordering.md"
    if reference_body is not None:
        (work / ref_rel).write_text(reference_body, encoding="utf-8")
    journal = tmp_path / "journal.json"
    journal.write_text(json.dumps({
        "version": "1",
        "created_at": "2026-05-25T00:00:00Z",
        "findings": [{
            "finding_id": "cluster-1",
            "status": "sources_edited",
            "reference_files": [ref_rel],
            "edits": [{
                "file": "commands/edited.md",
                "original_text": _VERIFY_ORIGINAL,
                "replacement_text": _VERIFY_POINTER.strip(),
                "start_line": 3,
                "end_line": 4,
                "content_hash": _content_hash(_VERIFY_ORIGINAL),
            }],
        }],
    }), encoding="utf-8")
    return work, journal


def test_verify_passes_for_consolidated_finding(dedupe, tmp_path):
    """Both clauses hold: original duplicate ABSENT from source, pointer PRESENT in
    source, AND reference file exists containing the canonical block -> verify PASS."""
    source_body = "# Apply\n\n" + _VERIFY_POINTER + "\nThen run the apply.\n"
    work, journal = _build_verify_corpus(
        tmp_path, source_body=source_body, reference_body=_VERIFY_ORIGINAL
    )
    rc, stdout, _ = _run(dedupe, "verify", "--journal", str(journal),
                         "--corpus", str(work))
    data = json.loads(stdout)
    assert all(r["pass"] for r in data["results"]), data["results"]


def test_verify_fails_when_duplicate_still_present(dedupe, tmp_path):
    """Clause 1 isolated: pointer present AND reference exists, but the ORIGINAL
    duplicate is ALSO still in the source -> verify FAIL (so clause 1 cannot be
    silently skipped; only the still-present-duplicate condition causes the fail)."""
    source_body = "# Apply\n\n" + _VERIFY_POINTER + "\n" + _VERIFY_ORIGINAL
    work, journal = _build_verify_corpus(
        tmp_path, source_body=source_body, reference_body=_VERIFY_ORIGINAL
    )
    rc, stdout, _ = _run(dedupe, "verify", "--journal", str(journal),
                         "--corpus", str(work))
    data = json.loads(stdout)
    assert any(not r["pass"] for r in data["results"]), data["results"]
    reasons = [s for r in data["results"] for s in r["reasons"]]
    assert any("clause1" in s for s in reasons), reasons


def test_verify_fails_when_pointer_or_reference_missing(dedupe, tmp_path):
    """Clause 2 isolated: original duplicate ABSENT (so clause 1 holds), but neither
    the pointer line is present nor the reference file exists -> verify FAIL (so
    clause 2 cannot be silently skipped; only the missing-pointer/ref condition fails)."""
    source_body = "# Apply\n\nSome unrelated prose that is long enough to be a block here.\n"
    work, journal = _build_verify_corpus(
        tmp_path, source_body=source_body, reference_body=None
    )
    rc, stdout, _ = _run(dedupe, "verify", "--journal", str(journal),
                         "--corpus", str(work))
    data = json.loads(stdout)
    assert any(not r["pass"] for r in data["results"]), data["results"]
    reasons = [s for r in data["results"] for s in r["reasons"]]
    assert any("clause2" in s for s in reasons), reasons


def test_verify_fails_when_reference_block_fragmented(dedupe, tmp_path):
    """Clause 2 content-integrity: the reference file must CONTAIN the consolidated
    block (a re-segmented block matching original_text at/above the confirm
    threshold), not merely clear a whole-file similarity ratio. Here the canonical
    sentence is fragmented -- split across two paragraphs with an unrelated note
    between them -- so NO single segmented block matches _VERIFY_ORIGINAL at >= 0.85
    (best block ratio ~0.842), yet the whole-file seqmatch ratio is ~0.90 (>= 0.85).
    A whole-file fallback would FALSE-PASS this; per-block matching correctly FAILs.

    Clauses 1 and 2a are satisfied (original duplicate absent, pointer present) so
    only the fragmented-reference condition can drive the failure."""
    # Fragmented reference: _VERIFY_ORIGINAL split after the 5th word, with a short
    # unrelated separator that re-merges the halves into one sub-threshold block.
    words = _VERIFY_ORIGINAL.strip().split(" ")
    half1 = " ".join(words[:5])
    half2 = " ".join(words[5:])
    fragmented_ref = f"{half1}\n\nSee the canonical block above.\n\n{half2}\n"
    source_body = "# Apply\n\n" + _VERIFY_POINTER + "\nThen run the apply.\n"
    work, journal = _build_verify_corpus(
        tmp_path, source_body=source_body, reference_body=fragmented_ref
    )
    rc, stdout, _ = _run(dedupe, "verify", "--journal", str(journal),
                         "--corpus", str(work))
    data = json.loads(stdout)
    assert any(not r["pass"] for r in data["results"]), data["results"]
    reasons = [s for r in data["results"] for s in r["reasons"]]
    assert any("does not contain the consolidated" in s for s in reasons), reasons


def test_verify_resolves_comma_corpus(dedupe, tmp_path):
    """The --corpus contract is a COMMA-SEPARATED list of files/dirs. For verify,
    the journal's repo-relative paths resolve against a single ROOT derived from
    that list (a lone dir is the root; multiple entries use their common ancestor).
    Treating the entire comma-joined arg as one Path() yields a bogus root so every
    finding silently reports pass: false. Passing the same work dir twice
    (`work,work`) must resolve to that dir as root and the consolidated finding
    must PASS exactly as the single-dir form does."""
    source_body = "# Apply\n\n" + _VERIFY_POINTER + "\nThen run the apply.\n"
    work, journal = _build_verify_corpus(
        tmp_path, source_body=source_body, reference_body=_VERIFY_ORIGINAL
    )
    rc, stdout, _ = _run(dedupe, "verify", "--journal", str(journal),
                         "--corpus", f"{work},{work}")
    data = json.loads(stdout)
    assert all(r["pass"] for r in data["results"]), data["results"]


def test_verify_fails_when_no_edits(dedupe, tmp_path):
    """A finding with an empty edits list checks nothing; it must NOT vacuously PASS
    (a green mirage that reports a consolidation 'landed' while verifying nothing).
    It must FAIL with a reason naming the missing edits."""
    work, journal = _build_verify_corpus(
        tmp_path,
        source_body="# Apply\n\nUnrelated prose long enough to be a block here.\n",
        reference_body=_VERIFY_ORIGINAL,
    )
    data_journal = json.loads(journal.read_text(encoding="utf-8"))
    data_journal["findings"][0]["edits"] = []
    journal.write_text(json.dumps(data_journal), encoding="utf-8")
    rc, stdout, _ = _run(dedupe, "verify", "--journal", str(journal),
                         "--corpus", str(work))
    data = json.loads(stdout)
    assert any(not r["pass"] for r in data["results"]), data["results"]
    reasons = [s for r in data["results"] for s in r["reasons"]]
    assert any("edits" in s for s in reasons), reasons


def test_skill_frontmatter_parses_and_is_dedupe():
    """Task 11 contract: SKILL.md has a parseable YAML frontmatter block whose
    name is 'dedupe' and whose description is non-empty. Parsed with a minimal
    frontmatter splitter (no third-party yaml dependency)."""
    skill = (
        Path(__file__).resolve().parent.parent.parent
        / "skills" / "dedupe" / "SKILL.md"
    )
    text = skill.read_text(encoding="utf-8")
    assert text.startswith("---\n"), "SKILL.md must open with a YAML frontmatter fence"
    _, fm, _ = text.split("---\n", 2)  # frontmatter between first two fences; relies on no bare '---' HR in body
    fields = {}
    for line in fm.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            fields[key.strip()] = val.strip().strip('"').strip()
    assert fields.get("name") == "dedupe", f"expected name: dedupe, got {fields.get('name')!r}"
    assert fields.get("description"), "SKILL.md description must be non-empty"
