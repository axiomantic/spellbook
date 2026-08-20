#!/usr/bin/env python3
"""Pre-commit hook: version metadata must agree across the tree.

Two independent failures shipped 16 releases with empty notes and left
extensions/gemini/gemini-extension.json pinned at 0.1.0 while .version read
0.89.0. Both were detectable: installer.version.validate_version_consistency
already checked the manifest, and nothing called it. This script is that
caller, plus the CHANGELOG check the release workflow needs to have already
passed by the time .version reaches main.

``--fix`` propagates .version into the manifests it owns. It is never run by
the pre-commit hook and never by any automatic path: a hook that silently
rewrites files turns a drift report into a drift eraser. A human types it.
"""

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from installer.version import (  # noqa: E402
    read_version,
    sync_version_to_files,
    validate_version_consistency,
)

CHANGELOG_PATH = REPO_ROOT / "CHANGELOG.md"

# Named once so the failure message and the documentation cannot drift apart.
REPAIR_COMMAND = "uv run scripts/check_version_consistency.py --fix"


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


def report(version: str, manifest_issues: list[str], changelog_issues: list[str]) -> None:
    print(f"Version consistency check FAILED (.version = {version})\n")
    for issue in manifest_issues + changelog_issues:
        print(f"  - {issue}")
    if manifest_issues:
        print(f"\nRepair the manifests with:\n\n    {REPAIR_COMMAND}\n")
    if changelog_issues:
        print(
            "\nCHANGELOG.md must be edited by hand. --fix will not write a release\n"
            "section: an auto-inserted empty section is precisely the empty-notes\n"
            "artifact the release guard exists to prevent."
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--fix",
        action="store_true",
        help=(
            "Propagate .version into the manifests that track it. Never run "
            "from the pre-commit hook; writes files."
        ),
    )
    args = parser.parse_args(argv)

    version = read_version(REPO_ROOT / ".version")

    manifest_issues = validate_version_consistency(REPO_ROOT)
    changelog_issues = check_changelog_heading(version)

    if not args.fix:
        if manifest_issues or changelog_issues:
            report(version, manifest_issues, changelog_issues)
            return 1
        return 0

    # --fix from here down. CHANGELOG.md is deliberately out of its reach.
    if not manifest_issues:
        print(f"Nothing to fix: manifests already agree with .version ({version}).")
    else:
        updated = sync_version_to_files(REPO_ROOT, version)
        if updated:
            print(f"Synced .version ({version}) into:")
            for path in updated:
                print(f"  - {Path(path).relative_to(REPO_ROOT)}")
        else:
            # sync_version_to_files swallows JSONDecodeError and OSError, so a
            # malformed or unreadable manifest reports no change and no error.
            # The re-validation below is what turns that into a red exit.
            print("No file was written.")

    # Re-validate against what is now on disk. A fixer that half-fixes and
    # exits 0 is the same silent-success shape this script exists to remove.
    remaining_manifest = validate_version_consistency(REPO_ROOT)
    remaining_changelog = check_changelog_heading(version)
    if remaining_manifest or remaining_changelog:
        print()
        report(version, remaining_manifest, remaining_changelog)
        print("\n--fix ran and the tree is still inconsistent.")
        return 1

    print("Version consistency restored.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
