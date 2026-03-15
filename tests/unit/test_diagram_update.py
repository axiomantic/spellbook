"""Tests for smart update flow in generate_diagrams.py.

Tests classify_change(), patch_diagram(), --force-regen flag,
and integration into the main processing loop.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

# Add project root so we can import generate_diagrams as a module
WORKTREE_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(WORKTREE_ROOT / "scripts"))

import generate_diagrams


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_source_item(
    tmp_path: Path,
    name: str = "test-skill",
    kind: str = "skill",
    mandatory: bool = True,
) -> generate_diagrams.SourceItem:
    """Create a SourceItem backed by real temp files."""
    source_path = tmp_path / f"{name}.md"
    source_path.write_text(f"# {name}\nSome content\n", encoding="utf-8")
    diagram_path = tmp_path / "diagrams" / f"{name}.md"
    diagram_path.parent.mkdir(parents=True, exist_ok=True)
    return generate_diagrams.SourceItem(
        name=name,
        kind=kind,
        source_path=source_path,
        diagram_path=diagram_path,
        mandatory=mandatory,
    )


def write_diagram_with_meta(item: generate_diagrams.SourceItem, source_hash: str) -> None:
    """Write a diagram file with a valid metadata header."""
    meta = {
        "source": str(item.source_path),
        "source_hash": f"sha256:{source_hash}",
        "generated_at": "2026-03-14T00:00:00Z",
        "generator": "generate_diagrams.py",
    }
    meta_line = f"<!-- diagram-meta: {json.dumps(meta)} -->"
    content = f"{meta_line}\n# Diagram: {item.name}\n\n```mermaid\ngraph TD\n  A --> B\n```\n"
    item.diagram_path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests: get_source_diff
# ---------------------------------------------------------------------------


class TestGetSourceDiff:
    """Tests for the get_source_diff function."""

    def test_returns_uncommitted_diff_when_available(self, tmp_path: Path) -> None:
        """get_source_diff returns git diff HEAD output when non-empty."""
        source_path = tmp_path / "skill.md"
        source_path.write_text("content", encoding="utf-8")

        diff_text = "- old line\n+ new line"
        git_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=diff_text, stderr=""
        )

        with (
            mock.patch("generate_diagrams.REPO_ROOT", tmp_path),
            mock.patch("generate_diagrams.subprocess.run", return_value=git_result) as mock_run,
        ):
            result = generate_diagrams.get_source_diff(source_path)

        assert result == diff_text
        assert mock_run.call_count == 1

    def test_falls_back_to_head_tilde_1_when_head_empty(self, tmp_path: Path) -> None:
        """get_source_diff tries HEAD~1 when HEAD diff is empty."""
        source_path = tmp_path / "skill.md"
        source_path.write_text("content", encoding="utf-8")

        empty_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        history_diff = "- old\n+ new"
        history_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=history_diff, stderr=""
        )

        with (
            mock.patch("generate_diagrams.REPO_ROOT", tmp_path),
            mock.patch("generate_diagrams.subprocess.run") as mock_run,
        ):
            mock_run.side_effect = [empty_result, history_result]
            result = generate_diagrams.get_source_diff(source_path)

        assert result == history_diff
        assert mock_run.call_count == 2

    def test_returns_empty_when_no_diff_available(self, tmp_path: Path) -> None:
        """get_source_diff returns empty string when both diffs are empty."""
        source_path = tmp_path / "skill.md"
        source_path.write_text("content", encoding="utf-8")

        empty_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        with (
            mock.patch("generate_diagrams.REPO_ROOT", tmp_path),
            mock.patch("generate_diagrams.subprocess.run", return_value=empty_result),
        ):
            result = generate_diagrams.get_source_diff(source_path)

        assert result == ""


# ---------------------------------------------------------------------------
# Tests: classify_change
# ---------------------------------------------------------------------------


class TestClassifyChange:
    """Tests for the classify_change function."""

    def test_returns_stamp_when_claude_says_stamp(self, tmp_path: Path) -> None:
        """classify_change returns 'STAMP' when Claude classifies as non-structural."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        claude_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="STAMP", stderr=""
        )

        with (
            mock.patch("generate_diagrams.get_source_diff", return_value="- old\n+ new"),
            mock.patch("generate_diagrams.subprocess.run", return_value=claude_result),
        ):
            classification = generate_diagrams.classify_change(
                item.source_path, item.diagram_path
            )

        assert classification == "STAMP"

    def test_returns_patch_when_claude_says_patch(self, tmp_path: Path) -> None:
        """classify_change returns 'PATCH' when Claude classifies as small structural."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        claude_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="PATCH\n", stderr=""
        )

        with (
            mock.patch("generate_diagrams.get_source_diff", return_value="- old step\n+ new step"),
            mock.patch("generate_diagrams.subprocess.run", return_value=claude_result),
        ):
            classification = generate_diagrams.classify_change(
                item.source_path, item.diagram_path
            )

        assert classification == "PATCH"

    def test_returns_regenerate_when_claude_says_regenerate(self, tmp_path: Path) -> None:
        """classify_change returns 'REGENERATE' when Claude classifies as major restructure."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        claude_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="REGENERATE", stderr=""
        )

        with (
            mock.patch("generate_diagrams.get_source_diff", return_value="massive rewrite"),
            mock.patch("generate_diagrams.subprocess.run", return_value=claude_result),
        ):
            classification = generate_diagrams.classify_change(
                item.source_path, item.diagram_path
            )

        assert classification == "REGENERATE"

    def test_falls_back_to_regenerate_on_claude_error(self, tmp_path: Path) -> None:
        """classify_change returns 'REGENERATE' when Claude subprocess fails."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        claude_result = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="error"
        )

        with (
            mock.patch("generate_diagrams.get_source_diff", return_value="some diff"),
            mock.patch("generate_diagrams.subprocess.run", return_value=claude_result),
        ):
            classification = generate_diagrams.classify_change(
                item.source_path, item.diagram_path
            )

        assert classification == "REGENERATE"

    def test_falls_back_to_regenerate_on_timeout(self, tmp_path: Path) -> None:
        """classify_change returns 'REGENERATE' when Claude times out."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        with (
            mock.patch("generate_diagrams.get_source_diff", return_value="some diff"),
            mock.patch(
                "generate_diagrams.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=60),
            ),
        ):
            classification = generate_diagrams.classify_change(
                item.source_path, item.diagram_path
            )

        assert classification == "REGENERATE"

    def test_falls_back_to_regenerate_on_unexpected_output(self, tmp_path: Path) -> None:
        """classify_change returns 'REGENERATE' when Claude returns gibberish."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        claude_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="I think you should regenerate this", stderr=""
        )

        with (
            mock.patch("generate_diagrams.get_source_diff", return_value="some diff"),
            mock.patch("generate_diagrams.subprocess.run", return_value=claude_result),
        ):
            classification = generate_diagrams.classify_change(
                item.source_path, item.diagram_path
            )

        assert classification == "REGENERATE"

    def test_falls_back_to_regenerate_when_no_diff_available(self, tmp_path: Path) -> None:
        """When get_source_diff returns empty, falls back to REGENERATE."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        with mock.patch("generate_diagrams.get_source_diff", return_value=""):
            classification = generate_diagrams.classify_change(
                item.source_path, item.diagram_path
            )

        assert classification == "REGENERATE"

    def test_sends_classification_prompt_with_diff(self, tmp_path: Path) -> None:
        """classify_change sends the diff embedded in the classification prompt to Claude."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        the_diff = "- removed line\n+ added line"
        claude_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="STAMP", stderr=""
        )

        with (
            mock.patch("generate_diagrams.get_source_diff", return_value=the_diff),
            mock.patch("generate_diagrams.subprocess.run", return_value=claude_result) as mock_run,
        ):
            generate_diagrams.classify_change(item.source_path, item.diagram_path)

        assert mock_run.call_count == 1
        cmd_list = mock_run.call_args[0][0]
        assert cmd_list[:5] == ["claude", "--print", "--model", "haiku", "--dangerously-skip-permissions"]
        prompt = cmd_list[5]
        assert the_diff in prompt
        assert "STAMP" in prompt  # Classification prompt mentions STAMP as an option
        assert "PATCH" in prompt
        assert "REGENERATE" in prompt


# ---------------------------------------------------------------------------
# Tests: patch_diagram
# ---------------------------------------------------------------------------


class TestPatchDiagram:
    """Tests for the patch_diagram function."""

    def test_returns_patched_content_on_success(self, tmp_path: Path) -> None:
        """patch_diagram returns the patched diagram content from Claude."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        diff = "- old step\n+ new step"
        patched_mermaid = "```mermaid\ngraph TD\n  A --> B\n  A --> C\n```"
        claude_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=patched_mermaid, stderr=""
        )

        with mock.patch("generate_diagrams.subprocess.run", return_value=claude_result):
            result = generate_diagrams.patch_diagram(
                item.source_path, item.diagram_path, diff
            )

        assert result == patched_mermaid

    def test_returns_none_on_claude_failure(self, tmp_path: Path) -> None:
        """patch_diagram returns None when Claude fails, signaling fallback to regen."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        claude_result = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="error"
        )

        with mock.patch("generate_diagrams.subprocess.run", return_value=claude_result):
            result = generate_diagrams.patch_diagram(
                item.source_path, item.diagram_path, "- old\n+ new"
            )

        assert result is None

    def test_returns_none_on_timeout(self, tmp_path: Path) -> None:
        """patch_diagram returns None when Claude times out."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        with mock.patch(
            "generate_diagrams.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=60),
        ):
            result = generate_diagrams.patch_diagram(
                item.source_path, item.diagram_path, "- old\n+ new"
            )

        assert result is None

    def test_returns_none_on_empty_output(self, tmp_path: Path) -> None:
        """patch_diagram returns None when Claude returns empty output."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        claude_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        with mock.patch("generate_diagrams.subprocess.run", return_value=claude_result):
            result = generate_diagrams.patch_diagram(
                item.source_path, item.diagram_path, "- old\n+ new"
            )

        assert result is None

    def test_returns_none_on_cannot_patch(self, tmp_path: Path) -> None:
        """patch_diagram returns None when Claude says CANNOT_PATCH."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        claude_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="CANNOT_PATCH", stderr=""
        )

        with mock.patch("generate_diagrams.subprocess.run", return_value=claude_result):
            result = generate_diagrams.patch_diagram(
                item.source_path, item.diagram_path, "- old\n+ new"
            )

        assert result is None

    def test_returns_none_when_diagram_missing(self, tmp_path: Path) -> None:
        """patch_diagram returns None when the diagram file doesn't exist."""
        item = make_source_item(tmp_path)
        # Don't create diagram file

        result = generate_diagrams.patch_diagram(
            item.source_path, item.diagram_path, "- old\n+ new"
        )

        assert result is None

    def test_sends_existing_diagram_and_diff_to_claude(self, tmp_path: Path) -> None:
        """patch_diagram sends the correct prompt containing existing diagram and diff."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        diff = "- old step\n+ new step"
        existing_content = item.diagram_path.read_text(encoding="utf-8")

        patched_mermaid = "```mermaid\ngraph TD\n  A --> B\n```"
        claude_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=patched_mermaid, stderr=""
        )

        with mock.patch("generate_diagrams.subprocess.run", return_value=claude_result) as mock_run:
            generate_diagrams.patch_diagram(
                item.source_path, item.diagram_path, diff
            )

        assert mock_run.call_count == 1
        call_args = mock_run.call_args
        cmd_list = call_args[0][0]
        assert cmd_list[:5] == ["claude", "--print", "--model", "haiku", "--dangerously-skip-permissions"]
        prompt_text = cmd_list[5]
        assert existing_content in prompt_text
        assert diff in prompt_text


# ---------------------------------------------------------------------------
# Tests: --force-regen flag
# ---------------------------------------------------------------------------


class TestForceRegenFlag:
    """Tests for the --force-regen CLI flag."""

    def test_force_regen_bypasses_classification(self, tmp_path: Path) -> None:
        """--force-regen should skip classify_change and go straight to full generation."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        with (
            mock.patch("generate_diagrams.classify_change") as mock_classify,
            mock.patch("generate_diagrams.generate_diagram") as mock_generate,
            mock.patch("generate_diagrams.discover_skills", return_value=[item]),
            mock.patch("generate_diagrams.discover_commands", return_value=[]),
            mock.patch("generate_diagrams.discover_agents", return_value=[]),
            mock.patch("sys.argv", ["generate_diagrams.py", "--force-regen", "--all"]),
        ):
            mock_generate.return_value = (
                generate_diagrams.GenerationResult(
                    item=item, status="generated", message="ok"
                ),
                "diagram content",
            )
            generate_diagrams.main()

        mock_classify.assert_not_called()
        assert mock_generate.call_count == 1

    def test_force_regen_flag_accepted_by_argparse(self) -> None:
        """The --force-regen flag should be recognized by the argument parser."""
        with (
            mock.patch("sys.argv", ["generate_diagrams.py", "--force-regen", "--dry-run"]),
            mock.patch("generate_diagrams.discover_skills", return_value=[]),
            mock.patch("generate_diagrams.discover_commands", return_value=[]),
            mock.patch("generate_diagrams.discover_agents", return_value=[]),
        ):
            result = generate_diagrams.main()
            assert result == 0


