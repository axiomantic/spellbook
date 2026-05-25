"""Unit tests for skills/dedupe/scripts/dedupe.py.

Loads the helper as a module via importlib (without executing main) and
exercises each subcommand against seeded fixture corpora. Default suite --
no integration marker; pure stdlib, no QMD/Serena.
"""
from __future__ import annotations

import ast
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
# Task 1: the four subcommands are registered and dispatchable, each emitting
# a valid JSON shell ({"version": SCHEMA_VERSION}) and returning 0 (stubs).
# ---------------------------------------------------------------------------


def test_schema_version_constant(dedupe):
    assert dedupe.SCHEMA_VERSION == "1"


@pytest.mark.parametrize(
    "argv",
    [
        ("expand-group", "--seed", "alpha"),
        ("detect", "--seed", "alpha"),
        ("external-callers",),
        ("verify",),
    ],
    ids=["expand-group", "detect", "external-callers", "verify"],
)
def test_subcommand_registered_and_emits_version_shell(dedupe, argv):
    """Each subcommand parses and dispatches to a stub that emits {"version": "1"}."""
    rc, stdout, _ = _run(dedupe, *argv)
    assert rc == 0
    assert json.loads(stdout) == {"version": "1"}


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
#     - contains_safety_marker is the Task 4 PLACEHOLDER (always False here);
#       the real INLINE-MANDATORY/danger detection lands in Task 7.
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
    # Task 4 placeholder: contains_safety_marker is always False (wired in Task 7).
    assert pair.contains_safety_marker is False


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
