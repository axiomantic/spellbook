"""Test content accumulator integration in PostToolUse hook."""
from pathlib import Path

HOOK_FILE = Path(__file__).resolve().parent.parent.parent / "hooks" / "spellbook_hook.py"


def test_hook_has_accumulator_call():
    """Hook must call content accumulator for external content."""
    source = HOOK_FILE.read_text()
    assert "accumulator" in source.lower(), (
        "Hook does not reference content accumulator"
    )


def test_accumulator_is_fire_and_forget():
    """Accumulator write must be fire-and-forget (non-blocking)."""
    source = HOOK_FILE.read_text()
    assert "_fire_and_forget" in source and "accumulator" in source.lower(), (
        "Accumulator write should use _fire_and_forget pattern"
    )