# ---------------------------------------------------------------------------
# Tests: Processing loop integration
# ---------------------------------------------------------------------------


class TestProcessingLoopIntegration:
    """Tests for classify_change integration into main processing loop."""

    def test_stamp_classification_calls_stamp_as_fresh(self, tmp_path: Path) -> None:
        """When classify_change returns STAMP, stamp_as_fresh is called and generation is skipped."""
        item = make_source_item(tmp_path)
        current_hash = generate_diagrams.compute_hash(item.source_path)
        write_diagram_with_meta(item, "oldhash")

        with (
            mock.patch("generate_diagrams.classify_change", return_value="STAMP") as mock_classify,
            mock.patch("generate_diagrams.stamp_as_fresh") as mock_stamp,
            mock.patch("generate_diagrams.generate_diagram") as mock_generate,
            mock.patch("generate_diagrams.discover_skills", return_value=[item]),
            mock.patch("generate_diagrams.discover_commands", return_value=[]),
            mock.patch("generate_diagrams.discover_agents", return_value=[]),
            mock.patch("sys.argv", ["generate_diagrams.py", "--all"]),
        ):
            generate_diagrams.main()

        mock_classify.assert_called_once_with(item.source_path, item.diagram_path)
        mock_stamp.assert_called_once_with(item, current_hash)
        mock_generate.assert_not_called()

    def test_patch_classification_calls_patch_diagram(self, tmp_path: Path) -> None:
        """When classify_change returns PATCH, patch_diagram is called."""
        item = make_source_item(tmp_path)
        current_hash = generate_diagrams.compute_hash(item.source_path)
        write_diagram_with_meta(item, "oldhash")

        patched_content = "```mermaid\ngraph TD\n  A --> C\n```"

        with (
            mock.patch("generate_diagrams.REPO_ROOT", tmp_path),
            mock.patch("generate_diagrams.classify_change", return_value="PATCH"),
            mock.patch("generate_diagrams.get_source_diff", return_value="- old\n+ new"),
            mock.patch("generate_diagrams.patch_diagram", return_value=patched_content) as mock_patch,
            mock.patch("generate_diagrams.generate_diagram") as mock_generate,
            mock.patch("generate_diagrams.discover_skills", return_value=[item]),
            mock.patch("generate_diagrams.discover_commands", return_value=[]),
            mock.patch("generate_diagrams.discover_agents", return_value=[]),
            mock.patch("sys.argv", ["generate_diagrams.py", "--all"]),
        ):
            generate_diagrams.main()

        mock_patch.assert_called_once()
        mock_generate.assert_not_called()

    def test_regenerate_classification_falls_through_to_generate(self, tmp_path: Path) -> None:
        """When classify_change returns REGENERATE, full generate_diagram is called."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        with (
            mock.patch("generate_diagrams.classify_change", return_value="REGENERATE"),
            mock.patch("generate_diagrams.stamp_as_fresh") as mock_stamp,
            mock.patch("generate_diagrams.generate_diagram") as mock_generate,
            mock.patch("generate_diagrams.discover_skills", return_value=[item]),
            mock.patch("generate_diagrams.discover_commands", return_value=[]),
            mock.patch("generate_diagrams.discover_agents", return_value=[]),
            mock.patch("sys.argv", ["generate_diagrams.py", "--all"]),
        ):
            mock_generate.return_value = (
                generate_diagrams.GenerationResult(
                    item=item, status="generated", message="ok"
                ),
                "diagram content",
            )
            generate_diagrams.main()

        mock_stamp.assert_not_called()
        assert mock_generate.call_count == 1

    def test_patch_failure_falls_back_to_full_generation(self, tmp_path: Path) -> None:
        """When patch_diagram returns None, fall back to full generate_diagram."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        with (
            mock.patch("generate_diagrams.REPO_ROOT", tmp_path),
            mock.patch("generate_diagrams.classify_change", return_value="PATCH"),
            mock.patch("generate_diagrams.get_source_diff", return_value="- old\n+ new"),
            mock.patch("generate_diagrams.patch_diagram", return_value=None),
            mock.patch("generate_diagrams.generate_diagram") as mock_generate,
            mock.patch("generate_diagrams.discover_skills", return_value=[item]),
            mock.patch("generate_diagrams.discover_commands", return_value=[]),
            mock.patch("generate_diagrams.discover_agents", return_value=[]),
            mock.patch("sys.argv", ["generate_diagrams.py", "--all"]),
        ):
            mock_generate.return_value = (
                generate_diagrams.GenerationResult(
                    item=item, status="generated", message="ok"
                ),
                "diagram content",
            )
            generate_diagrams.main()

        assert mock_generate.call_count == 1

    def test_existing_force_flag_still_works(self, tmp_path: Path) -> None:
        """The existing --force flag bypasses staleness and classification."""
        item = make_source_item(tmp_path)
        current_hash = generate_diagrams.compute_hash(item.source_path)
        # Diagram is fresh (matching hash)
        write_diagram_with_meta(item, current_hash)

        with (
            mock.patch("generate_diagrams.classify_change") as mock_classify,
            mock.patch("generate_diagrams.generate_diagram") as mock_generate,
            mock.patch("generate_diagrams.discover_skills", return_value=[item]),
            mock.patch("generate_diagrams.discover_commands", return_value=[]),
            mock.patch("generate_diagrams.discover_agents", return_value=[]),
            mock.patch("sys.argv", ["generate_diagrams.py", "--force", "--all"]),
        ):
            mock_generate.return_value = (
                generate_diagrams.GenerationResult(
                    item=item, status="generated", message="ok"
                ),
                "diagram content",
            )
            generate_diagrams.main()

        mock_classify.assert_not_called()
        assert mock_generate.call_count == 1


