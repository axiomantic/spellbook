"""``pythonpath = ["scripts"]`` puts every script module name on ``sys.path``.

``pyproject.toml`` prepends ``scripts/`` to ``sys.path`` for the whole test
session so that a test importing a gate checker can write an ordinary top-level
import. The cost is that every importable name in ``scripts/`` becomes a
candidate answer for every ``import`` executed under pytest. A future
``scripts/typing.py`` or ``scripts/click.py`` would answer ``import typing`` or
``import click`` for the entire suite, and nothing would report an error --
tests would simply run against the wrong module, or fail somewhere far from the
cause.

This module mechanizes that admission. The shadowing relation is between IMPORT
names, so those are what it compares:

* ``sys.stdlib_module_names`` is already a set of import names.
* For installed third-party code it uses ``importlib.metadata`` ->
  ``packages_distributions()``, whose KEYS are top-level import names, rather
  than ``distributions()``, whose names are DISTRIBUTION names. The two differ
  (the ``pytest-asyncio`` distribution imports as ``pytest_asyncio``), and only
  the import name can be typed in an ``import`` statement, so only the import
  name can be shadowed. Comparing distribution names would both miss real
  collisions and invent false ones.

The floor test is the anti-no-op guard, following the house convention in
``tests/scripts/test_reference_resolution.py::test_row_extracts_at_least_its_floor``:
a derivation that returns an empty set is disjoint from everything and would
pass both assertions while checking nothing.
"""

import sys
from importlib.metadata import packages_distributions
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"

# One unit is one ``scripts/*.py`` file whose stem is a valid Python
# identifier, i.e. a file reachable by a plain ``import <stem>``. Hyphenated
# scripts (``branch-context.py``) cannot be named in an import statement and so
# cannot shadow anything. Derived at the time of writing with:
#   uv run python -c "from pathlib import Path; \
#     print(sum(1 for p in Path('scripts').glob('*.py') if p.stem.isidentifier()))"
# which reported 17. The floor sits below that so ordinary deletion of a script
# does not turn the suite red, while a derivation that collapses toward zero
# does.
MODULE_NAME_FLOOR = 15


def script_module_names(scripts_dir: Path) -> set[str]:
    """Names that ``scripts_dir`` on ``sys.path`` makes importable."""
    return {p.stem for p in scripts_dir.glob("*.py") if p.stem.isidentifier()}


def installed_import_names() -> set[str]:
    """Top-level import names provided by installed distributions."""
    return set(packages_distributions())


def test_script_module_names_meet_their_floor():
    """A derivation that finds nothing is disjoint from everything."""
    names = script_module_names(SCRIPTS_DIR)
    assert len(names) >= MODULE_NAME_FLOOR, (
        f"Derived {len(names)} importable script module name(s) from "
        f"{SCRIPTS_DIR}, below the floor of {MODULE_NAME_FLOOR}. Either the "
        f"scripts directory moved or shrank, or this derivation broke. An "
        f"empty set passes every disjointness assertion below while checking "
        f"nothing."
    )


def test_script_module_names_do_not_shadow_the_stdlib():
    collisions = script_module_names(SCRIPTS_DIR) & sys.stdlib_module_names
    assert not collisions, (
        f"scripts/ contains module name(s) that shadow the standard library "
        f"for every test in the suite: {sorted(collisions)}. "
        f"pyproject.toml puts scripts/ on sys.path, so `import "
        f"{sorted(collisions)[0]}` would resolve to the script. Rename the "
        f"script."
    )


def test_script_module_names_do_not_shadow_installed_distributions():
    collisions = script_module_names(SCRIPTS_DIR) & installed_import_names()
    assert not collisions, (
        f"scripts/ contains module name(s) that shadow an installed "
        f"dependency's import name for every test in the suite: "
        f"{sorted(collisions)}. pyproject.toml puts scripts/ on sys.path, so "
        f"`import {sorted(collisions)[0]}` would resolve to the script rather "
        f"than to the installed package. Rename the script."
    )


def test_guard_names_a_planted_stdlib_collision(tmp_path):
    """RED proof: the stdlib check must actually catch a collision.

    Planted in a scratch directory, never in the real tree.
    """
    (tmp_path / "typing.py").write_text("")
    (tmp_path / "docs_config.py").write_text("")
    assert script_module_names(tmp_path) & sys.stdlib_module_names == {"typing"}


def test_guard_names_a_planted_distribution_collision(tmp_path):
    """RED proof: the installed-distribution check must catch a collision.

    ``pytest`` is a real installed dependency of this project and its
    distribution name and import name happen to coincide; ``pytest_asyncio``
    is the case where they do not, and it is the import name that must match.
    """
    (tmp_path / "pytest.py").write_text("")
    (tmp_path / "pytest_asyncio.py").write_text("")
    (tmp_path / "docs_config.py").write_text("")
    collisions = script_module_names(tmp_path) & installed_import_names()
    assert collisions == {"pytest", "pytest_asyncio"}


def test_hyphenated_scripts_are_excluded(tmp_path):
    """A hyphenated file cannot be named in an import statement."""
    (tmp_path / "branch-context.py").write_text("")
    assert script_module_names(tmp_path) == set()
