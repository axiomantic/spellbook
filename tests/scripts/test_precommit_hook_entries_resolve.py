"""Every local pre-commit hook must invoke something that still exists.

The recurring defect this guards: a subsystem is deleted and a hook that
drives it is left behind. The hook then fails only at the moment a
contributor stages a matching file, and it fails with a
``ModuleNotFoundError`` that looks like a broken environment rather than a
stale config. Two hooks in this repository invoked
``spellbook.gates.scanner`` for months after ``spellbook/gates/`` was
removed; a third named a script under a deleted directory.

The check resolves the two things a local hook entry can name:

* ``python -m MODULE`` -- the module must be importable.
* a path to a repository file (``scripts/foo.py``) -- the file must exist.
* ``bash -c 'cd DIR && ...'`` -- the directory must exist.

Anything the parser cannot classify fails the test with the offending
entry, so an extraction gap surfaces as red rather than as a silently
shrinking sample. ``repo: local`` hooks only: hooks from remote repos
carry their own environments and are not this repository's to validate.
"""

import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / ".pre-commit-config.yaml"

# Tokens that wrap the real command and carry no target of their own.
_WRAPPER_TOKENS = frozenset({"uv", "run", "uvx", "python", "python3", "-m"})


def _local_hooks() -> list[dict]:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    hooks: list[dict] = []
    for repo in config["repos"]:
        if repo.get("repo") == "local":
            hooks.extend(repo["hooks"])
    return hooks


LOCAL_HOOKS = _local_hooks()


def test_local_hooks_are_discovered():
    """A parse that silently found nothing would pass every check below."""
    assert LOCAL_HOOKS, f"No `repo: local` hooks parsed from {CONFIG_PATH}"


@pytest.mark.parametrize(
    "hook", LOCAL_HOOKS, ids=[h["id"] for h in LOCAL_HOOKS]
)
def test_hook_entry_resolves(hook):
    entry = hook["entry"]
    tokens = shlex.split(entry)

    # `bash -c '...'` and friends embed a shell program; the module/script
    # reference is inside the quoted string, so scan the raw entry text.
    module_match = re.search(r"(?:^|\s)-m\s+([\w.]+)", entry)
    if module_match:
        module = module_match.group(1)
        result = subprocess.run(
            [sys.executable, "-c", f"import {module}"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"Hook {hook['id']!r} invokes `-m {module}`, which is not "
            f"importable:\n{result.stderr.strip()}"
        )
        return

    scripts = [
        token
        for token in tokens
        if token not in _WRAPPER_TOKENS and re.search(r"\.(py|sh)$", token)
    ]
    if scripts:
        for script in scripts:
            assert (REPO_ROOT / script).is_file(), (
                f"Hook {hook['id']!r} invokes {script!r}, which does not "
                f"exist under {REPO_ROOT}"
            )
        return

    cd_match = re.search(r"(?<![\w-])cd\s+([^\s&|;'\"]+)", entry)
    if cd_match:
        target = cd_match.group(1)
        assert (REPO_ROOT / target).is_dir(), (
            f"Hook {hook['id']!r} changes into {target!r}, which does not "
            f"exist under {REPO_ROOT}"
        )
        return

    pytest.fail(
        f"Hook {hook['id']!r} entry {entry!r} names neither an importable "
        "module nor a repository script. Extend this test to classify it "
        "rather than letting it go unchecked."
    )


# A hook that repairs the tree instead of reporting on it converts a drift
# report into a drift eraser: the contributor sees a passing commit and the
# manifest changes underneath them. --fix on check_version_consistency.py
# writes files and is documented as human-invoked only. Nothing stops a later
# edit from "helpfully" adding it to the hook except this test.
_MUTATING_FLAG = "--fix"


def test_version_consistency_hook_is_configured():
    """The --fix guard below would pass vacuously if the hook were renamed."""
    ids = {hook["id"] for hook in LOCAL_HOOKS}
    assert "check-version-consistency" in ids, (
        "Hook 'check-version-consistency' is not in "
        f"{CONFIG_PATH}. Parsed ids: {sorted(ids)}"
    )


@pytest.mark.parametrize(
    "hook", LOCAL_HOOKS, ids=[h["id"] for h in LOCAL_HOOKS]
)
def test_hook_does_not_pass_mutating_fix_flag(hook):
    invocation = shlex.split(hook["entry"]) + list(hook.get("args", []))
    assert _MUTATING_FLAG not in invocation, (
        f"Hook {hook['id']!r} passes {_MUTATING_FLAG}. A pre-commit hook must "
        "report drift, never silently repair it; run the repair by hand."
    )
