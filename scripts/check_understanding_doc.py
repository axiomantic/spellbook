#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Mechanically check a Phase 1.5 understanding document.

This replaces the part of the old "13 validation functions" block that was
markdown pseudocode: nothing executed it, so its score was self-reported
while reading as computed. The checks here run against the artifact on
disk. The judgment half of the old list is NOT here -- it stayed in
`commands/feature-discover.md` labelled as self-assessment, because no
script can decide whether a chosen architecture is the right one.

Exit status is the gate: 0 when every check passes, 1 when any fails, 2 on
a usage error such as a missing file.
"""

import argparse
import re
import sys
from pathlib import Path

REQUIRED_SECTIONS = (
    "Feature Essence",
    "Research Summary",
    "Architectural Approach",
    "Scope Definition",
    "Integration Plan",
    "Failure Modes & Edge Cases",
    "Success Criteria",
    "Validated Assumptions",
    "Project Standards",
)

SCOPE_SUBHEADINGS = ("IN SCOPE", "EXPLICITLY OUT OF SCOPE", "MVP DEFINITION")

# "unknown" is deliberately absent: it appears legitimately in prose about
# what the feature must handle. The tokens kept here have no honest reading
# inside a document whose gate is "nothing deferred".
DEFERRAL_PATTERNS = (
    re.compile(r"\bTBD\b", re.IGNORECASE),
    re.compile(r"\bto be determined\b", re.IGNORECASE),
    re.compile(r"figure it out later", re.IGNORECASE),
)

UNFILLED_PLACEHOLDER = re.compile(r"^\s*[-*]?\s*\[\s*(\.\.\.|)\s*\]\s*$")


def split_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        heading = re.match(r"^##\s+(.*?)\s*$", line)
        if heading:
            current = heading.group(1)
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return sections


def _match_section(sections: dict[str, list[str]], wanted: str) -> list[str] | None:
    for name, body in sections.items():
        if name.startswith(wanted):
            return body
    return None


def _has_content(body: list[str]) -> bool:
    for line in body:
        stripped = line.strip()
        if not stripped or UNFILLED_PLACEHOLDER.match(line):
            continue
        return True
    return False


def check_required_sections(text: str, sections: dict[str, list[str]]) -> list[str]:
    return [
        f"required section missing: ## {name}"
        for name in REQUIRED_SECTIONS
        if _match_section(sections, name) is None
    ]


def check_sections_non_empty(text: str, sections: dict[str, list[str]]) -> list[str]:
    failures = []
    for name in REQUIRED_SECTIONS:
        body = _match_section(sections, name)
        if body is not None and not _has_content(body):
            failures.append(f"section has no content: ## {name}")
    return failures


def check_scope_boundaries(text: str, sections: dict[str, list[str]]) -> list[str]:
    body = _match_section(sections, "Scope Definition")
    if body is None:
        return ["scope boundaries unverifiable: ## Scope Definition missing"]
    joined = "\n".join(body)
    failures = []
    for sub in SCOPE_SUBHEADINGS:
        index = joined.find(sub)
        if index < 0:
            failures.append(f"scope block missing: {sub}")
            continue
        tail = joined[index + len(sub) :]
        following = tail.split("\n", 1)[1] if "\n" in tail else ""
        for other in SCOPE_SUBHEADINGS:
            cut = following.find(other)
            if cut >= 0:
                following = following[:cut]
        if not _has_content(following.splitlines()):
            failures.append(f"scope block is empty: {sub}")
    return failures


def check_success_criteria_have_thresholds(
    text: str, sections: dict[str, list[str]]
) -> list[str]:
    body = _match_section(sections, "Success Criteria")
    if body is None:
        return ["success criteria unverifiable: ## Success Criteria missing"]
    entries = [
        line.strip()
        for line in body
        if line.strip().startswith(("-", "*")) and not UNFILLED_PLACEHOLDER.match(line)
    ]
    if not entries:
        return ["success criteria list is empty"]
    return [
        f"success criterion carries no threshold after ':' -- {entry}"
        for entry in entries
        if not entry.partition(":")[2].strip()
    ]


def check_no_deferrals(text: str, sections: dict[str, list[str]]) -> list[str]:
    failures = []
    for number, line in enumerate(text.splitlines(), start=1):
        for pattern in DEFERRAL_PATTERNS:
            if pattern.search(line):
                failures.append(f"deferral marker on line {number}: {line.strip()}")
    return failures


def check_project_standards_recorded(
    text: str, sections: dict[str, list[str]]
) -> list[str]:
    body = _match_section(sections, "Project Standards")
    if body is None:
        return ["standards sweep unrecorded: ## Project Standards missing"]
    joined = "\n".join(body)

    def field(label: str) -> str:
        found = re.search(rf"^\s*[-*]?\s*{label}\s*:\s*(.*)$", joined, re.MULTILINE)
        return found.group(1).strip() if found else ""

    searched = field("Searched")
    if searched.lower() not in ("yes", "true"):
        return [f"standards sweep not recorded as run (Searched: {searched or 'absent'})"]
    sources = field("Sources found")
    if sources and not UNFILLED_PLACEHOLDER.match(f"[{sources.strip('[]')}]"):
        return []
    none_found = field("None found").lower().startswith(("true", "yes"))
    globs = field("Globs used")
    if none_found and globs and not UNFILLED_PLACEHOLDER.match(f"[{globs.strip('[]')}]"):
        return []
    return [
        "standards sweep result unauditable: needs a non-empty 'Sources found', "
        "or 'None found: true' together with a non-empty 'Globs used'"
    ]


CHECKS = (
    ("required-sections", check_required_sections),
    ("sections-non-empty", check_sections_non_empty),
    ("scope-boundaries", check_scope_boundaries),
    ("success-criteria-thresholds", check_success_criteria_have_thresholds),
    ("no-deferrals", check_no_deferrals),
    ("project-standards-recorded", check_project_standards_recorded),
)


def run_checks(text: str) -> list[tuple[str, list[str]]]:
    sections = split_sections(text)
    return [(name, check(text, sections)) for name, check in CHECKS]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="Path to the understanding document")
    args = parser.parse_args(argv)

    document = Path(args.path)
    if not document.is_file():
        print(f"ERROR: no understanding document at {document}", file=sys.stderr)
        return 2

    results = run_checks(document.read_text(encoding="utf-8"))
    failed = 0
    for name, failures in results:
        print(f"{'FAIL' if failures else 'PASS'}  {name}")
        for failure in failures:
            print(f"        {failure}")
        failed += bool(failures)

    print(f"\n{len(results) - failed}/{len(results)} mechanical checks passed")
    if failed:
        print("Phase 1.5 gate: BLOCKED")
        return 1
    print("Phase 1.5 gate: mechanical half satisfied; self-assessment still required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
