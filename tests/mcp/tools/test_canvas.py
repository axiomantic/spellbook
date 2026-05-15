"""Tests for ``spellbook.mcp.tools.canvas``.

Covers all four MCP tools (``canvas_open``, ``canvas_write``,
``canvas_close``, ``canvas_list``) including error codes per design §13
and event publishing per design §6.3.

Uses shared fixtures from ``tests/canvas/conftest.py``.
"""

from __future__ import annotations

import pytest

from tests.canvas.conftest import (  # noqa: F401 — re-export pytest fixtures
    canvas_tmp_root,
    mock_ctx,
    event_subscriber,
)

# Import the wrapped tool functions. FastMCP's ``@mcp.tool()`` decorator
# returns the original callable bound to the registry; the underlying
# Python function is still importable by name.
from spellbook.mcp.tools.canvas import (
    canvas_close,
    canvas_list,
    canvas_open,
    canvas_write,
)


# -----------------------------------------------------------------------
# canvas_open
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_open_new_canvas(canvas_tmp_root, mock_ctx, event_subscriber):
    result = await canvas_open(ctx=mock_ctx, name="design")
    assert result["status"] == "opened"
    assert result["name"] == "design"
    assert result["title"] == "design"
    assert result["created"] is True
    assert result["url"].endswith("/admin/canvas/design")
    # Exactly one event published with created=True, reopened=False.
    assert len(event_subscriber) == 1
    evt = event_subscriber[0]
    assert evt.subsystem.value == "canvas"
    assert evt.event_type == "canvas.opened"
    assert evt.data == {"canvas": "design", "created": True, "reopened": False}


@pytest.mark.asyncio
async def test_open_idempotent_existing(canvas_tmp_root, mock_ctx, event_subscriber):
    await canvas_open(ctx=mock_ctx, name="design")
    event_subscriber.clear()
    result = await canvas_open(ctx=mock_ctx, name="design")
    assert result["status"] == "opened"
    assert result["created"] is False
    assert len(event_subscriber) == 1
    assert event_subscriber[0].data == {
        "canvas": "design",
        "created": False,
        "reopened": False,
    }


@pytest.mark.asyncio
async def test_open_reopen_closed(canvas_tmp_root, mock_ctx, event_subscriber):
    await canvas_open(ctx=mock_ctx, name="design")
    await canvas_close(ctx=mock_ctx, name="design")
    event_subscriber.clear()
    result = await canvas_open(ctx=mock_ctx, name="design")
    assert result["status"] == "opened"
    assert result["created"] is False
    assert len(event_subscriber) == 1
    assert event_subscriber[0].data == {
        "canvas": "design",
        "created": False,
        "reopened": True,
    }


@pytest.mark.asyncio
async def test_open_invalid_name(canvas_tmp_root, mock_ctx, event_subscriber):
    result = await canvas_open(ctx=mock_ctx, name="../etc")
    assert result["code"] == "invalid_name"
    assert "error" in result
    assert event_subscriber == []  # No publish on error.


# -----------------------------------------------------------------------
# canvas_write
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_write_happy(canvas_tmp_root, mock_ctx, event_subscriber):
    await canvas_open(ctx=mock_ctx, name="design")
    event_subscriber.clear()
    result = await canvas_write(ctx=mock_ctx, canvas="design", content="# Hello")
    assert result["status"] == "written"
    assert result["canvas"] == "design"
    assert result["page"] == "index.md"
    assert result["bytes"] == len(b"# Hello")
    assert result["url"].endswith("/admin/canvas/design")
    assert len(event_subscriber) == 1
    evt = event_subscriber[0]
    assert evt.event_type == "canvas.updated"
    assert evt.data == {"canvas": "design", "page": "index.md", "bytes": 7}


@pytest.mark.asyncio
async def test_write_invalid_name(canvas_tmp_root, mock_ctx):
    result = await canvas_write(ctx=mock_ctx, canvas="../etc", content="x")
    assert result["code"] == "invalid_name"


@pytest.mark.asyncio
async def test_write_not_found(canvas_tmp_root, mock_ctx):
    result = await canvas_write(ctx=mock_ctx, canvas="ghost", content="x")
    assert result["code"] == "not_found"


@pytest.mark.asyncio
async def test_write_closed(canvas_tmp_root, mock_ctx):
    await canvas_open(ctx=mock_ctx, name="design")
    await canvas_close(ctx=mock_ctx, name="design")
    result = await canvas_write(ctx=mock_ctx, canvas="design", content="x")
    assert result["code"] == "closed"


