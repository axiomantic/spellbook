#!/usr/bin/env python3
"""Pre-commit hook: version metadata must agree across the tree.

Two independent failures shipped 16 releases with empty notes and left
extensions/gemini/gemini-extension.json pinned at 0.1.0 while .version read
0.89.0. Both were detectable: installer.version.validate_version_consistency
already checked the manifest, and nothing called it. This script is that
caller, plus the CHANGELOG check the release workflow needs to have already
passed by the time .version reaches main.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from installer.version import read_version, validate_version_consistency  # noqa: E402

CHANGELOG_PATH = REPO_ROOT / "CHANGELOG.md"


def check_changelog_heading(version: str) -> list[str]:
    """Require a ``## [<version>]`` heading once .version names a release.

    The release workflow extracts notes by matching this heading. It now fails
    when the heading is absent, but that failure lands after merge to main.
    Catching it here keeps the red build from being the first signal.
    """
    if not CHANGELOG_PATH.exists():
        return [f"CHANGELOG.md not found at {CHANGELOG_PATH}"]

    heading = f"## [{version}]"
    for line in CHANGELOG_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith(heading):
            return []
    return [
        f"CHANGELOG.md has no '{heading}' section for the version in .version. "
        f"The release workflow extracts notes by matching that heading and will "
        f"fail the release without it."
    ]


def main() -> int:
    version = read_version(REPO_ROOT / ".version")

    issues = validate_version_consistency(REPO_ROOT)
    issues.extend(check_changelog_heading(version))

    if issues:
        print(f"Version consistency check FAILED (.version = {version})\n")
        for issue in issues:
            print(f"  - {issue}")
        print(
            "\nUpdate the offending file, or run installer.version.sync_version_to_files "
            "to propagate .version across the tree."
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
