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

Stated blind spots -- what these checks do NOT cover:

* Claims phrased without the ``by <name>`` shape ("runs during
  development", "part of the review flow") are not extracted at all.
* A named invoker that is neither a ``skills/`` directory nor a
  ``commands/`` file is skipped, not failed. Claims naming a hook, a
  rule module, or an external mechanism therefore go unchecked.
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

# Orphaned pairs this dispatch did not own. Each entry is real debt, not a
# false positive: the claimant's description names an invoker that does not
# reference it. They are xfail(strict=True), so wiring one up turns the
# suite RED with XPASS and forces the entry's removal -- the registry cannot
# rot into a silent permanent exemption.
KNOWN_ORPHANS: dict[tuple[str, str], str] = {
    ("fractal-thinking", "deep-research"): "outside this dispatch's scope",
    ("fractal-thinking", "fact-checking"): "outside this dispatch's scope",
    ("sharpening-prompts", "reviewing-design-docs"): "outside this dispatch's scope",
    ("sharpening-prompts", "reviewing-impl-plans"): "outside this dispatch's scope",
}


def skill_names() -> set[str]:
    return {p.name for p in SKILLS_DIR.iterdir() if (p / "SKILL.md").is_file()}


def command_names() -> set[str]:
    return {p.stem for p in COMMANDS_DIR.glob("*.md")}


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


def claimed_pairs():
    """Yield (claimant, target, kind, span) for every resolvable claim."""
    skills = skill_names()
    commands = command_names()
    known = skills | commands
    for name in sorted(skills):
        text = claim_surface(
            (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")
        )
        for verb, span in CLAIM_RE.findall(text):
            for target in sorted(resolve_targets(span, known) - {name}):
                yield name, target, verb.lower(), span.strip()


def target_files(target: str) -> list[Path]:
    skill_dir = SKILLS_DIR / target
    if (skill_dir / "SKILL.md").is_file():
        return sorted(skill_dir.rglob("*.md"))
    command = COMMANDS_DIR / f"{target}.md"
    return [command] if command.is_file() else []


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
    for claimant, target in sorted({(c, t) for c, t, _, _ in claimed_pairs()})
]


def test_the_extractor_finds_claims_at_all():
    """A silent extractor and a clean repo look identical."""
    assert PAIRS, "no load-path claims extracted; the regex has rotted"


@pytest.mark.parametrize("claimant,target", PAIRS)
def test_named_invokers_reference_the_skill(claimant, target):
    files = target_files(target)
    if not files:
        pytest.skip(f"{target!r} is neither a skill nor a command; not checkable")
    for path in files:
        if claimant in path.read_text(encoding="utf-8"):
            return
    pytest.fail(
        f"ORPHANED LOAD PATH: skills/{claimant}/SKILL.md claims it is loaded by "
        f"{target!r}, but no file under {files[0].parent.relative_to(REPO)} "
        f"mentions {claimant!r}. The claim is false: {claimant} never reaches "
        f"context via {target}."
    )


@pytest.mark.parametrize("name", sorted(skill_names()), ids=lambda v: v)
def test_automatic_load_claims_name_their_loader(name):
    description = frontmatter_description(
        (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")
    )
    match = AUTOMATIC_RE.search(description)
    if match is None:
        return
    known = skill_names() | command_names()
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