@pytest.mark.asyncio
async def test_write_page_too_large(canvas_tmp_root, mock_ctx, monkeypatch):
    monkeypatch.setenv("SPELLBOOK_CANVAS_MAX_PAGE_BYTES", "10")
    await canvas_open(ctx=mock_ctx, name="design")
    result = await canvas_write(
        ctx=mock_ctx, canvas="design", content="0123456789X"
    )
    assert result["code"] == "page_too_large"


@pytest.mark.asyncio
async def test_write_invalid_content(canvas_tmp_root, mock_ctx):
    await canvas_open(ctx=mock_ctx, name="design")
    result = await canvas_write(
        ctx=mock_ctx, canvas="design", content="x", page="other.md"
    )
    assert result["code"] == "invalid_content"


# -----------------------------------------------------------------------
# canvas_close
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_close_happy(canvas_tmp_root, mock_ctx, event_subscriber):
    await canvas_open(ctx=mock_ctx, name="design")
    event_subscriber.clear()
    result = await canvas_close(ctx=mock_ctx, name="design")
    assert result["status"] == "closed"
    assert result["name"] == "design"
    assert len(event_subscriber) == 1
    evt = event_subscriber[0]
    assert evt.event_type == "canvas.closed"
    assert evt.data == {"canvas": "design"}


@pytest.mark.asyncio
async def test_close_not_found(canvas_tmp_root, mock_ctx):
    result = await canvas_close(ctx=mock_ctx, name="ghost")
    assert result["code"] == "not_found"


@pytest.mark.asyncio
async def test_close_invalid_name(canvas_tmp_root, mock_ctx):
    result = await canvas_close(ctx=mock_ctx, name="../etc")
    assert result["code"] == "invalid_name"


# -----------------------------------------------------------------------
# canvas_list
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_empty(canvas_tmp_root, mock_ctx, event_subscriber):
    result = await canvas_list(ctx=mock_ctx)
    assert result == {"canvases": [], "count": 0}
    assert event_subscriber == []  # Read-only: no publish.


@pytest.mark.asyncio
async def test_list_populated_sorted_desc(canvas_tmp_root, mock_ctx):
    import asyncio
    await canvas_open(ctx=mock_ctx, name="alpha")
    await asyncio.sleep(0.01)
    await canvas_open(ctx=mock_ctx, name="beta")
    await asyncio.sleep(0.01)
    # Bump alpha by writing to it.
    await canvas_write(ctx=mock_ctx, canvas="alpha", content="fresh")
    result = await canvas_list(ctx=mock_ctx)
    names = [c["name"] for c in result["canvases"]]
    assert names == ["alpha", "beta"]
    assert result["count"] == 2
    # Each item exposes url for the frontend.
    for item in result["canvases"]:
        assert item["url"].startswith("http://")
        assert item["url"].endswith(f"/admin/canvas/{item['name']}")


@pytest.mark.asyncio
async def test_list_corrupt_meta_regenerated(canvas_tmp_root, mock_ctx):
    import os
    await canvas_open(ctx=mock_ctx, name="design")
    meta_path = os.path.join(canvas_tmp_root, "design", "meta.json")
    with open(meta_path, "w") as f:
        f.write("garbage")
    result = await canvas_list(ctx=mock_ctx)
    names = [c["name"] for c in result["canvases"]]
    assert "design" in names


# -----------------------------------------------------------------------
# Threat-model docstring
# -----------------------------------------------------------------------


def test_threat_model_in_canvas_open_docstring():
    """canvas_open docstring contains the trusted-local-agent paragraph
    verbatim from design §4.1 lines 196-200."""
    doc = canvas_open.__doc__ or ""
    assert "TRUSTED-LOCAL-AGENT" in doc
    assert "trusted-local-agent" in doc.lower()
    assert "rehype-raw" in doc
    assert "session-takeover" in doc


def test_threat_model_in_canvas_write_docstring():
    """canvas_write docstring contains the trusted-local-agent paragraph
    verbatim from design §4.2 lines 278-281."""
    doc = canvas_write.__doc__ or ""
    assert "TRUSTED-LOCAL-AGENT" in doc
    assert "trusted-local-agent" in doc.lower()
    assert "rehype-raw" in doc


# -----------------------------------------------------------------------
# Publish error resilience
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_failure_does_not_break_tool(
    canvas_tmp_root, mock_ctx, monkeypatch
):
    """If event_bus.publish raises, the tool still returns success."""
    from spellbook.admin.events import event_bus

    async def _boom(event):
        raise RuntimeError("simulated publish failure")

    monkeypatch.setattr(event_bus, "publish", _boom)
    result = await canvas_open(ctx=mock_ctx, name="design")
    assert result["status"] == "opened"
