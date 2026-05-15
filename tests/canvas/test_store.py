"""Tests for ``spellbook.canvas.store``.

Covers: name regex, canvas root resolution, atomic page write, atomic meta
write, full canvas read (happy + missing-meta regeneration), and path-
traversal rejection.
"""

from __future__ import annotations

import json
import os

import pytest

from spellbook.canvas import store


def test_resolve_canvas_root(canvas_tmp_root):
    """Monkeypatched ``_resolve_canvas_root`` returns the patched path."""
    assert store._resolve_canvas_root() == canvas_tmp_root


@pytest.mark.parametrize(
    "name",
    [
        "foo",
        "foo-bar",
        "foo_bar_1",
        "a",
        "a" * 64,
        "0abc",
        "1",
    ],
)
def test_name_regex_valid(name):
    assert store.NAME_RE.match(name) is not None


@pytest.mark.parametrize(
    "name",
    [
        "",
        "-foo",
        "_foo",
        "FOO",
        "Foo",
        "foo/bar",
        "foo bar",
        "a" * 65,
        "..",
        "../etc",
        ".hidden",
    ],
)
def test_name_regex_invalid(name):
    assert store.NAME_RE.match(name) is None


def test_atomic_write_page_happy(canvas_tmp_root):
    """``write_page`` produces ``pages/index.md`` with exact content."""
    store.open_canvas("foo")
    n = store.write_page("foo", "hello world")
    page_path = os.path.join(canvas_tmp_root, "foo", "pages", "index.md")
    assert os.path.isfile(page_path)
    with open(page_path, "r", encoding="utf-8") as f:
        assert f.read() == "hello world"
    assert n == len(b"hello world")


def test_atomic_write_page_partial_recovery(canvas_tmp_root, monkeypatch):
    """If ``os.replace`` fails mid-write, no partial file remains.

    The tempfile pattern guarantees: either the final path holds the new
    bytes, or it holds the old bytes (here: empty). No half-written file
    is visible at the final path; the tmp file is cleaned up.
    """
    store.open_canvas("foo")
    # Initial state: empty index.md from open_canvas
    page_path = os.path.join(canvas_tmp_root, "foo", "pages", "index.md")
    assert os.path.isfile(page_path)
    original_replace = os.replace

    def boom(src, dst):
        raise OSError("simulated rename failure")

    monkeypatch.setattr("spellbook.canvas.store.os.replace", boom)

    with pytest.raises(OSError, match="simulated rename failure"):
        store.write_page("foo", "new content")

    # The original (empty) page is intact; no .tmp- files left behind.
    with open(page_path, "r", encoding="utf-8") as f:
        assert f.read() == ""
    leftover_tmp = [
        n
        for n in os.listdir(os.path.dirname(page_path))
        if n.startswith(".tmp-")
    ]
    assert leftover_tmp == [], f"Stray tmp files: {leftover_tmp}"
    # Restore for cleanup
    monkeypatch.setattr("spellbook.canvas.store.os.replace", original_replace)


def test_atomic_write_meta(canvas_tmp_root):
    """``write_meta`` produces ``meta.json`` parsable back into ``CanvasMeta``."""
    meta, _, _ = store.open_canvas("foo", title="Foo Title")
    meta_path = os.path.join(canvas_tmp_root, "foo", "meta.json")
    assert os.path.isfile(meta_path)
    with open(meta_path, "r", encoding="utf-8") as f:
        parsed = json.load(f)
    assert parsed["name"] == "foo"
    assert parsed["title"] == "Foo Title"
    assert parsed["closed"] is False
    assert parsed["schema_version"] == 1
    # Round-trip
    back = store.CanvasMeta.model_validate(parsed)
    assert back.name == "foo"
    assert back.title == "Foo Title"


def test_read_canvas_happy(canvas_tmp_root):
    """``read_canvas`` returns the full content dict for a populated canvas."""
    store.open_canvas("bar", title="Bar")
    store.write_page("bar", "# hello")
    result = store.read_canvas("bar")
    assert result is not None
    assert result["name"] == "bar"
    assert result["title"] == "Bar"
    assert result["closed"] is False
    assert result["page"] == "index.md"
    assert result["content"] == "# hello"
    assert result["bytes"] == len(b"# hello")
    assert "created_at" in result
    assert "last_updated" in result


