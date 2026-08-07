"""Tests for smart update flow in generate_diagrams.py.

Tests classify_change(), patch_diagram(), --force-regen flag,
and integration into the main processing loop.

All mocks use tripwire per project policy (see AGENTS.md, "Testing with
Tripwire"). ``unittest.mock`` and ``monkeypatch.setattr`` are forbidden
for mocking dependencies.
"""

import asyncio
import json
import sys
from pathlib import Path

import pytest
import tripwire
from dirty_equals import AnyThing

from spellbook.sdk.unified import ClaudeAgentClient


# Add project root so we can import generate_diagrams as a module
WORKTREE_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(WORKTREE_ROOT / "scripts"))

import generate_diagrams  # noqa: E402  (imported after sys.path mangling)


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

    @pytest.mark.allow("subprocess")
    def test_returns_uncommitted_diff_when_available(self, tmp_path: Path) -> None:
        """get_source_diff returns git diff HEAD output when non-empty."""
        source_path = tmp_path / "skill.md"
        source_path.write_text("content", encoding="utf-8")

        diff_text = "- old line\n+ new line"

        repo_root_mock = tripwire.mock("generate_diagrams:_get_repo_root")
        repo_root_mock.returns(tmp_path)
        tripwire.subprocess.mock_run(
            command=["git", "diff", "HEAD", "--", "skill.md"],
            returncode=0,
            stdout=diff_text,
        )

        with tripwire:
            result = generate_diagrams.get_source_diff(source_path)

        assert result == diff_text
        repo_root_mock.assert_call(args=(), kwargs={}, returned=AnyThing)
        tripwire.subprocess.assert_run(
            command=["git", "diff", "HEAD", "--", "skill.md"],
            returncode=0,
            stdout=diff_text,
            stderr="",
        )

    @pytest.mark.allow("subprocess")
    def test_falls_back_to_head_tilde_1_when_head_empty(self, tmp_path: Path) -> None:
        """get_source_diff tries HEAD~1 when HEAD diff is empty."""
        source_path = tmp_path / "skill.md"
        source_path.write_text("content", encoding="utf-8")

        history_diff = "- old\n+ new"

        repo_root_mock = tripwire.mock("generate_diagrams:_get_repo_root")
        repo_root_mock.returns(tmp_path)
        tripwire.subprocess.mock_run(
            command=["git", "diff", "HEAD", "--", "skill.md"],
            returncode=0,
            stdout="",
        )
        tripwire.subprocess.mock_run(
            command=["git", "diff", "HEAD~1", "--", "skill.md"],
            returncode=0,
            stdout=history_diff,
        )

        with tripwire:
            result = generate_diagrams.get_source_diff(source_path)

        assert result == history_diff
        repo_root_mock.assert_call(args=(), kwargs={}, returned=AnyThing)
        tripwire.subprocess.assert_run(
            command=["git", "diff", "HEAD", "--", "skill.md"],
            returncode=0,
            stdout="",
            stderr="",
        )
        tripwire.subprocess.assert_run(
            command=["git", "diff", "HEAD~1", "--", "skill.md"],
            returncode=0,
            stdout=history_diff,
            stderr="",
        )

    @pytest.mark.allow("subprocess")
    def test_returns_empty_when_no_diff_available(self, tmp_path: Path) -> None:
        """get_source_diff returns empty string when both diffs are empty."""
        source_path = tmp_path / "skill.md"
        source_path.write_text("content", encoding="utf-8")

        repo_root_mock = tripwire.mock("generate_diagrams:_get_repo_root")
        repo_root_mock.returns(tmp_path)
        tripwire.subprocess.mock_run(
            command=["git", "diff", "HEAD", "--", "skill.md"],
            returncode=0,
            stdout="",
        )
        tripwire.subprocess.mock_run(
            command=["git", "diff", "HEAD~1", "--", "skill.md"],
            returncode=0,
            stdout="",
        )

        with tripwire:
            result = generate_diagrams.get_source_diff(source_path)

        assert result == ""
        repo_root_mock.assert_call(args=(), kwargs={}, returned=AnyThing)
        tripwire.subprocess.assert_run(
            command=["git", "diff", "HEAD", "--", "skill.md"],
            returncode=0,
            stdout="",
            stderr="",
        )
        tripwire.subprocess.assert_run(
            command=["git", "diff", "HEAD~1", "--", "skill.md"],
            returncode=0,
            stdout="",
            stderr="",
        )


# ---------------------------------------------------------------------------
# Tests: generate_diagram (subprocess path)
# ---------------------------------------------------------------------------


