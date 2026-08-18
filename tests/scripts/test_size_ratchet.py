"""Behavioural tests for the per-file size ratchet in validate_schemas.py.

The ratchet replaced a blanket size exemption. Its dangerous failure mode is
not a false alarm but a silent one: a ratchet that records a LARGER ceiling
permits exactly the unbounded growth it exists to stop. Every test here pins
a rejection against the same input repaired, and the monotonicity tests drive
`compute_ceilings` with a grown file to prove no code path raises a ceiling.

Stated blind spot: these tests say nothing about whether the RECORDED
ceilings in `scripts/size_ceilings.json` are the right sizes. They prove the
mechanism cannot loosen on its own.
"""

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "validate_schemas.py"
CEILINGS_FILE = REPO_ROOT / "scripts" / "size_ceilings.json"

_spec = importlib.util.spec_from_file_location("validate_schemas", SCRIPT)
assert _spec and _spec.loader
vs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vs)


CEILINGS = {"skills/develop/SKILL.md": {"bytes": 200, "lines": 4}}


def _fake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str) -> Path:
    """Write `body` at a path that maps to the ratcheted repo-relative key."""
    target = tmp_path / "skills" / "develop" / "SKILL.md"
    target.parent.mkdir(parents=True)
    target.write_text(body, encoding="utf-8")
    monkeypatch.setattr(vs, "repo_relative_key", lambda p: "skills/develop/SKILL.md")
    return target


def test_file_over_its_byte_ceiling_is_rejected(tmp_path, monkeypatch):
    body = "x" * 250 + "\n"
    target = _fake(tmp_path, monkeypatch, body)
    errors: list[str] = []
    vs.check_truncation_limits(body, errors, target, CEILINGS)
    assert any("Exceeds recorded size ceiling" in e for e in errors)
    assert any("over by 51 bytes" in e for e in errors)


def test_same_file_under_its_ceiling_is_accepted(tmp_path, monkeypatch):
    body = "x" * 100 + "\n"
    target = _fake(tmp_path, monkeypatch, body)
    errors: list[str] = []
    vs.check_truncation_limits(body, errors, target, CEILINGS)
    assert errors == []


def test_file_over_its_line_ceiling_is_rejected(tmp_path, monkeypatch):
    body = "a\n" * 9
    target = _fake(tmp_path, monkeypatch, body)
    errors: list[str] = []
    vs.check_truncation_limits(body, errors, target, CEILINGS)
    assert any("Exceeds recorded line ceiling" in e for e in errors)


def test_ceiling_supersedes_the_global_limit(tmp_path, monkeypatch):
    """A ratcheted file over MAX_BYTES but under its ceiling passes.

    This is the case the old blanket exemption served, now bounded.
    """
    body = "x" * (vs.MAX_BYTES + 10_000) + "\n"
    target = _fake(tmp_path, monkeypatch, body)
    ceilings = {"skills/develop/SKILL.md": {"bytes": len(body.encode()), "lines": 5}}
    errors: list[str] = []
    vs.check_truncation_limits(body, errors, target, ceilings)
    assert errors == []


def test_unratcheted_file_still_hits_the_global_limit(tmp_path, monkeypatch):
    body = "x" * (vs.MAX_BYTES + 1) + "\n"
    target = _fake(tmp_path, monkeypatch, body)
    errors: list[str] = []
    vs.check_truncation_limits(body, errors, target, {})
    assert any("Exceeds size limit" in e for e in errors)


def test_growth_cannot_raise_a_ceiling():
    grown = {"skills/develop/SKILL.md": (10_000, 500)}
    assert vs.compute_ceilings(grown, CEILINGS) == CEILINGS


def test_shrinking_lowers_the_ceiling():
    shrunk = {"skills/develop/SKILL.md": (120, 3)}
    result = vs.compute_ceilings(shrunk, CEILINGS)
    assert result == {"skills/develop/SKILL.md": {"bytes": 120, "lines": 3}}


def test_bytes_and_lines_ratchet_independently():
    """A file that loses bytes but gains lines lowers only the byte ceiling."""
    mixed = {"skills/develop/SKILL.md": (120, 99)}
    result = vs.compute_ceilings(mixed, CEILINGS)
    assert result == {"skills/develop/SKILL.md": {"bytes": 120, "lines": 4}}


def test_small_files_are_not_ratcheted():
    measured = {"commands/tiny.md": (100, 5)}
    assert vs.compute_ceilings(measured, {}) == {}


def test_files_at_the_threshold_gain_a_ceiling():
    measured = {"commands/big.md": (vs.RATCHET_THRESHOLD_BYTES, 10)}
    result = vs.compute_ceilings(measured, {})
    assert result == {"commands/big.md": {"bytes": vs.RATCHET_THRESHOLD_BYTES, "lines": 10}}


def test_deleted_files_lose_their_entry():
    assert vs.compute_ceilings({}, CEILINGS) == {}


def test_over_limit_ceiling_without_rationale_is_rejected(tmp_path):
    path = tmp_path / "size_ceilings.json"
    path.write_text(
        json.dumps({"ceilings": {"commands/sneaky.md": {"bytes": vs.MAX_BYTES + 1, "lines": 10}}}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="OVER_LIMIT_RATIONALE"):
        vs.load_ceilings(path)


def test_over_limit_ceiling_with_rationale_loads(tmp_path):
    path = tmp_path / "size_ceilings.json"
    key = next(iter(vs.OVER_LIMIT_RATIONALE))
    path.write_text(
        json.dumps({"ceilings": {key: {"bytes": vs.MAX_BYTES + 1, "lines": 10}}}),
        encoding="utf-8",
    )
    assert vs.load_ceilings(path)[key]["bytes"] == vs.MAX_BYTES + 1


def test_recorded_ceilings_are_currently_satisfied():
    """The checked-in ceilings hold for the checked-in files."""
    over = []
    for key, entry in vs.load_ceilings(CEILINGS_FILE).items():
        target = REPO_ROOT / key
        if not target.is_file():
            continue
        text = target.read_text(encoding="utf-8")
        if len(text.encode("utf-8")) > entry["bytes"] or len(text.splitlines()) > entry["lines"]:
            over.append(key)
    assert over == []