def test_read_canvas_missing_meta_regenerates(canvas_tmp_root):
    """If ``meta.json`` is missing, ``read_canvas`` regenerates it with defaults."""
    canvas_dir = os.path.join(canvas_tmp_root, "baz")
    os.makedirs(os.path.join(canvas_dir, "pages"))
    page_path = os.path.join(canvas_dir, "pages", "index.md")
    with open(page_path, "w", encoding="utf-8") as f:
        f.write("orphaned content")

    result = store.read_canvas("baz")
    assert result is not None
    assert result["name"] == "baz"
    assert result["title"] == "baz"  # defaulted to name
    assert result["content"] == "orphaned content"
    assert result["closed"] is False
    # meta.json should now exist
    assert os.path.isfile(os.path.join(canvas_dir, "meta.json"))


def test_read_canvas_path_traversal_rejected(canvas_tmp_root):
    """``read_canvas('../etc/passwd')`` returns ``None`` before any FS access."""
    result = store.read_canvas("../etc/passwd")
    assert result is None


def test_read_canvas_missing_dir_returns_none(canvas_tmp_root):
    assert store.read_canvas("does-not-exist") is None


def test_open_canvas_idempotent(canvas_tmp_root):
    """Calling ``open_canvas`` twice on the same name does not duplicate state."""
    meta1, created1, reopened1 = store.open_canvas("foo")
    meta2, created2, reopened2 = store.open_canvas("foo")
    assert created1 is True and reopened1 is False
    assert created2 is False and reopened2 is False
    assert meta1.created_at == meta2.created_at


def test_open_canvas_reopens_closed(canvas_tmp_root):
    store.open_canvas("foo")
    store.close_canvas("foo")
    meta, created, reopened = store.open_canvas("foo")
    assert created is False
    assert reopened is True
    assert meta.closed is False


def test_open_canvas_invalid_name(canvas_tmp_root):
    with pytest.raises(ValueError):
        store.open_canvas("../etc")


def test_list_canvases_empty(canvas_tmp_root):
    assert store.list_canvases() == []


def test_list_canvases_sorted_by_last_updated_desc(canvas_tmp_root):
    """Newer ``last_updated`` comes first.

    ``write_page`` is page-only; ``canvas_write`` (MCP layer, A.3) bumps
    ``meta.last_updated``. Here we simulate the MCP layer by writing
    explicit ``last_updated`` timestamps directly, so the assertion does
    not rely on wall-clock spacing between ``open_canvas`` calls (slow
    CI can produce identical timestamps within a millisecond resolution
    grid).
    """
    from datetime import datetime, timedelta, timezone

    meta_alpha, _, _ = store.open_canvas("alpha")
    meta_beta, _, _ = store.open_canvas("beta")
    base = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    # beta is older; alpha is bumped to be newer.
    store.write_meta(
        "beta", meta_beta.model_copy(update={"last_updated": base})
    )
    store.write_meta(
        "alpha",
        meta_alpha.model_copy(update={"last_updated": base + timedelta(seconds=1)}),
    )
    items = store.list_canvases()
    names = [i["name"] for i in items]
    assert names == ["alpha", "beta"]


def test_close_canvas(canvas_tmp_root):
    store.open_canvas("foo")
    closed_meta = store.close_canvas("foo")
    assert closed_meta is not None
    assert closed_meta.closed is True


def test_close_canvas_not_found(canvas_tmp_root):
    assert store.close_canvas("nope") is None


def test_write_page_invalid_name(canvas_tmp_root):
    with pytest.raises(ValueError):
        store.write_page("../etc", "x")


def test_write_page_oversize(canvas_tmp_root, monkeypatch):
    """``write_page`` honours ``_max_page_bytes`` read at call time."""
    monkeypatch.setenv("SPELLBOOK_CANVAS_MAX_PAGE_BYTES", "10")
    store.open_canvas("foo")
    with pytest.raises(ValueError, match="page_too_large"):
        store.write_page("foo", "0123456789X")  # 11 bytes


def test_max_page_bytes_non_integer_falls_back_to_default(monkeypatch, caplog):
    """Malformed env var is logged and ignored, not raised."""
    monkeypatch.setenv("SPELLBOOK_CANVAS_MAX_PAGE_BYTES", "not-an-int")
    with caplog.at_level("WARNING"):
        result = store._max_page_bytes()
    assert result == 1 * 1024 * 1024
    assert any("not-an-int" in r.message for r in caplog.records)


