"""Tests for spellbook.core.models module."""

from spellbook.core.models import (
    Checkpoint,
    CompletionMarker,
    Manifest,
    Packet,
    Task,
    Track,
)


def test_task_is_dataclass():
    """Task is a dataclass with expected fields."""
    t = Task(id="1", description="test", files=["a.py"], acceptance="passes")
    assert t.id == "1"
    assert t.description == "test"
    assert t.files == ["a.py"]
    assert t.acceptance == "passes"


def test_packet_is_dataclass():
    """Packet is a dataclass with expected fields."""
    p = Packet(
        format_version="1",
        feature="feat",
        track=1,
        worktree="wt",
        branch="br",
        tasks=[],
        body="body",
    )
    assert p.track == 1


def test_track_is_dataclass():
    """Track is a dataclass with expected fields."""
    t = Track(
        id=1,
        name="track1",
        packet="p.json",
        worktree="wt",
        branch="br",
        status="pending",
        depends_on=[],
    )
    assert t.status == "pending"
    assert t.checkpoint is None


def test_manifest_is_dataclass():
    """Manifest is a dataclass."""
    assert hasattr(Manifest, "__dataclass_fields__")


def test_checkpoint_is_dataclass():
    """Checkpoint is a dataclass."""
    assert hasattr(Checkpoint, "__dataclass_fields__")


def test_completion_marker_is_dataclass():
    """CompletionMarker is a dataclass."""
    assert hasattr(CompletionMarker, "__dataclass_fields__")
