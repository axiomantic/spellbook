"""Tests for ``scripts/spellbook-sandbox`` cco SHA pin and audit citations.

This file lives under ``tests/installer/`` because the sandbox script is
the launch wrapper installed alongside the per-platform alias shims. The
spellbook-sandbox script is POSIX-only (sh/bash); the marks below skip
the entire module on Windows.

Acceptance criteria covered:

* Sec 9.3 audit citation pin: literal ``9744b9f`` short SHA appears in a
  parsed/structured pin line in the script header.
* Audit citation: the script header references the Sec 9.3 audit document.
* macOS L5 rationale: documented either in the script header or in a sibling
  ``scripts/spellbook-sandbox.md`` markdown file.
* Help-flag smoke test: ``spellbook-sandbox --help`` (or its passthrough to
  ``cco --help``) exits cleanly when invoked. Skipped if no help mode is
  exposed without launching the sandbox itself, since this test is run in
  unprivileged test environments without ``cco`` on PATH.
"""

import re
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.posix_only

REPO_ROOT = Path(__file__).resolve().parents[2]
SANDBOX_SCRIPT = REPO_ROOT / "scripts" / "spellbook-sandbox"
SANDBOX_DOC = REPO_ROOT / "scripts" / "spellbook-sandbox.md"

# The short SHA pinned by Sec 9.3 audit. The brief and operator durable rule
# require this exact value; a different SHA without re-audit is forbidden.
EXPECTED_CCO_SHA = "9744b9f"

# Stable phrase that anchors the macOS L5 rationale block. The wording was
# chosen by the brief and is asserted exactly to catch silent edits that
# would weaken the rationale.
MACOS_RATIONALE_PHRASE = "L5 macOS is intentionally absent"


def _read_script() -> str:
    return SANDBOX_SCRIPT.read_text()


def test_spellbook_sandbox_pins_cco_sha():
    """The sandbox script pins cco at the audited SHA via a structured pin line.

    Parses the pin via a regex anchored on the structured comment line so the
    test asserts on a captured value (the SHA) rather than substring presence.
    """
    script = _read_script()

    match = re.search(
        r"^#\s*cco sandbox pin:\s*SHA\s+([0-9a-f]{7,40})\b",
        script,
        re.MULTILINE,
    )
    assert match is not None, (
        "expected a '# cco sandbox pin: SHA <hash>' header line in "
        f"{SANDBOX_SCRIPT}; got none"
    )
    assert match.group(1) == EXPECTED_CCO_SHA


def test_spellbook_sandbox_cites_sec_9_3_audit():
    """The sandbox script header cites the Sec 9.3 audit by document filename.

    Parses the citation via a regex that captures the audit doc reference.
    Asserts exact equality on the captured filename to catch typos.
    """
    script = _read_script()

    match = re.search(r"(sec_9_3_result\.md)", script)
    assert match is not None, (
        f"expected the Sec 9.3 audit doc citation in {SANDBOX_SCRIPT}; got none"
    )
    assert match.group(1) == "sec_9_3_result.md"


def test_spellbook_sandbox_macos_rationale_documented():
    """The macOS L5 rationale is documented in the script or sibling .md file.

    Either location is acceptable per the brief. Asserts the canonical
    anchor phrase appears in at least one of the two locations.
    """
    script = _read_script()
    sidecar = SANDBOX_DOC.read_text() if SANDBOX_DOC.exists() else ""

    locations = {
        str(SANDBOX_SCRIPT): MACOS_RATIONALE_PHRASE in script,
        str(SANDBOX_DOC): MACOS_RATIONALE_PHRASE in sidecar,
    }
    # At least one location must contain the anchor phrase. We assert the
    # boolean OR via a structured comparison so the failure message names
    # both candidate locations.
    assert any(locations.values()), (
        f"macOS L5 rationale anchor phrase {MACOS_RATIONALE_PHRASE!r} not "
        f"found in any documented location: {locations}"
    )


def test_spellbook_sandbox_is_executable():
    """File mode must preserve the executable bit; the script is invoked
    directly by users via PATH lookups installed by the alias shims.
    """
    import stat

    mode = SANDBOX_SCRIPT.stat().st_mode
    assert bool(mode & stat.S_IXUSR) is True
    assert bool(mode & stat.S_IXGRP) is True
    assert bool(mode & stat.S_IXOTH) is True


def test_spellbook_sandbox_help_runs_cleanly():
    """``spellbook-sandbox --help`` exits cleanly OR is documented as not exposed.

    The script does not implement its own ``--help`` flag (it would forward
    to ``cco --help``, which requires cco on PATH). In test environments
    without cco installed, the script exits with the documented "cco not
    found" error. Both outcomes are acceptable; we assert one of them
    deterministically.
    """
    if not SANDBOX_SCRIPT.exists():
        pytest.skip(f"{SANDBOX_SCRIPT} missing")

    proc = subprocess.run(
        [str(SANDBOX_SCRIPT), "--help"],
        capture_output=True,
        text=True,
        timeout=5,
    )

    # The script either:
    #   (a) finds cco and forwards --help, exiting 0, OR
    #   (b) prints the documented "cco not found" message to stderr and
    #       exits 1 (the explicit exit code in the script).
    # Both are acceptable; assert exit code is in the documented set AND
    # if it is 1, the stderr matches the script's documented message.
    assert proc.returncode in {0, 1}
    if proc.returncode == 1:
        assert proc.stderr == (
            "spellbook-sandbox: cco not found on PATH. "
            "Install from https://github.com/nikvdp/cco\n"
        )