# ---------------------------------------------------------------------------
# Tests: Interactive mode with smart classification
# ---------------------------------------------------------------------------


class TestInteractiveSmartClassification:
    """Tests for interactive mode prompts based on classification."""

    def test_interactive_stamp_shows_stamp_prompt(self, tmp_path: Path) -> None:
        """In interactive mode, STAMP classification shows stamp/generate/quit prompt."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        with (
            mock.patch("generate_diagrams.classify_change", return_value="STAMP"),
            mock.patch("generate_diagrams.stamp_as_fresh") as mock_stamp,
            mock.patch("generate_diagrams.show_source_changes"),
            mock.patch("generate_diagrams.discover_skills", return_value=[item]),
            mock.patch("generate_diagrams.discover_commands", return_value=[]),
            mock.patch("generate_diagrams.discover_agents", return_value=[]),
            mock.patch("builtins.input", return_value="s") as mock_input,
            mock.patch("sys.argv", ["generate_diagrams.py", "--interactive", "--all"]),
        ):
            generate_diagrams.main()

        prompt_text = mock_input.call_args[0][0]
        assert prompt_text == "  [S]tamp (enter) / [g]enerate / [q]uit: "

    def test_interactive_patch_shows_patch_prompt(self, tmp_path: Path) -> None:
        """In interactive mode, PATCH classification shows patch/generate/quit prompt."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        with (
            mock.patch("generate_diagrams.REPO_ROOT", tmp_path),
            mock.patch("generate_diagrams.classify_change", return_value="PATCH"),
            mock.patch("generate_diagrams.get_source_diff", return_value="- old\n+ new"),
            mock.patch("generate_diagrams.patch_diagram", return_value="```mermaid\ngraph TD\n  A --> B\n```"),
            mock.patch("generate_diagrams.show_source_changes"),
            mock.patch("generate_diagrams.discover_skills", return_value=[item]),
            mock.patch("generate_diagrams.discover_commands", return_value=[]),
            mock.patch("generate_diagrams.discover_agents", return_value=[]),
            mock.patch("builtins.input", return_value="p") as mock_input,
            mock.patch("sys.argv", ["generate_diagrams.py", "--interactive", "--all"]),
        ):
            generate_diagrams.main()

        prompt_text = mock_input.call_args[0][0]
        assert prompt_text == "  [P]atch (enter) / [g]enerate / [q]uit: "

    def test_interactive_regenerate_shows_generate_prompt(self, tmp_path: Path) -> None:
        """In interactive mode, REGENERATE classification shows generate/skip/quit prompt."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        with (
            mock.patch("generate_diagrams.classify_change", return_value="REGENERATE"),
            mock.patch("generate_diagrams.show_source_changes"),
            mock.patch("generate_diagrams.generate_diagram") as mock_generate,
            mock.patch("generate_diagrams.discover_skills", return_value=[item]),
            mock.patch("generate_diagrams.discover_commands", return_value=[]),
            mock.patch("generate_diagrams.discover_agents", return_value=[]),
            mock.patch("builtins.input", return_value="g") as mock_input,
            mock.patch("sys.argv", ["generate_diagrams.py", "--interactive", "--all"]),
        ):
            mock_generate.return_value = (
                generate_diagrams.GenerationResult(
                    item=item, status="generated", message="ok"
                ),
                "diagram content",
            )
            generate_diagrams.main()

        prompt_text = mock_input.call_args[0][0]
        assert prompt_text == "  [G]enerate (enter) / [s]kip / [q]uit: "
