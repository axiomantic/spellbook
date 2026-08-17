"""Documentation must not outlive its source.

scripts/check-readme-completeness.py asserts that every real skill,
command, and agent is documented. That direction alone cannot notice a
deleted source, because a deleted source is simply absent from the
forward loop. Seven skills and five commands kept shipping README rows,
docs/ pages, and mkdocs nav entries long after their sources were gone.

These tests pin the reverse direction: every documented item must
resolve to a real source file.
"""

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKER = REPO_ROOT / "scripts" / "check-readme-completeness.py"
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
