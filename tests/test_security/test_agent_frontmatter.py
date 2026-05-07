"""Schema validation for agents/ directory.

Validates three distinct contracts:
  1. NEW narrowing-role agents (the 9 listed in EXPECTED_NEW_AGENTS): each
     has `tools:` frontmatter matching the canonical table, a `model:`
     field, `name:` matching the filename, and a body with exactly the
     5 required headings in canonical order.
  2. EXISTING 7 agents: byte-identical SHA-256 snapshot. Guards against
     accidental modification of the existing 7 during WI-5 work.
  3. EXEMPT existing agents (`code-reviewer`, `justice-resolver`): these
     two were authored before the `tools:` frontmatter convention was
     established, and bringing them into compliance is tracked as a
     separate cleanup task. The byte-snapshot test still applies; the
     tools-presence check does not.

Snapshot regeneration (only after intentional edits to the existing 7):
    AGENT_SNAPSHOT_REGEN=1 uv run pytest \
        tests/test_security/test_agent_frontmatter.py::test_regenerate_snapshots_when_requested
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "agents"
SNAPSHOT_PATH = Path(__file__).resolve().parent / "agent_snapshots.json"

# Canonical tools mapping for the 9 NEW narrowing-role agents.
# Source of truth: WI-5 brief §B (2026-05-06-wi-5-brief.md, lines 50-60).
# Compared as comma-split sets normalized via str.strip().
EXPECTED_NEW_AGENTS: dict[str, str] = {
    "web-researcher": "WebFetch, WebSearch, Read",
    "implementer": "Edit, Write, Read, Grep, Glob, Bash",
    "git-committer": "Bash, Read",
    "git-pusher": "Bash, Read",
    "pr-creator": "Bash, Read",
    "pr-merger": "Bash, Read",
    "jira-reader": "Read",
    "jira-mutator": "Read",
    "test-runner": "Bash, Read, Grep",
}

# Existing 7 agents to byte-snapshot.
EXISTING_AGENTS: frozenset[str] = frozenset({
    "chariot-implementer",
    "code-reviewer",
    "emperor-governor",
    "hierophant-distiller",
    "justice-resolver",
    "lovers-integrator",
    "queen-affective",
})

# Existing agents that legitimately omit `tools:` frontmatter:
# code-reviewer.md and justice-resolver.md were authored before the
# `tools:` frontmatter convention was established, and bringing them
# into compliance is tracked as a separate cleanup task. The body
# byte-snapshot still applies; only the tools-presence test exempts these.
TOOLS_EXEMPT_EXISTING: frozenset[str] = frozenset({
    "code-reviewer",
    "justice-resolver",
})

REQUIRED_BODY_SECTIONS: tuple[str, ...] = (
    "## Purpose",
    "## Tools",
    "## Output Schema",
    "## Guardrails",
    "## Constraints",
)


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body). Empty dict if no frontmatter."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    fm = yaml.safe_load(text[4:end])
    return (fm or {}), text[end + len("\n---\n"):]


def _existing_new_agents() -> list[str]:
    """The subset of EXPECTED_NEW_AGENTS that currently exists on disk.

    Task B ships only `implementer.md`; Task C adds the rest. The schema
    tests parametrize over whichever files currently exist, so each new
    agent file authored later is automatically validated."""
    return sorted(
        name for name in EXPECTED_NEW_AGENTS
        if (AGENTS_DIR / f"{name}.md").exists()
    )


def _tokenize_tools(value: str) -> set[str]:
    """Split a comma-separated `tools:` string into a normalized token set."""
    return {token.strip() for token in value.split(",") if token.strip()}


# ---------------------------------------------------------------------------
# NEW-AGENT validation (parametrized over existing files)
# ---------------------------------------------------------------------------


def test_canonical_implementer_exists():
    """Task B canonical seed: implementer.md MUST exist before Task C
    fans out the remaining 8 agents."""
    assert (AGENTS_DIR / "implementer.md").exists(), (
        "agents/implementer.md missing; Task B canonical seed not yet authored"
    )


@pytest.mark.parametrize("agent_name", _existing_new_agents())
def test_new_agent_has_canonical_tools_frontmatter(agent_name: str):
    path = AGENTS_DIR / f"{agent_name}.md"
    fm, _ = _split_frontmatter(path.read_text(encoding="utf-8"))
    assert "tools" in fm, f"{agent_name}: missing `tools` frontmatter"
    expected = _tokenize_tools(EXPECTED_NEW_AGENTS[agent_name])
    actual = _tokenize_tools(fm["tools"])
    assert actual == expected, (
        f"{agent_name}: tools mismatch. expected={sorted(expected)}, "
        f"actual={sorted(actual)}"
    )


@pytest.mark.parametrize("agent_name", _existing_new_agents())
def test_new_agent_has_required_body_sections_in_order(agent_name: str):
    path = AGENTS_DIR / f"{agent_name}.md"
    _, body = _split_frontmatter(path.read_text(encoding="utf-8"))
    # Match each heading as a full line (flanked by newlines) so that a
    # literal "## Purpose" appearing inside a fenced code block cannot
    # false-match the section-ordering check. Prepending "\n" lets the
    # very first heading match even when it sits at the top of the body.
    search_body = "\n" + body
    missing = [
        h for h in REQUIRED_BODY_SECTIONS if f"\n{h}\n" not in search_body
    ]
    assert not missing, f"{agent_name}: missing headings {missing}"
    indices = [search_body.index(f"\n{h}\n") for h in REQUIRED_BODY_SECTIONS]
    assert indices == sorted(indices), (
        f"{agent_name}: section order wrong. expected order "
        f"{list(REQUIRED_BODY_SECTIONS)}, indices {indices}"
    )


@pytest.mark.parametrize("agent_name", _existing_new_agents())
def test_new_agent_has_model_inherit(agent_name: str):
    path = AGENTS_DIR / f"{agent_name}.md"
    fm, _ = _split_frontmatter(path.read_text(encoding="utf-8"))
    assert fm.get("model") == "inherit", (
        f"{agent_name}: expected `model: inherit`, got {fm.get('model')!r}"
    )


@pytest.mark.parametrize("agent_name", _existing_new_agents())
def test_new_agent_name_matches_filename(agent_name: str):
    path = AGENTS_DIR / f"{agent_name}.md"
    fm, _ = _split_frontmatter(path.read_text(encoding="utf-8"))
    assert fm.get("name") == agent_name, (
        f"{agent_name}: name field {fm.get('name')!r} != filename basename"
    )


@pytest.mark.parametrize("agent_name", _existing_new_agents())
def test_new_agent_has_description(agent_name: str):
    path = AGENTS_DIR / f"{agent_name}.md"
    fm, _ = _split_frontmatter(path.read_text(encoding="utf-8"))
    description = fm.get("description")
    assert isinstance(description, str) and description.strip(), (
        f"{agent_name}: missing or empty `description` frontmatter"
    )


# ---------------------------------------------------------------------------
# EXISTING-AGENT byte-identical snapshot
# ---------------------------------------------------------------------------


def _current_snapshots() -> dict[str, str]:
    return {
        name: hashlib.sha256(
            (AGENTS_DIR / f"{name}.md").read_bytes()
        ).hexdigest()
        for name in sorted(EXISTING_AGENTS)
    }


def _load_committed_snapshots() -> dict[str, str]:
    if not SNAPSHOT_PATH.exists():
        return {}
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize("agent_name", sorted(EXISTING_AGENTS))
def test_existing_agent_byte_identical_to_snapshot(agent_name: str):
    if os.environ.get("AGENT_SNAPSHOT_REGEN"):
        pytest.skip("Snapshot regeneration mode")
    committed = _load_committed_snapshots()
    if not committed:
        pytest.fail(
            f"Snapshot file missing at {SNAPSHOT_PATH}. Generate with "
            "AGENT_SNAPSHOT_REGEN=1 uv run pytest "
            "tests/test_security/test_agent_frontmatter.py::"
            "test_regenerate_snapshots_when_requested"
        )
    assert agent_name in committed, (
        f"{agent_name}: missing from snapshot file. Regenerate snapshot."
    )
    current_sha = hashlib.sha256(
        (AGENTS_DIR / f"{agent_name}.md").read_bytes()
    ).hexdigest()
    assert committed[agent_name] == current_sha, (
        f"{agent_name}.md was modified. expected SHA {committed[agent_name]}, "
        f"got {current_sha}. If the change was intentional, regenerate the "
        f"snapshot via AGENT_SNAPSHOT_REGEN=1."
    )


def test_snapshot_covers_all_existing_agents():
    """Snapshot file must enumerate every name in EXISTING_AGENTS exactly."""
    if os.environ.get("AGENT_SNAPSHOT_REGEN"):
        pytest.skip("Snapshot regeneration mode")
    committed = _load_committed_snapshots()
    if not committed:
        pytest.fail(
            f"Snapshot file missing at {SNAPSHOT_PATH}. Regenerate via "
            "AGENT_SNAPSHOT_REGEN=1."
        )
    assert set(committed.keys()) == set(EXISTING_AGENTS), (
        f"snapshot keys {sorted(committed.keys())} != "
        f"EXISTING_AGENTS {sorted(EXISTING_AGENTS)}"
    )


def test_regenerate_snapshots_when_requested():
    """Writes the canonical snapshot file when AGENT_SNAPSHOT_REGEN=1.

    This is the only test that writes; it skips otherwise."""
    if not os.environ.get("AGENT_SNAPSHOT_REGEN"):
        pytest.skip("Set AGENT_SNAPSHOT_REGEN=1 to regenerate the snapshot")
    SNAPSHOT_PATH.write_text(
        json.dumps(_current_snapshots(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_tools_exempt_existing_agents_lack_tools_frontmatter():
    """Document the exemption: code-reviewer and justice-resolver
    legitimately omit `tools:` because they predate the convention.

    If this test fails because the two exempt agents now have `tools:`,
    the cleanup is:

      1. Regenerate `agent_snapshots.json` (those two files have changed
         bytes, so the byte-snapshot test will also fail):

             AGENT_SNAPSHOT_REGEN=1 uv run pytest \\
                 tests/test_security/test_agent_frontmatter.py::test_regenerate_snapshots_when_requested

      2. Remove the agent name(s) from TOOLS_EXEMPT_EXISTING.
      3. Delete this test."""
    for agent_name in sorted(TOOLS_EXEMPT_EXISTING):
        fm, _ = _split_frontmatter(
            (AGENTS_DIR / f"{agent_name}.md").read_text(encoding="utf-8")
        )
        assert "tools" not in fm, (
            f"{agent_name}: now has `tools:` frontmatter. Remove from "
            "TOOLS_EXEMPT_EXISTING and delete this test."
        )
