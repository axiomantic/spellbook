"""Guard: a skill that names its invoker must actually be referenced by it.

A skill whose description says "Required by: code-review" is making a
load-path claim. Nothing in the harness enforces it. If ``code-review``
never mentions the skill, the skill never reaches context, and the failure
is invisible: the claim reads exactly like a wired-up dependency.

Two checks, both narrow on purpose:

``test_named_invokers_reference_the_skill``
    For every extractable "required by X" / "invoked by X" / "loaded by X"
    claim, assert X's own files mention the claiming skill.

``test_automatic_load_claims_name_their_loader``
    A claim of AUTOMATIC loading with no named loader is unfalsifiable
    prose. Require such a description to name an invoker the first check
    can then verify.

``test_claims_name_a_checkable_invoker``
    A "by X" claim whose X resolves to no skill, command, or rule module
    ("invoked by skill improvement workflows", "invoked by other skills
    when they need certainty") names nothing checkable. Such a claim used
    to vanish from extraction entirely, so it read as a wired dependency
    while no check could ever see it. It now fails.

Stated blind spots -- what these checks do NOT cover:

* Claims phrased without the ``by <name>`` shape ("runs during
  development", "part of the review flow") are not extracted at all.
  A claim that DOES use the ``by <name>`` shape is now always visible:
  it either resolves to a checkable target, or fails as unverifiable.
* Resolvable targets are ``skills/`` directories, ``commands/`` files,
  and ``rules/`` modules (matched on the stem with its numeric ordering
  prefix stripped, so ``rules/80-code-quality.md`` answers to
  ``code-quality``). An invoker outside those three trees -- a hook, an
  MCP tool, an external mechanism -- cannot be named inside a ``by``
  claim without failing; state that load path in prose instead.
* Reference is a substring match on the skill name. A mention inside a
  comment, a NOT-for clause, or a deprecation note counts as a
  reference; the check proves mention, not correct wiring.
* Only ``skills/*/SKILL.md`` is scanned as a claimant. Commands and
  agents make load-path claims too and are not checked here.
* Only the ``description`` and ``intro`` frontmatter fields are scanned,
  not the body. Scanning bodies matched illustrative examples inside
  writing-skills (a how-to that quotes the claim form) and could not tell
  them from real claims. A load-path claim buried only in a body is
  therefore invisible to this check.
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO / "skills"
COMMANDS_DIR = REPO / "commands"
RULES_DIR = REPO / "rules"

# "80-code-quality" is addressed as "code-quality"; the digits are ordering.
RULE_STEM_RE = re.compile(r"^\d+-")

# "required by: a, b", "invoked automatically by x", "loaded by y".
# The span stops at sentence end, newline, or a quote so a description
# cannot bleed into the next claim.
CLAIM_RE = re.compile(
    r"\b(required|invoked|loaded)\s+(?:automatically\s+)?by\s*:?\s*([^.\n\"]{1,160})",
    re.IGNORECASE,
)

# A bare assertion of automatic loading, with no "by <name>" to check.
AUTOMATIC_RE = re.compile(
    r"\b(?:invoked|loaded)\s+automatically\b|\bloaded\s+at\s+session\s+start\b",
    re.IGNORECASE,
)

TOKEN_RE = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)+|[a-z]{4,}")

# Orphaned pairs awaiting wiring. Each entry is real debt, not a false
# positive: the claimant's description names an invoker that does not
# reference it. They are xfail(strict=True), so wiring one up turns the
# suite RED with XPASS and forces the entry's removal -- the registry cannot
# rot into a silent permanent exemption.
#
# Empty is the intended steady state: every load-path claim in the tree is
# currently backed by a real reference. An entry belongs here only as a
# deliberate, temporary record of known debt.
KNOWN_ORPHANS: dict[tuple[str, str], str] = {}


def skill_names() -> set[str]:
    return {p.name for p in SKILLS_DIR.iterdir() if (p / "SKILL.md").is_file()}


def command_names() -> set[str]:
    return {p.stem for p in COMMANDS_DIR.glob("*.md")}


def rule_names() -> dict[str, Path]:
    return {RULE_STEM_RE.sub("", p.stem): p for p in RULES_DIR.glob("*.md")}


def known_targets() -> set[str]:
    return skill_names() | command_names() | set(rule_names())


def frontmatter_field(text: str, field: str) -> str:
    """A frontmatter field's raw value, however it is quoted or block-scalared."""
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    block = text[3:end] if end != -1 else text
    match = re.search(rf"^{field}:\s*(.*?)(?=^\w+:|\Z)", block, re.M | re.S)
    return match.group(1) if match else ""