class TestGenerateDiagramNoMermaid:
    """Regression: when the subprocess produces no mermaid content, nothing
    is written to disk (no scavenged/synthesized diagram file)."""

    @pytest.mark.allow("subprocess")
    def test_no_mermaid_output_writes_nothing(self) -> None:
        import shutil
        import tempfile

        # build_prompt()/generate_diagram() call item.source_path.relative_to
        # (module-level) REPO_ROOT, which tripwire cannot mock as a bare
        # constant -- so the item must live under the real REPO_ROOT.
        work_dir = Path(tempfile.mkdtemp(dir=generate_diagrams.REPO_ROOT))
        repo_root_stray = generate_diagrams.REPO_ROOT / "DIAGRAM.md"
        # Never clobber a real repo-root file; if one exists the plant is skipped.
        plant_repo_root_stray = not repo_root_stray.exists()
        try:
            item = make_source_item(work_dir)
            assert not item.diagram_path.exists()

            # The regression this test names is a file-scavenging loop that
            # adopted any DIAGRAM.md it found near the source. Without a stray
            # file present, every candidate.exists() is False and the loop would
            # be invisible -- the test could not fail.
            #
            # Plant EVERY candidate the removed loop probed, not just the first.
            # Planting only `<source dir>/DIAGRAM.md` meant a partial regression
            # that restored just the REPO_ROOT or the `<name>-DIAGRAM.md` arm
            # stayed green.
            stray_body = "# stray\n\n```mermaid\ngraph TD\n  X --> Y\n```\n"
            strays = [
                item.source_path.parent / "DIAGRAM.md",
                item.diagram_path.parent / f"{item.name}-DIAGRAM.md",
            ]
            if plant_repo_root_stray:
                strays.append(repo_root_stray)
            for stray in strays:
                stray.parent.mkdir(parents=True, exist_ok=True)
                stray.write_text(stray_body, encoding="utf-8")

            prompt = generate_diagrams.build_prompt(item)
            expected_cmd = [
                "claude",
                "--print",
                "--model", "haiku",
                "--dangerously-skip-permissions",
                "--allowedTools", "Read",
                prompt,
            ]

            tripwire.subprocess.mock_run(
                command=expected_cmd,
                returncode=0,
                stdout="I looked at the source and it seems fine, no changes needed.",
            )

            with tripwire:
                result, content = generate_diagrams.generate_diagram(
                    item, "newhash", provider="claude", model="haiku", write=True,
                )

            assert result.status == "failed"
            assert content is None
            assert not item.diagram_path.exists()
            # No stray may be adopted as the diagram, nor consumed.
            for stray in strays:
                assert stray.exists(), (
                    f"a stray {stray.name} must not be scavenged or deleted"
                )
                assert stray.read_text(encoding="utf-8") == stray_body
            tripwire.subprocess.assert_run(
                command=expected_cmd,
                returncode=0,
                stdout=AnyThing,
                stderr="",
            )
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)
            if plant_repo_root_stray:
                repo_root_stray.unlink(missing_ok=True)


class TestAgentOptionsAreLockedDown:
    """The classifier and the patcher are text-in/text-out. They must be given
    NO tools and a single turn.

    These options are the whole of the new behavior, so asserting the call with
    ``args=AnyThing`` would leave them unpinned: dropping ``allowed_tools=[]``
    would silently restore tool access with every test still green. The options
    object is therefore captured and inspected field by field.
    """

    @staticmethod
    def _capture(client) -> tuple[list, object]:
        """Mock ``get_agent_client`` so the AgentOptions it receives is captured.

        Returns ``(captured, mock)``. The mock handle must still be asserted --
        tripwire's strict verifier requires an assert for every interaction --
        but the meaningful assertions run against ``captured``.
        """
        captured: list = []

        def _get_client(provider, options):
            captured.append((provider, options))
            return client

        client_mock = tripwire.mock("generate_diagrams:get_agent_client")
        client_mock.calls(_get_client)
        return captured, client_mock

    def test_classify_change_gets_no_tools_and_one_turn(self, tmp_path: Path) -> None:
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        async def _run(_prompt: str) -> str:
            return "STAMP"

        client = ClaudeAgentClient()
        run_mock = tripwire.mock.object(client, "run")
        run_mock.calls(_run)
        diff_mock = tripwire.mock("generate_diagrams:get_source_diff")
        diff_mock.returns("- old\n+ new")
        captured, client_mock = self._capture(client)

        with tripwire:
            asyncio.run(
                generate_diagrams.classify_change(
                    item.source_path, item.diagram_path, model="haiku"
                )
            )

        assert len(captured) == 1
        provider, opts = captured[0]
        assert provider == "claude"
        assert opts.allowed_tools == [], "the classifier must be given NO tools"
        assert opts.max_turns == 1, "the classifier must get exactly one turn"
        assert opts.model == "haiku"
        diff_mock.assert_call(args=(item.source_path,), kwargs={}, returned=AnyThing)
        client_mock.assert_call(args=AnyThing, kwargs={}, returned=AnyThing)
        run_mock.assert_call(args=AnyThing, kwargs={}, returned=AnyThing)

    def test_patch_diagram_gets_no_tools_and_one_turn(self, tmp_path: Path) -> None:
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        async def _run(_prompt: str) -> str:
            return "```mermaid\ngraph TD\n  A --> B\n```"

        client = ClaudeAgentClient()
        run_mock = tripwire.mock.object(client, "run")
        run_mock.calls(_run)
        captured, client_mock = self._capture(client)

        with tripwire:
            asyncio.run(
                generate_diagrams.patch_diagram(
                    item.source_path, item.diagram_path, "- old\n+ new", model="haiku"
                )
            )

        assert len(captured) == 1
        provider, opts = captured[0]
        assert provider == "claude"
        assert opts.allowed_tools == [], "the patcher must be given NO tools"
        assert opts.max_turns == 1, "the patcher must get exactly one turn"
        assert opts.model == "haiku"
        client_mock.assert_call(args=AnyThing, kwargs={}, returned=AnyThing)
        run_mock.assert_call(args=AnyThing, kwargs={}, returned=AnyThing)


