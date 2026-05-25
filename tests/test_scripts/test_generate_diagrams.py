"""Tests for scripts/generate_diagrams.py pure helpers.

Covers the two bug fixes:

1. ``item_label`` — derives an unambiguous, repo-relative label for a
   discovered source item, so progress lines no longer print bare
   filenames like ``SKILL.md`` (every skill shares that filename).
2. ``_normalize_classification`` — guards the classifier's parsed
   LLM response against ``None``/empty/unrecognized values, returning
   the REGENERATE fail-safe default WITHOUT raising (the original code
   path raised ``TypeError: 'NoneType' object is not iterable`` when the
   parsed response field was ``None``).

The full LLM pipeline is not exercised here (it requires an API). Only
the pure helpers are tested by calling them directly with constructed or
``None`` inputs.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "generate_diagrams.py"
SCRIPTS_DIR = REPO_ROOT / "scripts"


# Private sys.modules name for the under-test copy of generate_diagrams. Loading
# under this unique name (instead of the bare ``generate_diagrams``) avoids
# clobbering the shared ``sys.modules["generate_diagrams"]`` entry that
# tests/unit/test_diagram_update.py imports and tripwire-mocks by spec string
# ("generate_diagrams:_get_repo_root"). Overwriting the shared entry here would
# give that sibling test a different module object, so its mock patch would land
# on the wrong identity and the real _get_repo_root would run.
_UNDER_TEST_MODULE_NAME = "generate_diagrams_under_test"


def _load_module():
    """Load generate_diagrams from its file path under a unique private name.

    The module lives in scripts/ (not a package) and imports sibling
    ``diagram_config`` by bare name, so scripts/ must be on sys.path. It is
    registered in ``sys.modules`` under ``_UNDER_TEST_MODULE_NAME`` rather than
    the bare ``generate_diagrams`` so the shared entry is never disturbed.
    """
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    spec = importlib.util.spec_from_file_location(_UNDER_TEST_MODULE_NAME, SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    # Register under the unique private name so exec_module can resolve any
    # self-referential imports without overwriting sys.modules["generate_diagrams"].
    sys.modules[_UNDER_TEST_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gd():
    return _load_module()


def _make_item(gd, *, name, kind, source_rel, diagram_rel):
    """Build a SourceItem rooted at the real REPO_ROOT for label derivation."""
    return gd.SourceItem(
        name=name,
        kind=kind,
        source_path=REPO_ROOT / source_rel,
        diagram_path=REPO_ROOT / diagram_rel,
        mandatory=True,
    )


# ---------------------------------------------------------------------------
# Bug 1: item_label — unambiguous, repo-relative progress labels
# ---------------------------------------------------------------------------


def test_item_label_skill_includes_skill_dir(gd):
    item = _make_item(
        gd,
        name="develop",
        kind="skill",
        source_rel="skills/develop/SKILL.md",
        diagram_rel="docs/diagrams/skills/develop.md",
    )
    assert gd.item_label(item) == "skills/develop/SKILL.md"


def test_item_label_command_includes_commands_dir(gd):
    item = _make_item(
        gd,
        name="feature-config",
        kind="command",
        source_rel="commands/feature-config.md",
        diagram_rel="docs/diagrams/commands/feature-config.md",
    )
    assert gd.item_label(item) == "commands/feature-config.md"


def test_item_label_agent_includes_agents_dir(gd):
    item = _make_item(
        gd,
        name="implementer",
        kind="agent",
        source_rel="agents/implementer.md",
        diagram_rel="docs/diagrams/agents/implementer.md",
    )
    assert gd.item_label(item) == "agents/implementer.md"


def test_item_label_disambiguates_two_skills_sharing_filename(gd):
    """Two different skills both have a SKILL.md; labels must differ."""
    a = _make_item(
        gd,
        name="develop",
        kind="skill",
        source_rel="skills/develop/SKILL.md",
        diagram_rel="docs/diagrams/skills/develop.md",
    )
    b = _make_item(
        gd,
        name="executing-plans",
        kind="skill",
        source_rel="skills/executing-plans/SKILL.md",
        diagram_rel="docs/diagrams/skills/executing-plans.md",
    )
    assert gd.item_label(a) == "skills/develop/SKILL.md"
    assert gd.item_label(b) == "skills/executing-plans/SKILL.md"
    assert gd.item_label(a) != gd.item_label(b)


def test_item_label_disambiguates_skill_and_command_sharing_name(gd):
    """A skill and a command can share the same ``item.name`` (e.g. ``canvas``).

    Progress lines that print bare ``item.name`` without the kind would be
    ambiguous across these two items; the repo-relative label keeps them
    distinct because the leading ``skills/`` vs ``commands/`` segment differs.
    """
    skill = _make_item(
        gd,
        name="canvas",
        kind="skill",
        source_rel="skills/canvas/SKILL.md",
        diagram_rel="docs/diagrams/skills/canvas.md",
    )
    command = _make_item(
        gd,
        name="canvas",
        kind="command",
        source_rel="commands/canvas.md",
        diagram_rel="docs/diagrams/commands/canvas.md",
    )
    assert gd.item_label(skill) == "skills/canvas/SKILL.md"
    assert gd.item_label(command) == "commands/canvas.md"
    assert gd.item_label(skill) != gd.item_label(command)


# ---------------------------------------------------------------------------
# Bug 2: _normalize_classification — None-guard with REGENERATE fail-safe
# ---------------------------------------------------------------------------


def test_normalize_classification_none_returns_regenerate(gd):
    assert gd._normalize_classification(None) == "REGENERATE"


def test_normalize_classification_empty_returns_regenerate(gd):
    assert gd._normalize_classification("") == "REGENERATE"


def test_normalize_classification_whitespace_returns_regenerate(gd):
    assert gd._normalize_classification("   \n  ") == "REGENERATE"


def test_normalize_classification_unrecognized_returns_regenerate(gd):
    assert gd._normalize_classification("maybe later") == "REGENERATE"


def test_normalize_classification_non_str_returns_regenerate(gd):
    # A truthy non-str (e.g. a dict or list) must not AttributeError on
    # .strip(); it degrades to the REGENERATE fail-safe.
    assert gd._normalize_classification({"unexpected": "shape"}) == "REGENERATE"
    assert gd._normalize_classification(["REGENERATE"]) == "REGENERATE"


def test_normalize_classification_preserves_stamp(gd):
    assert gd._normalize_classification("stamp") == "STAMP"


def test_normalize_classification_preserves_patch_with_whitespace(gd):
    assert gd._normalize_classification("  PATCH\n") == "PATCH"


def test_normalize_classification_preserves_regenerate(gd):
    assert gd._normalize_classification("REGENERATE") == "REGENERATE"
