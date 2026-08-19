"""Documentation must not outlive its source.

scripts/check-readme-completeness.py asserts that every real skill,
command, and agent is documented. That direction alone cannot notice a
deleted source, because a deleted source is simply absent from the
forward loop. Seven skills and five commands kept shipping README rows,
docs/ pages, and mkdocs nav entries long after their sources were gone.

These tests pin the reverse direction: every documented item must
resolve to a real source file.
"""

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKER = REPO_ROOT / "scripts" / "check-readme-completeness.py"

import corpus_trees
# A copy manifest for the scratch repo, not a corpus membership -- it is
# "what the checker needs to run", so it is deliberately not corpus_trees.
SOURCE_DIRS = ("scripts", "skills", "commands", "agents", "rules", "docs")


def _scratch_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    for name in SOURCE_DIRS:
        shutil.copytree(REPO_ROOT / name, root / name)
    for name in ("README.md", "mkdocs.yml"):
        shutil.copy2(REPO_ROOT / name, root / name)
    return root


def _run(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(root / "scripts" / "check-readme-completeness.py")],
        capture_output=True,
        text=True,
        cwd=str(root),
        timeout=300,
    )


def _load_checker_module():
    """Import the checker by path; its filename is not a valid module name."""
    spec = importlib.util.spec_from_file_location("check_readme_completeness", CHECKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_repository_documents_nothing_phantom():
    result = subprocess.run(
        [sys.executable, str(CHECKER)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=300,
    )
    assert result.returncode == 0, f"{result.stdout}{result.stderr}"


def test_phantom_readme_table_entry_is_named(tmp_path):
    root = _scratch_repo(tmp_path)
    readme = root / "README.md"
    text = readme.read_text(encoding="utf-8")
    marker = "| **Session** | "
    assert marker in text, "fixture expects a Session row in the Skills table"
    readme.write_text(
        text.replace(marker, marker + "[ghost-skill], ", 1), encoding="utf-8"
    )

    result = _run(root)
    assert result.returncode == 1, result.stdout
    assert "ghost-skill" in result.stdout, result.stdout


def test_phantom_link_definition_is_named(tmp_path):
    root = _scratch_repo(tmp_path)
    readme = root / "README.md"
    text = readme.read_text(encoding="utf-8")
    readme.write_text(
        text
        + "\n[ghost-skill]: https://axiomantic.github.io/spellbook/latest/skills/ghost-skill/\n",
        encoding="utf-8",
    )

    result = _run(root)
    assert result.returncode == 1, result.stdout
    assert "[ghost-skill]" in result.stdout, result.stdout


def test_phantom_mkdocs_nav_entry_is_named(tmp_path):
    root = _scratch_repo(tmp_path)
    mkdocs = root / "mkdocs.yml"
    text = mkdocs.read_text(encoding="utf-8")
    marker = "      - skills/develop.md\n"
    assert marker in text, "fixture expects skills/develop.md in the nav"
    mkdocs.write_text(
        text.replace(marker, marker + "      - skills/ghost-skill.md\n", 1),
        encoding="utf-8",
    )

    result = _run(root)
    assert result.returncode == 1, result.stdout
    assert "skills/ghost-skill.md" in result.stdout, result.stdout


def test_orphan_docs_page_is_named(tmp_path):
    root = _scratch_repo(tmp_path)
    (root / "docs" / "commands" / "ghost-command.md").write_text(
        "# ghost\n", encoding="utf-8"
    )

    result = _run(root)
    assert result.returncode == 1, result.stdout
    assert "docs/commands/ghost-command.md" in result.stdout, result.stdout


def test_orphan_rules_docs_page_is_named(tmp_path):
    """docs/rules/ is generated, so it can rot exactly like the other trees.

    README has no Rules section, so the README-table checks correctly skip
    rules. The orphan sweep reads docs/, not README, so that exclusion never
    applied to it -- and 20 generated pages sat with no reverse-direction
    guard at all.
    """
    root = _scratch_repo(tmp_path)
    (root / "docs" / "rules" / "99-ghost-rule.md").write_text(
        "# ghost\n", encoding="utf-8"
    )

    result = _run(root)
    assert result.returncode == 1, result.stdout
    assert "docs/rules/99-ghost-rule.md" in result.stdout, result.stdout


def test_real_rules_pages_are_not_orphans():
    """The sweep must not report the 20 legitimate generated rule pages."""
    result = subprocess.run(
        [sys.executable, str(CHECKER)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=300,
    )
    assert "docs/rules/" not in result.stdout, result.stdout
    assert result.returncode == 0, f"{result.stdout}{result.stderr}"


def test_phantom_rules_nav_entry_is_named(tmp_path):
    """A nav entry for a deleted rule must be reported.

    Without this, deleting a rule leaves a stale nav entry, and once
    generate_docs.py drops the docs page the orphan sweep cannot see it
    either -- so nothing reports it, ever.
    """
    root = _scratch_repo(tmp_path)
    mkdocs = root / "mkdocs.yml"
    text = mkdocs.read_text(encoding="utf-8")
    marker = "      - rules/00-core.md\n"
    assert marker in text, "fixture expects rules/00-core.md in the nav"
    mkdocs.write_text(
        text.replace(marker, marker + "      - rules/99-ghost-rule.md\n", 1),
        encoding="utf-8",
    )

    result = _run(root)
    assert result.returncode == 1, result.stdout
    assert "rules/99-ghost-rule.md" in result.stdout, result.stdout


def test_rule_missing_from_nav_is_named(tmp_path):
    """A real rule with no nav entry must be reported."""
    root = _scratch_repo(tmp_path)
    mkdocs = root / "mkdocs.yml"
    text = mkdocs.read_text(encoding="utf-8")
    marker = "      - rules/00-core.md\n"
    assert marker in text, "fixture expects rules/00-core.md in the nav"
    mkdocs.write_text(text.replace(marker, "", 1), encoding="utf-8")

    result = _run(root)
    assert result.returncode == 1, result.stdout
    assert "mkdocs.yml nav missing: rules/00-core.md" in result.stdout, result.stdout


def test_nav_entry_regex_tracks_documented_trees():
    """The nav regex alternation must not drift from DOCUMENTED_TREES."""
    checker = _load_checker_module()
    for tree in corpus_trees.DOCUMENTED_TREES:
        assert checker.NAV_ENTRY_RE.findall(f"{tree}/probe.md") == [(tree, "probe")]
    assert checker.NAV_ENTRY_RE.findall("patterns/probe.md") == []


def test_duplicated_link_definition_is_reported(tmp_path):
    """A duplicated definition is silent in markdown and hid real drift.

    The README carried five duplicated definitions, two of them for
    items whose sources no longer existed. Markdown resolves the first
    and ignores the rest, so nothing rendered wrong.
    """
    root = _scratch_repo(tmp_path)
    readme = root / "README.md"
    text = readme.read_text(encoding="utf-8")
    readme.write_text(
        text
        + "\n[develop]: https://axiomantic.github.io/spellbook/latest/skills/develop/\n",
        encoding="utf-8",
    )

    result = _run(root)
    assert result.returncode == 1, result.stdout
    assert "duplicated" in result.stdout, result.stdout
    assert "[develop]" in result.stdout, result.stdout


def test_subdirectory_commands_are_not_phantoms():
    """commands/<name>/<name>.md is a real command, not a missing file.

    A reverse check that knew only the flat commands/<name>.md shape
    would report systematic-debugging and scientific-debugging as
    phantoms and invite their deletion.
    """
    for name in ("systematic-debugging", "scientific-debugging"):
        assert (REPO_ROOT / "commands" / name / f"{name}.md").exists()
        assert (REPO_ROOT / "docs" / "commands" / f"{name}.md").exists()