def frontmatter_description(text: str) -> str:
    return frontmatter_field(text, "description")


def resolve_targets(span: str, known: set[str]) -> set[str]:
    return {tok for tok in TOKEN_RE.findall(span.lower()) if tok in known}


def claim_surface(text: str) -> str:
    """The frontmatter fields a load-path claim legitimately lives in."""
    return frontmatter_description(text) + "\n" + frontmatter_field(text, "intro")


def claims():
    """Yield (claimant, span, targets) for every extracted claim.

    ``targets`` is empty when the span names nothing checkable -- the
    unverifiable-claim case, which used to be dropped silently here.
    """
    known = known_targets()
    for name in sorted(skill_names()):
        text = claim_surface(
            (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")
        )
        for _verb, span in CLAIM_RE.findall(text):
            yield name, span.strip(), sorted(resolve_targets(span, known) - {name})


def claimed_pairs():
    """Yield (claimant, target) for every resolvable claim."""
    for name, _span, targets in claims():
        for target in targets:
            yield name, target


def target_files(target: str) -> list[Path]:
    skill_dir = SKILLS_DIR / target
    if (skill_dir / "SKILL.md").is_file():
        return sorted(skill_dir.rglob("*.md"))
    command = COMMANDS_DIR / f"{target}.md"
    if command.is_file():
        return [command]
    rule = rule_names().get(target)
    return [rule] if rule is not None else []


PAIRS = [
    pytest.param(
        claimant,
        target,
        marks=(
            [pytest.mark.xfail(strict=True, reason=KNOWN_ORPHANS[(claimant, target)])]
            if (claimant, target) in KNOWN_ORPHANS
            else []
        ),
        id=f"{claimant}-{target}",
    )
    for claimant, target in sorted(set(claimed_pairs()))
]


def test_the_extractor_finds_claims_at_all():
    """A silent extractor and a clean repo look identical."""
    assert PAIRS, "no load-path claims extracted; the regex has rotted"


@pytest.mark.parametrize("claimant,target", PAIRS)
def test_named_invokers_reference_the_skill(claimant, target):
    files = target_files(target)
    for path in files:
        if claimant in path.read_text(encoding="utf-8"):
            return
    pytest.fail(
        f"ORPHANED LOAD PATH: skills/{claimant}/SKILL.md claims it is loaded by "
        f"{target!r}, but no file under {files[0].parent.relative_to(REPO)} "
        f"mentions {claimant!r}. The claim is false: {claimant} never reaches "
        f"context via {target}."
    )


def test_claims_name_a_checkable_invoker():
    """A "by X" claim naming nothing checkable is unverifiable prose."""
    vague = [(c, s) for c, s, targets in claims() if not targets]
    assert not vague, "UNVERIFIABLE LOAD CLAIM(S):\n" + "\n".join(
        f"  skills/{c}/SKILL.md -- 'by {s}' names no skill, command, or rule "
        f"module. Nothing can check it, so it reads as a wired dependency "
        f"while being unfalsifiable. Name a real invoker, or drop the "
        f"'by ...' phrasing."
        for c, s in vague
    )


@pytest.mark.parametrize("name", sorted(skill_names()), ids=lambda v: v)
def test_automatic_load_claims_name_their_loader(name):
    description = frontmatter_description(
        (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")
    )
    match = AUTOMATIC_RE.search(description)
    if match is None:
        return
    known = known_targets()
    named = {
        target
        for _, span in CLAIM_RE.findall(description)
        for target in resolve_targets(span, known) - {name}
    }
    assert named, (
        f"UNVERIFIABLE LOAD CLAIM: skills/{name}/SKILL.md describes itself as "
        f"{match.group(0)!r} but names no invoker. Nothing loads a skill "
        f"automatically on its own say-so. Either name the skill or command "
        f"that loads it (so the reference can be checked), or state the real "
        f"load path."
    )
