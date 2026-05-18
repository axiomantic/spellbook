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


class _StubAgentClient:
    """Minimal stand-in for the SDK agent client.

    The classify/patch code paths only call ``client.run(prompt)``. A hand-rolled
    object stands in for the client itself; tripwire is then used to mock
    ``run`` so behavior, args, and call count are pinned through the same
    framework as the rest of the test.
    """

    def __init__(self):
        async def _default(_prompt):
            return ""

        self.run = _default


def _stub_client_returns(value):
    client = _StubAgentClient()

    async def _run(_prompt):
        return value

    client.run = _run
    return client


def _stub_client_raises(exc):
    client = _StubAgentClient()

    async def _run(_prompt):
        raise exc

    client.run = _run
    return client


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
# Tests: classify_change
# ---------------------------------------------------------------------------


class TestClassifyChange:
    """Tests for the classify_change function (async, SDK-based)."""

    def test_returns_stamp_when_sdk_says_stamp(self, tmp_path: Path) -> None:
        """classify_change returns 'STAMP' when the agent returns 'STAMP'."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        client = _stub_client_returns("STAMP")

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

    def test_returns_patch_when_sdk_says_patch(self, tmp_path: Path) -> None:
        """classify_change returns 'PATCH' when the agent returns 'PATCH'."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        client = _stub_client_returns("PATCH\n")

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

    def test_returns_regenerate_when_sdk_says_regenerate(self, tmp_path: Path) -> None:
        """classify_change returns 'REGENERATE' when the agent returns 'REGENERATE'."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        client = _stub_client_returns("REGENERATE")

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

    def test_falls_back_to_regenerate_on_sdk_error(self, tmp_path: Path) -> None:
        """classify_change returns 'REGENERATE' when the agent raises an exception."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        client = _stub_client_raises(RuntimeError("sdk error"))

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

    def test_falls_back_to_regenerate_on_timeout(self, tmp_path: Path) -> None:
        """classify_change returns 'REGENERATE' when the agent times out."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        client = _stub_client_raises(asyncio.TimeoutError())

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

    def test_falls_back_to_regenerate_on_unexpected_output(self, tmp_path: Path) -> None:
        """classify_change returns 'REGENERATE' when the agent returns gibberish."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        client = _stub_client_returns("I think you should regenerate this")

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

        class _CapturingClient:
            async def run(self, prompt):
                captured_prompts.append(prompt)
                return "STAMP"

        diff_mock = tripwire.mock("generate_diagrams:get_source_diff")
        diff_mock.returns(the_diff)
        client_mock = tripwire.mock("generate_diagrams:get_agent_client")
        client_mock.returns(_CapturingClient())

        with tripwire:
            asyncio.run(
                generate_diagrams.classify_change(item.source_path, item.diagram_path)
            )

        diff_mock.assert_call(args=(item.source_path,), kwargs={}, returned=AnyThing)
        client_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)

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
        client = _stub_client_returns(patched_mermaid)

        client_mock = tripwire.mock("generate_diagrams:get_agent_client")
        client_mock.returns(client)

        with tripwire:
            result = asyncio.run(
                generate_diagrams.patch_diagram(item.source_path, item.diagram_path, diff)
            )

        assert result == patched_mermaid
        client_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)

    def test_returns_none_on_sdk_failure(self, tmp_path: Path) -> None:
        """patch_diagram returns None when the agent raises, signaling fallback to regen."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        client = _stub_client_raises(RuntimeError("error"))

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

    def test_returns_none_on_timeout(self, tmp_path: Path) -> None:
        """patch_diagram returns None when the agent times out."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        client = _stub_client_raises(asyncio.TimeoutError())

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

    def test_returns_none_on_empty_output(self, tmp_path: Path) -> None:
        """patch_diagram returns None when the agent returns empty output."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        client = _stub_client_returns("")

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

    def test_returns_none_on_cannot_patch(self, tmp_path: Path) -> None:
        """patch_diagram returns None when the agent says CANNOT_PATCH."""
        item = make_source_item(tmp_path)
        write_diagram_with_meta(item, "oldhash")

        client = _stub_client_returns("CANNOT_PATCH")

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

        class _CapturingClient:
            async def run(self, prompt):
                captured_prompts.append(prompt)
                return patched_mermaid

        client_mock = tripwire.mock("generate_diagrams:get_agent_client")
        client_mock.returns(_CapturingClient())

        with tripwire:
            asyncio.run(
                generate_diagrams.patch_diagram(item.source_path, item.diagram_path, diff)
            )

        client_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
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
