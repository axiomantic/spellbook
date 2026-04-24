"""Integration tests for ``forge_roundtable_convene_local`` MCP tool.

The tool mirrors ``forge_roundtable_convene`` but EXECUTES the dialogue
against the user-configured worker LLM and parses the response locally.
On worker error it returns the convene result with a ``worker_llm_error``
key set to a ``<worker-llm-error>`` block so the orchestrator can fall
back to the non-local variant. On a happy path it forwards the parsed
verdicts + dialogue + raw response back to the caller.

See impl plan Task D6; design §5.4.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest


@pytest.fixture
def tmp_artifact(tmp_path: Path) -> Path:
    """Write a minimal artifact that ``roundtable_convene`` can read."""
    p = tmp_path / "design.md"
    p.write_text(
        "# Design: Demo Feature\n\nThis is the demo design doc.\n",
        encoding="utf-8",
    )
    return p


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_roundtable_local_happy_path(
    worker_llm_transport,
    worker_llm_config,
    tmp_artifact,
):
    """Worker returns a valid multi-voice response; tool returns parsed
    verdicts, preserves the dialogue, and includes the raw response.
    """
    worker_llm_transport(
        [
            type(
                "S",
                (),
                {
                    "status": 200,
                    "body": {
                        "choices": [
                            {
                                "message": {
                                    "content": (
                                        "**Magician**: ok\n"
                                        "Verdict: APPROVE\n\n"
                                        "**Priestess**: ok\n"
                                        "Verdict: APPROVE\n\n"
                                        "## Summary\nall good"
                                    )
                                }
                            }
                        ]
                    },
                    "delay_s": 0.0,
                    "raise_on_send": None,
                },
            )()
        ]
    )

    from spellbook.mcp.tools.forged import forge_roundtable_convene_local

    out = await forge_roundtable_convene_local(
        feature_name="demo",
        stage="DESIGN",
        artifact_path=str(tmp_artifact),
        gate="design_review",
        archetypes=["magician", "priestess"],
    )

    assert "worker_llm_error" not in out, out
    assert "verdicts" in out
    assert "dialogue" in out
    assert "worker_llm_raw_response" in out
    assert out["worker_llm_raw_response"].startswith("**Magician**")


# ---------------------------------------------------------------------------
# Worker error path (loud-fail: error field set on response)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_roundtable_local_unreachable_sets_error_field(
    worker_llm_transport,
    worker_llm_config,
    tmp_artifact,
):
    worker_llm_transport(
        [
            type(
                "S",
                (),
                {
                    "status": 0,
                    "body": "",
                    "delay_s": 0.0,
                    "raise_on_send": httpx.ConnectError("refused"),
                },
            )()
        ]
    )

    from spellbook.mcp.tools.forged import forge_roundtable_convene_local

    out = await forge_roundtable_convene_local(
        feature_name="demo",
        stage="DESIGN",
        artifact_path=str(tmp_artifact),
        gate="design_review",
        archetypes=["magician"],
    )

    assert "worker_llm_error" in out
    assert "<worker-llm-error>" in out["worker_llm_error"]
    assert "WorkerLLMUnreachable" in out["worker_llm_error"]


# ---------------------------------------------------------------------------
# Feature flag off (WorkerLLMNotConfigured)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_roundtable_local_feature_off_returns_error_field(
    worker_llm_transport,
    worker_llm_config,
    tmp_artifact,
):
    worker_llm_config["worker_llm_feature_roundtable"] = False
    # No worker call expected.
    seen = worker_llm_transport([])

    from spellbook.mcp.tools.forged import forge_roundtable_convene_local

    out = await forge_roundtable_convene_local(
        feature_name="demo",
        stage="DESIGN",
        artifact_path=str(tmp_artifact),
        gate="design_review",
        archetypes=["magician"],
    )

    assert "worker_llm_error" in out
    assert "WorkerLLMNotConfigured" in out["worker_llm_error"]
    assert seen == []


# ---------------------------------------------------------------------------
# Convene error (artifact missing) is surfaced unchanged
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_roundtable_local_artifact_missing_returns_convene_error(
    worker_llm_transport,
    worker_llm_config,
    tmp_path,
):
    """If ``roundtable_convene`` reports an artifact error, we must NOT call
    the worker — return the convene result as-is.
    """
    seen = worker_llm_transport([])  # empty: any call raises

    from spellbook.mcp.tools.forged import forge_roundtable_convene_local

    out = await forge_roundtable_convene_local(
        feature_name="demo",
        stage="DESIGN",
        artifact_path=str(tmp_path / "does-not-exist.md"),
        gate="design_review",
        archetypes=["magician"],
    )

    # roundtable_convene signals artifact-not-found via empty dialogue +
    # an ``error`` field carrying a stable prefix. The local variant passes
    # that through without invoking the worker.
    assert seen == []
    # The convene result's error surface is intact — exact-prefix check so
    # a regression that swallows or renames the error surfaces loudly.
    assert out.get("dialogue", "") == ""
    assert "error" in out
    assert out["error"].startswith("Artifact not found")