class TestClassifyChange:
    """Tests for the classify_change function (async, SDK-based)."""

    def test_returns_stamp_when_sdk_says_stamp(self, tmp_path: Path) -> None:
        """classify_change returns 'STAMP' when the agent returns 'STAMP'."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        async def _run(_prompt: str) -> str:
            return "STAMP"

        client = ClaudeAgentClient()
        run_mock = tripwire.mock.object(client, "run")
        run_mock.calls(_run)

        diff_mock = tripwire.mock("generate_diagrams:get_source_diff")
        diff_mock.returns("- old\n+ new")
        client_mock = tripwire.mock("generate_diagrams:get_agent_client")
        client_mock.returns(client)

        with tripwire:
            result = asyncio.run(
                generate_diagrams.classify_change(item.source_path, item.diagram_path)
            )

        assert result == "STAMP"
        diff_mock.assert_call(args=(item.source_path,), kwargs={}, returned=AnyThing)
        client_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
        run_mock.assert_call(args=AnyThing, kwargs={}, returned=AnyThing)

    def test_returns_patch_when_sdk_says_patch(self, tmp_path: Path) -> None:
        """classify_change returns 'PATCH' when the agent returns 'PATCH'."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        async def _run(_prompt: str) -> str:
            return "PATCH\n"

        client = ClaudeAgentClient()
        run_mock = tripwire.mock.object(client, "run")
        run_mock.calls(_run)

        diff_mock = tripwire.mock("generate_diagrams:get_source_diff")
        diff_mock.returns("- old step\n+ new step")
        client_mock = tripwire.mock("generate_diagrams:get_agent_client")
        client_mock.returns(client)

        with tripwire:
            result = asyncio.run(
                generate_diagrams.classify_change(item.source_path, item.diagram_path)
            )

        assert result == "PATCH"
        diff_mock.assert_call(args=(item.source_path,), kwargs={}, returned=AnyThing)
        client_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
        run_mock.assert_call(args=AnyThing, kwargs={}, returned=AnyThing)

    def test_returns_regenerate_when_sdk_says_regenerate(self, tmp_path: Path) -> None:
        """classify_change returns 'REGENERATE' when the agent returns 'REGENERATE'."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        async def _run(_prompt: str) -> str:
            return "REGENERATE"

        client = ClaudeAgentClient()
        run_mock = tripwire.mock.object(client, "run")
        run_mock.calls(_run)

        diff_mock = tripwire.mock("generate_diagrams:get_source_diff")
        diff_mock.returns("massive rewrite")
        client_mock = tripwire.mock("generate_diagrams:get_agent_client")
        client_mock.returns(client)

        with tripwire:
            result = asyncio.run(
                generate_diagrams.classify_change(item.source_path, item.diagram_path)
            )

        assert result == "REGENERATE"
        diff_mock.assert_call(args=(item.source_path,), kwargs={}, returned=AnyThing)
        client_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
        run_mock.assert_call(args=AnyThing, kwargs={}, returned=AnyThing)

    def test_classification_unavailable_on_sdk_error(self, tmp_path: Path) -> None:
        """classify_change returns CLASSIFICATION_UNAVAILABLE (not REGENERATE)
        when the agent raises an exception, so a real REGENERATE verdict is
        distinguishable from a swallowed classification failure."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        async def _run(_prompt: str) -> str:
            raise RuntimeError("sdk error")

        client = ClaudeAgentClient()
        run_mock = tripwire.mock.object(client, "run")
        run_mock.calls(_run)

        diff_mock = tripwire.mock("generate_diagrams:get_source_diff")
        diff_mock.returns("some diff")
        client_mock = tripwire.mock("generate_diagrams:get_agent_client")
        client_mock.returns(client)

        with tripwire:
            result = asyncio.run(
                generate_diagrams.classify_change(item.source_path, item.diagram_path)
            )

        assert result == generate_diagrams.CLASSIFICATION_UNAVAILABLE
        assert result != "REGENERATE"
        diff_mock.assert_call(args=(item.source_path,), kwargs={}, returned=AnyThing)
        client_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
        run_mock.assert_call(args=AnyThing, kwargs={}, returned=AnyThing)

    def test_classification_unavailable_on_timeout(self, tmp_path: Path) -> None:
        """classify_change returns CLASSIFICATION_UNAVAILABLE when the agent
        times out (not REGENERATE, per the disguise-removal fix)."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        async def _run(_prompt: str) -> str:
            raise asyncio.TimeoutError()

        client = ClaudeAgentClient()
        run_mock = tripwire.mock.object(client, "run")
        run_mock.calls(_run)

        diff_mock = tripwire.mock("generate_diagrams:get_source_diff")
        diff_mock.returns("some diff")
        client_mock = tripwire.mock("generate_diagrams:get_agent_client")
        client_mock.returns(client)

        with tripwire:
            result = asyncio.run(
                generate_diagrams.classify_change(item.source_path, item.diagram_path)
            )

        assert result == generate_diagrams.CLASSIFICATION_UNAVAILABLE
        assert result != "REGENERATE"
        diff_mock.assert_call(args=(item.source_path,), kwargs={}, returned=AnyThing)
        client_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
        run_mock.assert_call(args=AnyThing, kwargs={}, returned=AnyThing)

    def test_falls_back_to_regenerate_on_unexpected_output(self, tmp_path: Path) -> None:
        """classify_change returns 'REGENERATE' when the agent returns gibberish."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        async def _run(_prompt: str) -> str:
            return "I think you should regenerate this"

        client = ClaudeAgentClient()
        run_mock = tripwire.mock.object(client, "run")
        run_mock.calls(_run)

        diff_mock = tripwire.mock("generate_diagrams:get_source_diff")
        diff_mock.returns("some diff")
        client_mock = tripwire.mock("generate_diagrams:get_agent_client")
        client_mock.returns(client)

        with tripwire:
            result = asyncio.run(
                generate_diagrams.classify_change(item.source_path, item.diagram_path)
            )

        assert result == "REGENERATE"
        diff_mock.assert_call(args=(item.source_path,), kwargs={}, returned=AnyThing)
        client_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
        run_mock.assert_call(args=AnyThing, kwargs={}, returned=AnyThing)

    def test_falls_back_to_regenerate_when_no_diff_available(self, tmp_path: Path) -> None:
        """When get_source_diff returns empty, falls back to REGENERATE."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        diff_mock = tripwire.mock("generate_diagrams:get_source_diff")
        diff_mock.returns("")

        with tripwire:
            result = asyncio.run(
                generate_diagrams.classify_change(item.source_path, item.diagram_path)
            )

        assert result == "REGENERATE"
        diff_mock.assert_call(args=(item.source_path,), kwargs={}, returned=AnyThing)

    def test_sends_classification_prompt_with_diff(self, tmp_path: Path) -> None:
        """classify_change sends the diff embedded in the classification prompt to the agent."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        the_diff = "- removed line\n+ added line"
        captured_prompts: list[str] = []

        async def _run(prompt: str) -> str:
            captured_prompts.append(prompt)
            return "STAMP"

        client = ClaudeAgentClient()
        run_mock = tripwire.mock.object(client, "run")
        run_mock.calls(_run)

        diff_mock = tripwire.mock("generate_diagrams:get_source_diff")
        diff_mock.returns(the_diff)
        client_mock = tripwire.mock("generate_diagrams:get_agent_client")
        client_mock.returns(client)

        with tripwire:
            asyncio.run(
                generate_diagrams.classify_change(item.source_path, item.diagram_path)
            )

        diff_mock.assert_call(args=(item.source_path,), kwargs={}, returned=AnyThing)
        client_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
        run_mock.assert_call(args=AnyThing, kwargs={}, returned=AnyThing)

        assert len(captured_prompts) == 1
        prompt = captured_prompts[0]
        assert the_diff in prompt
        assert "STAMP" in prompt
        assert "PATCH" in prompt
        assert "REGENERATE" in prompt


