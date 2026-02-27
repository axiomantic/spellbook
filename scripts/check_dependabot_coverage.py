#!/usr/bin/env python3
"""Pre-commit hook: ensure all package manifests are covered by Dependabot.

Scans the repo for package.json, go.mod, Dockerfile, pyproject.toml, etc.
and verifies each has a matching entry in .github/dependabot.yml.
"""

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DEPENDABOT_PATH = REPO_ROOT / ".github" / "dependabot.yml"

# Map manifest filenames to their Dependabot ecosystem
MANIFEST_ECOSYSTEMS = {
    "package.json": "npm",
    "go.mod": "gomod",
    "Dockerfile": "docker",
    "pyproject.toml": "pip",
    "Cargo.toml": "cargo",
    "Gemfile": "bundler",
    "composer.json": "composer",
    "pom.xml": "maven",
    "build.gradle": "gradle",
    "requirements.txt": "pip",
}

# Directories to skip (node_modules, vendored code, etc.)
SKIP_DIRS = {"node_modules", ".venv", "venv", "vendor", "__pycache__", ".git", ".claude"}

# Directories whose manifests are covered by a parent directory's entry
# (e.g. spellbook_mcp/requirements.txt is covered by the root pip entry)
COVERED_BY_PARENT = {
    "/spellbook_mcp",  # requirements.txt covered by root pyproject.toml
}

# Directories containing test fixtures, not real dependencies
SKIP_PATHS = {
    "integrationtests/workspaces",  # mcp-language-server test fixtures
}


def find_manifests() -> list[tuple[str, Path]]:
    """Find all package manifests in the repo, return (ecosystem, directory) pairs."""
    found = []
    for manifest_name, ecosystem in MANIFEST_ECOSYSTEMS.items():
        for path in REPO_ROOT.rglob(manifest_name):
            # Skip vendored/generated directories
            if any(skip in path.parts for skip in SKIP_DIRS):
                continue
            rel_path = str(path.parent.relative_to(REPO_ROOT))
            # Skip test fixture directories
            if any(skip in rel_path for skip in SKIP_PATHS):
                continue
            rel_dir = "/" + rel_path
            if rel_dir == "/.":
                rel_dir = "/"
            found.append((ecosystem, rel_dir))
    return found


def load_dependabot_entries() -> set[tuple[str, str]]:
    """Load configured (ecosystem, directory) pairs from dependabot.yml."""
    if not DEPENDABOT_PATH.exists():
        return set()

    with open(DEPENDABOT_PATH) as f:
        config = yaml.safe_load(f)

    entries = set()
    for update in config.get("updates", []):
        ecosystem = update.get("package-ecosystem", "")
        directory = update.get("directory", "/")
        # Normalize trailing slashes
        directory = directory.rstrip("/") or "/"
        entries.add((ecosystem, directory))
    return entries


def main() -> int:
    manifests = find_manifests()
    configured = load_dependabot_entries()

    missing = []
    for ecosystem, directory in manifests:
        normalized_dir = directory.rstrip("/") or "/"
        if normalized_dir in COVERED_BY_PARENT:
            continue
        if (ecosystem, normalized_dir) not in configured:
            missing.append((ecosystem, directory))

    if missing:
        print("Dependabot coverage gap detected!")
        print(f"The following manifests are not in {DEPENDABOT_PATH.relative_to(REPO_ROOT)}:\n")
        for ecosystem, directory in sorted(set(missing)):
            print(f"  - package-ecosystem: \"{ecosystem}\"")
            print(f"    directory: \"{directory}\"\n")
        print("Add entries to .github/dependabot.yml or update SKIP_DIRS in this script.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
