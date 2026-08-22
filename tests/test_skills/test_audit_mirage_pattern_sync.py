"""Guard against pattern drift between the audit-mirage analyze and report commands.

``commands/audit-mirage-analyze.md`` DEFINES the green mirage patterns.
``commands/audit-mirage-report.md`` gives the report template a slot per pattern:
a ``pattern_<n>_*`` key in the machine-parseable YAML block, and a
``|-- Pattern <n> (...)`` line in the human-readable summary.

A pattern defined in analyze with no slot in report has nowhere to go: the finding
is dropped while the report still looks complete. That is the failure this file
makes loud. The expected set is DERIVED from the analyze headings, so adding a
pattern there turns this test red until report gains its slots.
"""
from __future__ import annotations

import re
from pathlib import Path


COMMANDS = Path(__file__).resolve().parents[2] / "commands"
ANALYZE_PATH = COMMANDS / "audit-mirage-analyze.md"
REPORT_PATH = COMMANDS / "audit-mirage-report.md"

_ANALYZE_HEADING = re.compile(r"^#{2,4}\s+Pattern\s+(\d+)\s*:", re.MULTILINE)
_REPORT_YAML_KEY = re.compile(r"^\s*pattern_(\d+)_\w+\s*:", re.MULTILINE)
_REPORT_SUMMARY_LINE = re.compile(r"^\|--\s*Pattern\s+(\d+)\s*\(", re.MULTILINE)


def _indices(pattern: re.Pattern[str], path: Path) -> set[int]:
    return {int(m.group(1)) for m in pattern.finditer(path.read_text())}


def test_analyze_defines_a_contiguous_pattern_range() -> None:
    defined = _indices(_ANALYZE_HEADING, ANALYZE_PATH)
    assert defined, f"no '### Pattern N:' headings found in {ANALYZE_PATH}"
    assert defined == set(range(1, max(defined) + 1)), (
        f"pattern numbering in {ANALYZE_PATH.name} has gaps or duplicates: "
        f"{sorted(defined)}"
    )


def test_report_yaml_block_has_a_slot_for_every_defined_pattern() -> None:
    defined = _indices(_ANALYZE_HEADING, ANALYZE_PATH)
    in_yaml = _indices(_REPORT_YAML_KEY, REPORT_PATH)
    assert in_yaml == defined, (
        f"patterns_found keys in {REPORT_PATH.name} do not match the patterns "
        f"defined in {ANALYZE_PATH.name}. Missing: {sorted(defined - in_yaml)}; "
        f"unknown: {sorted(in_yaml - defined)}"
    )


def test_report_summary_has_a_line_for_every_defined_pattern() -> None:
    defined = _indices(_ANALYZE_HEADING, ANALYZE_PATH)
    in_summary = _indices(_REPORT_SUMMARY_LINE, REPORT_PATH)
    assert in_summary == defined, (
        f"human-readable Patterns list in {REPORT_PATH.name} does not match the "
        f"patterns defined in {ANALYZE_PATH.name}. "
        f"Missing: {sorted(defined - in_summary)}; "
        f"unknown: {sorted(in_summary - defined)}"
    )