# ---------------------------------------------------------------------------
# Tests: patch_diagram
# ---------------------------------------------------------------------------


class TestPatchDiagram:
    """Tests for the patch_diagram function (async, SDK-based)."""

    def test_returns_patched_content_on_success(self, tmp_path: Path) -> None:
        """patch_diagram returns the patched diagram content from the agent."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        diff = "- old step\n+ new step"
        patched_mermaid = "```mermaid\ngraph TD\n  A --> B\n  A --> C\n```"

        async def _run(_prompt: str) -> str:
            return patched_mermaid

        client = ClaudeAgentClient()
        run_mock = tripwire.mock.object(client, "run")
        run_mock.calls(_run)

        client_mock = tripwire.mock("generate_diagrams:get_agent_client")
        client_mock.returns(client)

        with tripwire:
            result = asyncio.run(
                generate_diagrams.patch_diagram(item.source_path, item.diagram_path, diff)
            )

        assert result == patched_mermaid
        client_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
        run_mock.assert_call(args=AnyThing, kwargs={}, returned=AnyThing)

    def test_returns_none_on_sdk_failure(self, tmp_path: Path) -> None:
        """patch_diagram returns None when the agent raises, signaling fallback to regen."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        async def _run(_prompt: str) -> str:
            raise RuntimeError("error")

        client = ClaudeAgentClient()
        run_mock = tripwire.mock.object(client, "run")
        run_mock.calls(_run)

        client_mock = tripwire.mock("generate_diagrams:get_agent_client")
        client_mock.returns(client)

        with tripwire:
            result = asyncio.run(
                generate_diagrams.patch_diagram(
                    item.source_path, item.diagram_path, "- old\n+ new"
                )
            )

        assert result is None
        client_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
        run_mock.assert_call(args=AnyThing, kwargs={}, returned=AnyThing)

    def test_returns_none_on_timeout(self, tmp_path: Path) -> None:
        """patch_diagram returns None when the agent times out."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        async def _run(_prompt: str) -> str:
            raise asyncio.TimeoutError()

        client = ClaudeAgentClient()
        run_mock = tripwire.mock.object(client, "run")
        run_mock.calls(_run)

        client_mock = tripwire.mock("generate_diagrams:get_agent_client")
        client_mock.returns(client)

        with tripwire:
            result = asyncio.run(
                generate_diagrams.patch_diagram(
                    item.source_path, item.diagram_path, "- old\n+ new"
                )
            )

        assert result is None
        client_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
        run_mock.assert_call(args=AnyThing, kwargs={}, returned=AnyThing)

    def test_returns_none_on_empty_output(self, tmp_path: Path) -> None:
        """patch_diagram returns None when the agent returns empty output."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        async def _run(_prompt: str) -> str:
            return ""

        client = ClaudeAgentClient()
        run_mock = tripwire.mock.object(client, "run")
        run_mock.calls(_run)

        client_mock = tripwire.mock("generate_diagrams:get_agent_client")
        client_mock.returns(client)

        with tripwire:
            result = asyncio.run(
                generate_diagrams.patch_diagram(
                    item.source_path, item.diagram_path, "- old\n+ new"
                )
            )

        assert result is None
        client_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
        run_mock.assert_call(args=AnyThing, kwargs={}, returned=AnyThing)

    def test_returns_none_on_cannot_patch(self, tmp_path: Path) -> None:
        """patch_diagram returns None when the agent says CANNOT_PATCH."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        async def _run(_prompt: str) -> str:
            return "CANNOT_PATCH"

        client = ClaudeAgentClient()
        run_mock = tripwire.mock.object(client, "run")
        run_mock.calls(_run)

        client_mock = tripwire.mock("generate_diagrams:get_agent_client")
        client_mock.returns(client)

        with tripwire:
            result = asyncio.run(
                generate_diagrams.patch_diagram(
                    item.source_path, item.diagram_path, "- old\n+ new"
                )
            )

        assert result is None
        client_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
        run_mock.assert_call(args=AnyThing, kwargs={}, returned=AnyThing)

    def test_returns_none_when_diagram_missing(self, tmp_path: Path) -> None:
        """patch_diagram returns None when the diagram file doesn't exist."""
        item = make_source_item(tmp_path)
        # Don't create diagram file

        result = asyncio.run(
            generate_diagrams.patch_diagram(
                item.source_path, item.diagram_path, "- old\n+ new"
            )
        )

        assert result is None

    def test_sends_existing_diagram_and_diff_to_agent(self, tmp_path: Path) -> None:
        """patch_diagram sends the correct prompt containing existing diagram and diff."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        diff = "- old step\n+ new step"
        existing_content = item.diagram_path.read_text(encoding="utf-8")

        patched_mermaid = "```mermaid\ngraph TD\n  A --> B\n```"
        captured_prompts: list[str] = []

        async def _run(prompt: str) -> str:
            captured_prompts.append(prompt)
            return patched_mermaid

        client = ClaudeAgentClient()
        run_mock = tripwire.mock.object(client, "run")
        run_mock.calls(_run)

        client_mock = tripwire.mock("generate_diagrams:get_agent_client")
        client_mock.returns(client)

        with tripwire:
            asyncio.run(
                generate_diagrams.patch_diagram(item.source_path, item.diagram_path, diff)
            )

        client_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
        run_mock.assert_call(args=AnyThing, kwargs={}, returned=AnyThing)
        assert len(captured_prompts) == 1
        prompt_text = captured_prompts[0]
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

        gen_result = (
            generate_diagrams.GenerationResult(
                item=item, status="generated", message="ok"
            ),
            "diagram content",
        )

        # NOTE: classify_change is intentionally NOT mocked. tripwire's strict
        # verifier will raise UnmockedInteractionError if main_async calls
        # classify_change while --force-regen is set, pinning the contract.
        gen_mock = tripwire.mock("generate_diagrams:generate_diagram")
        gen_mock.returns(gen_result)
        skills_mock = tripwire.mock("generate_diagrams:discover_skills")
        skills_mock.returns([item])
        cmds_mock = tripwire.mock("generate_diagrams:discover_commands")
        cmds_mock.returns([])
        agents_mock = tripwire.mock("generate_diagrams:discover_agents")
        agents_mock.returns([])

        with tripwire:
            asyncio.run(generate_diagrams.main_async(
                ["--force-regen", "--all"]
            ))

        with tripwire.in_any_order():
            gen_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
            skills_mock.assert_call(args=(), kwargs={}, returned=AnyThing)
            cmds_mock.assert_call(args=(), kwargs={}, returned=AnyThing)
            agents_mock.assert_call(args=(), kwargs={}, returned=AnyThing)

    def test_force_regen_flag_accepted_by_argparse(self) -> None:
        """The --force-regen flag should be recognized by the argument parser."""
        skills_mock = tripwire.mock("generate_diagrams:discover_skills")
        skills_mock.returns([])
        cmds_mock = tripwire.mock("generate_diagrams:discover_commands")
        cmds_mock.returns([])
        agents_mock = tripwire.mock("generate_diagrams:discover_agents")
        agents_mock.returns([])

        with tripwire:
            result = asyncio.run(generate_diagrams.main_async(
                ["--force-regen", "--dry-run"]
            ))

        assert result == 0
        with tripwire.in_any_order():
            skills_mock.assert_call(args=(), kwargs={}, returned=AnyThing)
            cmds_mock.assert_call(args=(), kwargs={}, returned=AnyThing)
            agents_mock.assert_call(args=(), kwargs={}, returned=AnyThing)


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

        async def _classify(*args, **kwargs):
            return "STAMP"

        classify_mock = tripwire.mock("generate_diagrams:classify_change")
        classify_mock.calls(_classify)
        stamp_mock = tripwire.mock("generate_diagrams:stamp_as_fresh")
        stamp_mock.returns(None)
        # NOTE: generate_diagram is intentionally NOT mocked. tripwire's
        # strict verifier pins that STAMP path must not invoke it.
        skills_mock = tripwire.mock("generate_diagrams:discover_skills")
        skills_mock.returns([item])
        cmds_mock = tripwire.mock("generate_diagrams:discover_commands")
        cmds_mock.returns([])
        agents_mock = tripwire.mock("generate_diagrams:discover_agents")
        agents_mock.returns([])

        with tripwire:
            asyncio.run(generate_diagrams.main_async(["--all"]))

        with tripwire.in_any_order():
            classify_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
            stamp_mock.assert_call(args=(item, current_hash), kwargs={}, returned=AnyThing)
            skills_mock.assert_call(args=(), kwargs={}, returned=AnyThing)
            cmds_mock.assert_call(args=(), kwargs={}, returned=AnyThing)
            agents_mock.assert_call(args=(), kwargs={}, returned=AnyThing)

    def test_patch_classification_calls_patch_diagram(self, tmp_path: Path) -> None:
        """When classify_change returns PATCH, patch_diagram is called."""
        item = make_source_item(tmp_path)
        generate_diagrams.compute_hash(item.source_path)
        write_diagram_with_meta(item, "oldhash")

        patched_content = "```mermaid\ngraph TD\n  A --> C\n```"

        async def _classify(*a, **k):
            return "PATCH"

        async def _patch(*a, **k):
            return patched_content

        classify_mock = tripwire.mock("generate_diagrams:classify_change")
        classify_mock.calls(_classify)
        diff_mock = tripwire.mock("generate_diagrams:get_source_diff")
        diff_mock.returns("- old\n+ new")
        patch_mock = tripwire.mock("generate_diagrams:patch_diagram")
        patch_mock.calls(_patch)
        repo_root_mock = tripwire.mock("generate_diagrams:_get_repo_root")
        repo_root_mock.returns(tmp_path)
        # NOTE: generate_diagram is intentionally NOT mocked; PATCH success
        # must not fall through to full regeneration.
        skills_mock = tripwire.mock("generate_diagrams:discover_skills")
        skills_mock.returns([item])
        cmds_mock = tripwire.mock("generate_diagrams:discover_commands")
        cmds_mock.returns([])
        agents_mock = tripwire.mock("generate_diagrams:discover_agents")
        agents_mock.returns([])

        with tripwire:
            asyncio.run(generate_diagrams.main_async(["--all"]))

        with tripwire.in_any_order():
            classify_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
            diff_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
            patch_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
            repo_root_mock.assert_call(args=(), kwargs={}, returned=AnyThing)
            skills_mock.assert_call(args=(), kwargs={}, returned=AnyThing)
            cmds_mock.assert_call(args=(), kwargs={}, returned=AnyThing)
            agents_mock.assert_call(args=(), kwargs={}, returned=AnyThing)

    def test_regenerate_classification_falls_through_to_generate(self, tmp_path: Path) -> None:
        """When classify_change returns REGENERATE, full generate_diagram is called."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        async def _classify(*a, **k):
            return "REGENERATE"

        gen_result = (
            generate_diagrams.GenerationResult(
                item=item, status="generated", message="ok"
            ),
            "diagram content",
        )

        classify_mock = tripwire.mock("generate_diagrams:classify_change")
        classify_mock.calls(_classify)
        # NOTE: stamp_as_fresh intentionally unmocked; REGENERATE path
        # must not call it.
        gen_mock = tripwire.mock("generate_diagrams:generate_diagram")
        gen_mock.returns(gen_result)
        skills_mock = tripwire.mock("generate_diagrams:discover_skills")
        skills_mock.returns([item])
        cmds_mock = tripwire.mock("generate_diagrams:discover_commands")
        cmds_mock.returns([])
        agents_mock = tripwire.mock("generate_diagrams:discover_agents")
        agents_mock.returns([])

        with tripwire:
            asyncio.run(generate_diagrams.main_async(["--all"]))

        with tripwire.in_any_order():
            classify_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
            gen_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
            skills_mock.assert_call(args=(), kwargs={}, returned=AnyThing)
            cmds_mock.assert_call(args=(), kwargs={}, returned=AnyThing)
            agents_mock.assert_call(args=(), kwargs={}, returned=AnyThing)

    def test_classification_unavailable_skips_the_item(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """UNAVAILABLE must change the ROUTING, not merely the tally.

        A swallowed classification failure is not evidence that regeneration is
        warranted. If UNAVAILABLE fell through to the REGENERATE branch, an SDK
        outage would silently burn a full regeneration on every stale diagram
        while the summary counter made it look accounted for.

        The guard is BEHAVIOURAL, not incidental. Leaving generate_diagram
        unmocked does make a regression crash, but it crashes on an unrelated
        ``relative_to(REPO_ROOT)`` -- a red for the wrong reason, which would
        stop being red the moment the item moved under the repo root. So the
        assertions below name the three observable consequences directly: the
        skip is ANNOUNCED, the diagram's recorded hash is UNCHANGED (not
        stamped, so the next run reclassifies), and the process reports the
        outage in its exit code.
        """
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        async def _classify(*a, **k):
            return generate_diagrams.CLASSIFICATION_UNAVAILABLE

        classify_mock = tripwire.mock("generate_diagrams:classify_change")
        classify_mock.calls(_classify)
        skills_mock = tripwire.mock("generate_diagrams:discover_skills")
        skills_mock.returns([item])
        cmds_mock = tripwire.mock("generate_diagrams:discover_commands")
        cmds_mock.returns([])
        agents_mock = tripwire.mock("generate_diagrams:discover_agents")
        agents_mock.returns([])

        diagram_before = item.diagram_path.read_text(encoding="utf-8")

        with tripwire:
            rc = asyncio.run(generate_diagrams.main_async(["--all"]))

        out = capsys.readouterr().out

        # Skipped, not regenerated and not stamped: the diagram is untouched, so
        # the next run reclassifies it instead of treating it as fresh.
        assert item.diagram_path.read_text(encoding="utf-8") == diagram_before
        assert '"source_hash": "sha256:oldhash"' in diagram_before
        # The skip is ANNOUNCED, not silent.
        assert "SKIPPED (classification unavailable)" in out
        # And the run-level summary surfaces it as needing attention. Deleting
        # this line from the summary must fail here.
        assert "classification unavailable (needs attention)" in out
        # A total classification outage is NOT a clean run.
        assert rc == generate_diagrams.EXIT_CLASSIFICATION_UNAVAILABLE
        assert rc != 0

        with tripwire.in_any_order():
            classify_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
            skills_mock.assert_call(args=(), kwargs={}, returned=AnyThing)
            cmds_mock.assert_call(args=(), kwargs={}, returned=AnyThing)
            agents_mock.assert_call(args=(), kwargs={}, returned=AnyThing)

    def test_patch_failure_falls_back_to_full_generation(self, tmp_path: Path) -> None:
        """When patch_diagram returns None, fall back to full generate_diagram."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        async def _classify(*a, **k):
            return "PATCH"

        async def _patch(*a, **k):
            return None

        gen_result = (
            generate_diagrams.GenerationResult(
                item=item, status="generated", message="ok"
            ),
            "diagram content",
        )

        classify_mock = tripwire.mock("generate_diagrams:classify_change")
        classify_mock.calls(_classify)
        diff_mock = tripwire.mock("generate_diagrams:get_source_diff")
        diff_mock.returns("- old\n+ new")
        patch_mock = tripwire.mock("generate_diagrams:patch_diagram")
        patch_mock.calls(_patch)
        gen_mock = tripwire.mock("generate_diagrams:generate_diagram")
        gen_mock.returns(gen_result)
        skills_mock = tripwire.mock("generate_diagrams:discover_skills")
        skills_mock.returns([item])
        cmds_mock = tripwire.mock("generate_diagrams:discover_commands")
        cmds_mock.returns([])
        agents_mock = tripwire.mock("generate_diagrams:discover_agents")
        agents_mock.returns([])

        with tripwire:
            asyncio.run(generate_diagrams.main_async(["--all"]))

        with tripwire.in_any_order():
            classify_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
            diff_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
            patch_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
            gen_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
            skills_mock.assert_call(args=(), kwargs={}, returned=AnyThing)
            cmds_mock.assert_call(args=(), kwargs={}, returned=AnyThing)
            agents_mock.assert_call(args=(), kwargs={}, returned=AnyThing)

    def test_existing_force_flag_still_works(self, tmp_path: Path) -> None:
        """The existing --force flag bypasses staleness and classification."""
        item = make_source_item(tmp_path)
        current_hash = generate_diagrams.compute_hash(item.source_path)
        # Diagram is fresh (matching hash)
        write_diagram_with_meta(item, current_hash)

        gen_result = (
            generate_diagrams.GenerationResult(
                item=item, status="generated", message="ok"
            ),
            "diagram content",
        )

        # NOTE: classify_change intentionally unmocked; --force must bypass it.
        gen_mock = tripwire.mock("generate_diagrams:generate_diagram")
        gen_mock.returns(gen_result)
        skills_mock = tripwire.mock("generate_diagrams:discover_skills")
        skills_mock.returns([item])
        cmds_mock = tripwire.mock("generate_diagrams:discover_commands")
        cmds_mock.returns([])
        agents_mock = tripwire.mock("generate_diagrams:discover_agents")
        agents_mock.returns([])

        with tripwire:
            asyncio.run(generate_diagrams.main_async(["--force", "--all"]))

        with tripwire.in_any_order():
            gen_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
            skills_mock.assert_call(args=(), kwargs={}, returned=AnyThing)
            cmds_mock.assert_call(args=(), kwargs={}, returned=AnyThing)
            agents_mock.assert_call(args=(), kwargs={}, returned=AnyThing)


# ---------------------------------------------------------------------------
# Tests: Interactive mode with smart classification
# ---------------------------------------------------------------------------


class TestInteractiveSmartClassification:
    """Tests for interactive mode prompts based on classification."""

    def test_interactive_stamp_shows_stamp_prompt(self, tmp_path: Path) -> None:
        """In interactive mode, STAMP classification shows stamp/generate/quit prompt."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        async def _classify(*a, **k):
            return "STAMP"

        captured_prompts: list[str] = []

        def _fake_input(prompt):
            captured_prompts.append(prompt)
            return "s"

        classify_mock = tripwire.mock("generate_diagrams:classify_change")
        classify_mock.calls(_classify)
        stamp_mock = tripwire.mock("generate_diagrams:stamp_as_fresh")
        stamp_mock.returns(None)
        show_mock = tripwire.mock("generate_diagrams:show_source_changes")
        show_mock.returns(None)
        skills_mock = tripwire.mock("generate_diagrams:discover_skills")
        skills_mock.returns([item])
        cmds_mock = tripwire.mock("generate_diagrams:discover_commands")
        cmds_mock.returns([])
        agents_mock = tripwire.mock("generate_diagrams:discover_agents")
        agents_mock.returns([])
        input_mock = tripwire.mock("builtins:input")
        input_mock.calls(_fake_input)

        with tripwire:
            asyncio.run(generate_diagrams.main_async(["--interactive", "--all"]))

        with tripwire.in_any_order():
            classify_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
            stamp_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
            show_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
            input_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
            skills_mock.assert_call(args=(), kwargs={}, returned=AnyThing)
            cmds_mock.assert_call(args=(), kwargs={}, returned=AnyThing)
            agents_mock.assert_call(args=(), kwargs={}, returned=AnyThing)

        assert captured_prompts == ["  [S]tamp (enter) / [g]enerate / [q]uit: "]

    def test_interactive_patch_shows_patch_prompt(self, tmp_path: Path) -> None:
        """In interactive mode, PATCH classification shows patch/generate/quit prompt."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        async def _classify(*a, **k):
            return "PATCH"

        async def _patch(*a, **k):
            return "```mermaid\ngraph TD\n  A --> B\n```"

        captured_prompts: list[str] = []

        def _fake_input(prompt):
            captured_prompts.append(prompt)
            return "p"

        classify_mock = tripwire.mock("generate_diagrams:classify_change")
        classify_mock.calls(_classify)
        diff_mock = tripwire.mock("generate_diagrams:get_source_diff")
        diff_mock.returns("- old\n+ new")
        patch_mock = tripwire.mock("generate_diagrams:patch_diagram")
        patch_mock.calls(_patch)
        repo_root_mock = tripwire.mock("generate_diagrams:_get_repo_root")
        repo_root_mock.returns(tmp_path)
        show_mock = tripwire.mock("generate_diagrams:show_source_changes")
        show_mock.returns(None)
        skills_mock = tripwire.mock("generate_diagrams:discover_skills")
        skills_mock.returns([item])
        cmds_mock = tripwire.mock("generate_diagrams:discover_commands")
        cmds_mock.returns([])
        agents_mock = tripwire.mock("generate_diagrams:discover_agents")
        agents_mock.returns([])
        input_mock = tripwire.mock("builtins:input")
        input_mock.calls(_fake_input)

        with tripwire:
            asyncio.run(generate_diagrams.main_async(["--interactive", "--all"]))

        with tripwire.in_any_order():
            classify_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
            input_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
            diff_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
            patch_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
            repo_root_mock.assert_call(args=(), kwargs={}, returned=AnyThing)
            show_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
            skills_mock.assert_call(args=(), kwargs={}, returned=AnyThing)
            cmds_mock.assert_call(args=(), kwargs={}, returned=AnyThing)
            agents_mock.assert_call(args=(), kwargs={}, returned=AnyThing)

        assert captured_prompts == ["  [P]atch (enter) / [g]enerate / [q]uit: "]

    def test_interactive_regenerate_shows_generate_prompt(self, tmp_path: Path) -> None:
        """In interactive mode, REGENERATE classification shows generate/skip/quit prompt."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        async def _classify(*a, **k):
            return "REGENERATE"

        captured_prompts: list[str] = []

        def _fake_input(prompt):
            captured_prompts.append(prompt)
            return "g"

        gen_result = (
            generate_diagrams.GenerationResult(
                item=item, status="generated", message="ok"
            ),
            "diagram content",
        )

        classify_mock = tripwire.mock("generate_diagrams:classify_change")
        classify_mock.calls(_classify)
        show_mock = tripwire.mock("generate_diagrams:show_source_changes")
        show_mock.returns(None)
        gen_mock = tripwire.mock("generate_diagrams:generate_diagram")
        gen_mock.returns(gen_result)
        skills_mock = tripwire.mock("generate_diagrams:discover_skills")
        skills_mock.returns([item])
        cmds_mock = tripwire.mock("generate_diagrams:discover_commands")
        cmds_mock.returns([])
        agents_mock = tripwire.mock("generate_diagrams:discover_agents")
        agents_mock.returns([])
        input_mock = tripwire.mock("builtins:input")
        input_mock.calls(_fake_input)

        with tripwire:
            asyncio.run(generate_diagrams.main_async(["--interactive", "--all"]))

        with tripwire.in_any_order():
            classify_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
            input_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
            show_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
            gen_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
            skills_mock.assert_call(args=(), kwargs={}, returned=AnyThing)
            cmds_mock.assert_call(args=(), kwargs={}, returned=AnyThing)
            agents_mock.assert_call(args=(), kwargs={}, returned=AnyThing)

        assert captured_prompts == ["  [G]enerate (enter) / [s]kip / [q]uit: "]

    def test_interactive_unavailable_prompts_instead_of_defaulting_to_regenerate(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """UNAVAILABLE must NOT be treated as a REGENERATE verdict.

        The REGENERATE branch shows "[G]enerate (enter) / [s]kip / [q]uit",
        which defaults the operator into a full regeneration on a bare Enter --
        during an SDK outage, for every stale diagram. A classification failure
        is the ABSENCE of a verdict, so it must fall to the unclassified prompt
        where the operator answers explicitly.

        Reverting the fix to ``classification = "REGENERATE"`` changes the
        prompt text and fails this test.
        """
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        async def _classify(*a, **k):
            return generate_diagrams.CLASSIFICATION_UNAVAILABLE

        captured_prompts: list[str] = []

        def _fake_input(prompt):
            captured_prompts.append(prompt)
            return "s"

        classify_mock = tripwire.mock("generate_diagrams:classify_change")
        classify_mock.calls(_classify)
        show_mock = tripwire.mock("generate_diagrams:show_source_changes")
        show_mock.returns(None)
        skills_mock = tripwire.mock("generate_diagrams:discover_skills")
        skills_mock.returns([item])
        cmds_mock = tripwire.mock("generate_diagrams:discover_commands")
        cmds_mock.returns([])
        agents_mock = tripwire.mock("generate_diagrams:discover_agents")
        agents_mock.returns([])
        input_mock = tripwire.mock("builtins:input")
        input_mock.calls(_fake_input)

        with tripwire:
            asyncio.run(generate_diagrams.main_async(["--interactive", "--all"]))

        with tripwire.in_any_order():
            classify_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
            show_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
            input_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
            skills_mock.assert_call(args=(), kwargs={}, returned=AnyThing)
            cmds_mock.assert_call(args=(), kwargs={}, returned=AnyThing)
            agents_mock.assert_call(args=(), kwargs={}, returned=AnyThing)

        assert captured_prompts == ["  Generate this diagram? [y]es / [s]kip / [q]uit: "]
        assert "Classification unavailable" in capsys.readouterr().out

    def test_interactive_unavailable_decline_does_not_stamp_and_is_surfaced(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The early-return path is where an outage ACTUALLY lands, and it leaked.

        During a classifier outage nothing has a verdict, so the operator
        declines everything, ``to_generate`` and ``to_patch`` are both empty and
        the function returns from the "Nothing to generate" branch. That branch
        (a) never read ``classify_failed_count``, so the outage was invisible,
        (b) called ``stamp_as_fresh`` on every declined item, marking them fresh
        against the CURRENT hash so they were never reclassified -- a silent
        PERMANENT drop, and (c) returned 0.

        ``stamp_as_fresh`` is intentionally left UNMOCKED: it is not supposed to
        be called at all here, and the assertion on the on-disk hash proves it
        was not.
        """
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")
        diagram_before = item.diagram_path.read_text(encoding="utf-8")

        async def _classify(*a, **k):
            return generate_diagrams.CLASSIFICATION_UNAVAILABLE

        def _fake_input(prompt):
            return "s"

        classify_mock = tripwire.mock("generate_diagrams:classify_change")
        classify_mock.calls(_classify)
        show_mock = tripwire.mock("generate_diagrams:show_source_changes")
        show_mock.returns(None)
        skills_mock = tripwire.mock("generate_diagrams:discover_skills")
        skills_mock.returns([item])
        cmds_mock = tripwire.mock("generate_diagrams:discover_commands")
        cmds_mock.returns([])
        agents_mock = tripwire.mock("generate_diagrams:discover_agents")
        agents_mock.returns([])
        input_mock = tripwire.mock("builtins:input")
        input_mock.calls(_fake_input)

        with tripwire:
            rc = asyncio.run(generate_diagrams.main_async(["--interactive", "--all"]))

        out = capsys.readouterr().out

        # (b) NOT stamped: the recorded hash is still the stale one, so the next
        # run reclassifies rather than treating the diagram as fresh.
        assert item.diagram_path.read_text(encoding="utf-8") == diagram_before
        assert '"source_hash": "sha256:oldhash"' in diagram_before
        assert "UNSTAMPED" in out

        # (a) The outage is surfaced on THIS return path, not only on the paths
        # that generated something. Deleting the tally must fail here.
        assert "classification unavailable (needs attention)" in out
        assert "1 item(s) went unclassified" in out

        # (c) A total classification outage is not a clean exit.
        assert rc == generate_diagrams.EXIT_CLASSIFICATION_UNAVAILABLE
        assert rc != 0

        with tripwire.in_any_order():
            classify_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
            show_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
            input_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
            skills_mock.assert_call(args=(), kwargs={}, returned=AnyThing)
            cmds_mock.assert_call(args=(), kwargs={}, returned=AnyThing)
            agents_mock.assert_call(args=(), kwargs={}, returned=AnyThing)