def test_max_page_bytes_non_positive_falls_back_to_default(monkeypatch, caplog):
    """Zero or negative env var is logged and ignored."""
    monkeypatch.setenv("SPELLBOOK_CANVAS_MAX_PAGE_BYTES", "0")
    with caplog.at_level("WARNING"):
        result = store._max_page_bytes()
    assert result == 1 * 1024 * 1024
    assert any("must be positive" in r.message for r in caplog.records)


def test_max_page_bytes_unset_returns_default(monkeypatch):
    """Unset env var returns the 1 MB default."""
    monkeypatch.delenv("SPELLBOOK_CANVAS_MAX_PAGE_BYTES", raising=False)
    assert store._max_page_bytes() == 1 * 1024 * 1024


def test_write_page_non_index(canvas_tmp_root):
    """MVP only accepts ``index.md``."""
    store.open_canvas("foo")
    with pytest.raises(ValueError, match="invalid_content"):
        store.write_page("foo", "x", page="other.md")


def test_read_canvas_corrupt_meta_regenerated(canvas_tmp_root):
    """Corrupt ``meta.json`` is replaced with a default-derived value."""
    store.open_canvas("foo")
    canvas_dir = os.path.join(canvas_tmp_root, "foo")
    with open(os.path.join(canvas_dir, "meta.json"), "w") as f:
        f.write("not json {")
    result = store.read_canvas("foo")
    assert result is not None
    assert result["name"] == "foo"
    assert result["title"] == "foo"


def test_list_canvases_skips_non_dirs_and_invalid_names(canvas_tmp_root):
    """Files at the root and badly-named subdirs are ignored."""
    store.open_canvas("good")
    # Stray file
    with open(os.path.join(canvas_tmp_root, "stray.txt"), "w") as f:
        f.write("noise")
    # Bad-name directory
    os.makedirs(os.path.join(canvas_tmp_root, "BadName"))
    items = store.list_canvases()
    assert [i["name"] for i in items] == ["good"]


def test_list_canvases_regenerates_missing_meta(canvas_tmp_root):
    """Directories with no meta.json get a synthesized entry."""
    canvas_dir = os.path.join(canvas_tmp_root, "orphan")
    os.makedirs(os.path.join(canvas_dir, "pages"))
    with open(os.path.join(canvas_dir, "pages", "index.md"), "w") as f:
        f.write("x")
    items = store.list_canvases()
    names = [i["name"] for i in items]
    assert "orphan" in names
    # meta.json should now be on disk.
    assert os.path.isfile(os.path.join(canvas_dir, "meta.json"))


def test_list_canvases_root_missing(monkeypatch, tmp_path):
    """When the canvas root doesn't exist, list returns []."""
    monkeypatch.setattr(
        "spellbook.canvas.store._resolve_canvas_root",
        lambda: str(tmp_path / "no-such-dir"),
    )
    assert store.list_canvases() == []


def test_close_canvas_invalid_name(canvas_tmp_root):
    assert store.close_canvas("../etc") is None


def test_close_canvas_corrupt_meta(canvas_tmp_root):
    """``close_canvas`` on corrupt meta returns ``None``."""
    store.open_canvas("foo")
    canvas_dir = os.path.join(canvas_tmp_root, "foo")
    with open(os.path.join(canvas_dir, "meta.json"), "w") as f:
        f.write("garbage")
    assert store.close_canvas("foo") is None


def test_open_canvas_with_corrupt_meta_treated_as_regenerate(canvas_tmp_root):
    """Existing dir + corrupt meta: open_canvas regenerates and reports created=False."""
    store.open_canvas("foo")
    canvas_dir = os.path.join(canvas_tmp_root, "foo")
    with open(os.path.join(canvas_dir, "meta.json"), "w") as f:
        f.write("garbage")
    meta, created, reopened = store.open_canvas("foo")
    assert created is False
    assert reopened is False
    assert meta.title == "foo"


def test_default_canvas_root_is_under_home():
    """The unmonkeypatched root points under the user's home dir."""
    import os.path
    root = store._resolve_canvas_root()
    assert root.endswith(os.path.join(".local", "spellbook", "canvas"))
