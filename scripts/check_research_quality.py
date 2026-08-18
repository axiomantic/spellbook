#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Mechanically check a Phase 1 research-findings artifact.

This replaces the part of the old "Research Quality Score" block that was
TypeScript pseudocode in markdown: nothing executed it, so the percentage it
printed was self-reported while reading as computed. The checks here run
against the findings JSON on disk. The judgment half is NOT here -- it stayed
in `commands/feature-research.md` labelled as self-assessment, because no
script can decide whether an answer deserves HIGH confidence.

This mirrors `scripts/check_understanding_doc.py`, the Phase 1.5 equivalent.

Exit status is the gate: 0 when every check passes, 1 when any fails, 2 on a
usage error such as a missing or unparseable file.
"""

import argparse
import json
import re
import sys
from pathlib import Path

CONFIDENCE_LEVELS = ("HIGH", "MEDIUM", "LOW", "UNKNOWN")
UNFLAGGED_LEVELS = ("LOW", "UNKNOWN")
FINDING_FIELDS = ("question", "answer", "confidence", "evidence", "ambiguities")

# "unknown" is deliberately absent: UNKNOWN is a legitimate confidence value
# in this artifact. The tokens kept here have no honest reading in an answer.
DEFERRAL_PATTERNS = (
    re.compile(r"\bTBD\b", re.IGNORECASE),
    re.compile(r"\bto be determined\b", re.IGNORECASE),
    re.compile(r"figure it out later", re.IGNORECASE),
)

PLACEHOLDER = re.compile(r"^\s*(\[\s*(\.\.\.|)\s*\]|\.\.\.)\s*$")


def _blank(value: object) -> bool:
    return not isinstance(value, str) or not value.strip() or bool(PLACEHOLDER.match(value))


def _findings(data: dict) -> list:
    found = data.get("findings")
    return found if isinstance(found, list) else []


def _label(index: int, finding: object) -> str:
    if isinstance(finding, dict) and isinstance(finding.get("question"), str):
        return f"finding {index} ({finding['question'][:60]})"
    return f"finding {index}"


def check_schema_shape(data: dict) -> list[str]:
    failures = []
    for key, kind in (("findings", list), ("patterns_discovered", list), ("unknowns", list)):
        if key not in data:
            failures.append(f"top-level key missing: {key}")
        elif not isinstance(data[key], kind):
            failures.append(f"top-level key is not a list: {key}")
    if isinstance(data.get("findings"), list) and not data["findings"]:
        failures.append("findings list is empty: research produced no answers")
    return failures


def check_finding_fields(data: dict) -> list[str]:
    failures = []
    for index, finding in enumerate(_findings(data), start=1):
        if not isinstance(finding, dict):
            failures.append(f"{_label(index, finding)}: not an object")
            continue
        for field in FINDING_FIELDS:
            if field not in finding:
                failures.append(f"{_label(index, finding)}: field missing -- {field}")
        for field in ("question", "answer"):
            if field in finding and _blank(finding[field]):
                failures.append(f"{_label(index, finding)}: field is blank -- {field}")
        confidence = finding.get("confidence")
        if confidence is not None and confidence not in CONFIDENCE_LEVELS:
            failures.append(
                f"{_label(index, finding)}: confidence not one of "
                f"{'/'.join(CONFIDENCE_LEVELS)} -- {confidence!r}"
            )
        for field in ("evidence", "ambiguities"):
            if field in finding and not isinstance(finding[field], list):
                failures.append(f"{_label(index, finding)}: field is not a list -- {field}")
    return failures


def check_evidence_present(data: dict) -> list[str]:
    """Every answerable finding cites at least one non-blank evidence entry."""
    failures = []
    for index, finding in enumerate(_findings(data), start=1):
        if not isinstance(finding, dict) or finding.get("confidence") == "UNKNOWN":
            continue
        evidence = finding.get("evidence")
        if not isinstance(evidence, list):
            continue
        cited = [item for item in evidence if not _blank(item)]
        if not cited:
            failures.append(
                f"{_label(index, finding)}: confidence "
                f"{finding.get('confidence')} with no evidence entry"
            )
    return failures


def check_unknowns_flagged(data: dict) -> list[str]:
    """Every LOW/UNKNOWN finding names its question in the `unknowns` list."""
    unknowns = data.get("unknowns")
    if not isinstance(unknowns, list):
        return ["unknowns unverifiable: top-level `unknowns` is not a list"]
    blob = "\n".join(item for item in unknowns if isinstance(item, str)).lower()
    failures = []
    for index, finding in enumerate(_findings(data), start=1):
        if not isinstance(finding, dict) or finding.get("confidence") not in UNFLAGGED_LEVELS:
            continue
        question = finding.get("question")
        if _blank(question):
            continue
        stem = question.strip().rstrip("?").lower()
        if stem not in blob:
            failures.append(
                f"{_label(index, finding)}: confidence "
                f"{finding.get('confidence')} but the question is absent from `unknowns`"
            )
    return failures


def check_patterns_sourced(data: dict) -> list[str]:
    """Every discovered pattern names the files it was read from."""
    patterns = data.get("patterns_discovered")
    if not isinstance(patterns, list):
        return []
    failures = []
    for index, pattern in enumerate(patterns, start=1):
        if not isinstance(pattern, dict):
            failures.append(f"pattern {index}: not an object")
            continue
        for field in ("name", "description"):
            if _blank(pattern.get(field)):
                failures.append(f"pattern {index}: field missing or blank -- {field}")
        files = pattern.get("files")
        if not isinstance(files, list) or not [f for f in files if not _blank(f)]:
            failures.append(f"pattern {index}: no file references")
    return failures


def check_no_deferrals(data: dict) -> list[str]:
    text = json.dumps(data, indent=2)
    failures = []
    for number, line in enumerate(text.splitlines(), start=1):
        for pattern in DEFERRAL_PATTERNS:
            if pattern.search(line):
                failures.append(f"deferral marker on line {number}: {line.strip()}")
    return failures


def check_standards_sweep_recorded(data: dict) -> list[str]:
    """The §1.2.5 governance sweep result is present and auditable."""
    standards = data.get("project_standards")
    if not isinstance(standards, dict):
        return ["standards sweep unrecorded: `project_standards` object missing"]
    if standards.get("searched") is not True:
        return [f"standards sweep not recorded as run (searched: {standards.get('searched')!r})"]
    sources = standards.get("sources")
    if isinstance(sources, list) and sources:
        return []
    globs = standards.get("search_globs_used")
    if standards.get("none_found") is True and isinstance(globs, list) and globs:
        return []
    return [
        "standards sweep result unauditable: needs a non-empty `sources`, or "
        "`none_found: true` together with a non-empty `search_globs_used`"
    ]


CHECKS = (
    ("schema-shape", check_schema_shape),
    ("finding-fields", check_finding_fields),
    ("evidence-present", check_evidence_present),
    ("unknowns-flagged", check_unknowns_flagged),
    ("patterns-sourced", check_patterns_sourced),
    ("no-deferrals", check_no_deferrals),
    ("standards-sweep-recorded", check_standards_sweep_recorded),
)


def run_checks(data: dict) -> list[tuple[str, list[str]]]:
    return [(name, check(data)) for name, check in CHECKS]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="Path to the research findings JSON")
    args = parser.parse_args(argv)

    document = Path(args.path)
    if not document.is_file():
        print(f"ERROR: no research findings at {document}", file=sys.stderr)
        return 2
    try:
        data = json.loads(document.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        print(f"ERROR: {document} is not valid JSON: {error}", file=sys.stderr)
        return 2
    if not isinstance(data, dict):
        print(f"ERROR: {document} does not hold a JSON object", file=sys.stderr)
        return 2

    results = run_checks(data)
    failed = 0
    for name, failures in results:
        print(f"{'FAIL' if failures else 'PASS'}  {name}")
        for failure in failures:
            print(f"        {failure}")
        failed += bool(failures)

    print(f"\n{len(results) - failed}/{len(results)} mechanical checks passed")
    if failed:
        print("Phase 1 gate: BLOCKED")
        return 1
    print("Phase 1 gate: mechanical half satisfied; self-assessment still required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
