"""Install / uninstall the elijahr/cco hardened fork as ``spellbook-cco``.

This module is the once-globally seam invoked by
``installer/platforms/claude_code.py`` (Task 3 wires it in). It clones the
audited fork at the pinned SHA into ``~/.local/spellbook/cco/`` and writes
a managed wrapper at ``~/.local/bin/spellbook-cco`` that ``exec``s the
clone's ``cco`` binary. The wrapper is the canonical entry point for
spellbook-supported sandboxing on Linux and macOS.

Single-user assumption (F-H): the install root is per-user under
``Path.home()``. Concurrent multi-user installs under the same ``$HOME``
are not supported.

Rollback: ``SPELLBOOK_USE_VANILLA_CCO=1`` in the operator's environment
short-circuits the install (and the sandbox script's runtime gate) so the
operator falls back to vanilla ``nikvdp/cco`` at the legacy pin
``9744b9f``. A stderr WARNING fires at every entry point so the rollback
is visible in transcripts.

Audit gate: ``SPELLBOOK_INSTALLER_SKIP_FORK_PIN=1`` skips the two-step
pin verification (``git rev-parse`` + ``cco --version``). It is intended
for audited downgrades only and emits a stderr WARNING that names the
gate explicitly.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Module constants -- contract-locked with the orchestrator's task brief.
# ---------------------------------------------------------------------------

# Pin to elijahr/cco master commit audited 2026-05-07. Bumping requires
# re-audit per Sec 9.3.
SPELLBOOK_CCO_PINNED_SHA: str = "d7044ef"

# HTTPS only -- the installer cannot assume the operator has SSH keys.
SPELLBOOK_CCO_REPO_URL: str = "https://github.com/elijahr/cco.git"

# Single-user assumption: per-user clone root (F-H acceptance).
SPELLBOOK_CCO_DEFAULT_INSTALL_ROOT: Path = Path.home() / ".local" / "spellbook" / "cco"

# Wrapper namespace tag (F-D). Exact line in the wrapper for ownership
# detection. NOT ``# Source:`` -- that collides with the operator's
# existing dev-script signature.
SPELLBOOK_CCO_WRAPPER_TAG: str = "# spellbook-cco-managed: v1"

# Default wrapper install location. We do NOT mutate any rc file; the
# caller emits a stderr WARNING with a one-line how-to if this dir is not
# on the operator's PATH.
SPELLBOOK_CCO_WRAPPER_DIR: Path = Path.home() / ".local" / "bin"
SPELLBOOK_CCO_WRAPPER_PATH: Path = SPELLBOOK_CCO_WRAPPER_DIR / "spellbook-cco"

# Marker file dropped INSIDE the clone's .git/ dir so uninstall can
# distinguish a directory we created from a foreign directory living at
# the same path. We deliberately keep the marker out of the working tree
# so ``git status --porcelain`` does not see it as an untracked file
# (which would spuriously trip the "install_root has uncommitted
# changes" abort path on second-run idempotency).
#
# Tests that drop a managed marker for uninstall fixtures may use either
# the .git-internal path or the legacy top-level path; ``_is_managed``
# accepts both for forward-compatibility.
_MANAGED_MARKER_NAME: str = ".spellbook-cco-managed"
_MANAGED_MARKER_BODY: str = "v1\n"


def _managed_marker_paths(install_root: Path) -> tuple[Path, Path]:
    """Return both the canonical (.git-internal) and legacy (top-level)
    marker paths for a given install_root."""
    return (
        install_root / ".git" / _MANAGED_MARKER_NAME,
        install_root / _MANAGED_MARKER_NAME,
    )


def _is_managed_install_root(install_root: Path) -> bool:
    """True iff the install_root looks like one we created.

    Accepts the canonical .git-internal marker AND the legacy top-level
    marker so existing test fixtures keep working without modification.
    """
    canonical, legacy = _managed_marker_paths(install_root)
    return canonical.exists() or legacy.exists()


# Canonical WARNING strings -- factored into a helper below so tests can
# assert exact prefixes/substrings on stderr.
_WARNING_PREFIX: str = "WARNING:"

_WARNING_USE_VANILLA_CCO: str = (
    f"{_WARNING_PREFIX} SPELLBOOK_USE_VANILLA_CCO=1 set; using vanilla "
    "nikvdp/cco. This bypasses the hardened fork's macOS SBPL profile and "
    "DYLD scrub.\n"
)

_WARNING_SKIP_FORK_PIN: str = (
    f"{_WARNING_PREFIX} SPELLBOOK_INSTALLER_SKIP_FORK_PIN=1 set; pin "
    "verification skipped. This bypasses an audit gate and is intended "
    "only for audited downgrades.\n"
)

_WARNING_PATH_NOT_SET: str = (
    f"{_WARNING_PREFIX} ~/.local/bin is not on PATH. Add it to your "
    f'shell rc (e.g., export PATH="$HOME/.local/bin:$PATH") so '
    f"spellbook-cco is invokable.\n"
)


def _emit_warning(message: str) -> None:
    """Single chokepoint for stderr WARNING emission.

    Centralizing the writes makes it trivial for tests to capture them
    via ``capsys`` and lets us swap the destination if the operator ever
    asks for structured logging.
    """
    sys.stderr.write(message)
    sys.stderr.flush()


def emit_rollback_warning() -> None:
    """Public chokepoint for the canonical SPELLBOOK_USE_VANILLA_CCO=1
    rollback WARNING.

    Imported by every entry point that branches on the
    ``SPELLBOOK_USE_VANILLA_CCO=1`` env override
    (``installer/platforms/claude_code.py``, ``installer/tui.py``,
    ``install.py``) so the byte-content of the WARNING is centralized
    in one place and cannot drift between call sites. Tests assert
    the substrings ``"WARNING:"`` and ``"SPELLBOOK_USE_VANILLA_CCO=1"``
    are present on captured stderr.
    """
    _emit_warning(_WARNING_USE_VANILLA_CCO)


def _wrapper_template(install_root: Path, pinned_sha: str) -> str:
    """Return the wrapper script body for the given resolved install_root.

    Five-line script (orchestrator contract). The Audit reference is the
    Sec 9.3 audit revision section that documents the macOS SBPL
    hardening. ``install_root`` MUST be the resolved absolute path so
    idempotency byte-comparison does not spuriously trigger on symlink
    variance.
    """
    return (
        "#!/usr/bin/env bash\n"
        f"{SPELLBOOK_CCO_WRAPPER_TAG}\n"
        f"# Source:    {install_root} (fork of nikvdp/cco @ {pinned_sha})\n"
        "# Audit:     ~/.local/spellbook/docs/Users-eek-Development-spellbook"
        "/verifications/sec_9_3_result.md\n"
        f'exec {install_root}/cco "$@"\n'
    )


# ---------------------------------------------------------------------------
# Pin verification
# ---------------------------------------------------------------------------


def _verify_pin(install_root: Path) -> tuple[bool, str]:
    """Two-step pin verification.

    Step 1: ``git -C <install_root> rev-parse --short=7 HEAD`` is compared
    string-equal to ``SPELLBOOK_CCO_PINNED_SHA``.

    Step 2: ``<install_root>/cco --version`` is parsed via "second
    whitespace token of the first line" (mirroring spellbook-sandbox's
    awk parse) and compared string-equal to ``SPELLBOOK_CCO_PINNED_SHA``.

    Returns ``(matched, observed_sha)``. ``observed_sha`` may be an empty
    string when the underlying subprocess errors. The caller uses both
    fields to compose a precise ``skipped_reason``.
    """
    # Step 1.
    rev_proc = subprocess.run(
        ["git", "-C", str(install_root), "rev-parse", "--short=7", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if rev_proc.returncode != 0:
        return False, ""
    git_sha = rev_proc.stdout.strip()
    if git_sha != SPELLBOOK_CCO_PINNED_SHA:
        return False, git_sha

    # Step 2.
    version_proc = subprocess.run(
        [str(install_root / "cco"), "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    if version_proc.returncode != 0:
        return False, ""
    first_line = version_proc.stdout.splitlines()[0] if version_proc.stdout else ""
    tokens = first_line.split()
    runtime_sha = tokens[1] if len(tokens) >= 2 else ""
    if runtime_sha != SPELLBOOK_CCO_PINNED_SHA:
        return False, runtime_sha

    return True, runtime_sha


# ---------------------------------------------------------------------------
# Clone / fetch helpers
# ---------------------------------------------------------------------------


def _clone_or_fetch(install_root: Path) -> tuple[bool, str | None]:
    """Bring ``install_root`` to the pinned SHA via clone or fetch+checkout.

    Returns ``(ok, skipped_reason)``. On success returns ``(True, None)``.
    On any abort condition returns ``(False, "<reason>")`` so the caller
    can surface the reason in the result dict.

    Three dispositions:
        - install_root absent -> ``git clone`` then ``git checkout PIN``.
        - install_root present + remote.origin.url matches -> ``git fetch``
          then ``git checkout PIN``. Aborts if working tree is dirty.
        - install_root present + remote mismatch -> abort.
    """
    parent = install_root.parent
    parent.mkdir(parents=True, exist_ok=True)

    if not install_root.exists():
        clone_proc = subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "50",
                SPELLBOOK_CCO_REPO_URL,
                str(install_root),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if clone_proc.returncode != 0:
            return False, (f"git clone failed: {clone_proc.stderr.strip() or 'unknown error'}")
        # Drop the managed-marker INSIDE the clone's .git/ dir so
        # uninstall can detect we created this tree, without polluting
        # the working tree (which would trip ``git status --porcelain``
        # on the next install run).
        canonical_marker, _ = _managed_marker_paths(install_root)
        canonical_marker.parent.mkdir(parents=True, exist_ok=True)
        canonical_marker.write_text(_MANAGED_MARKER_BODY)
    else:
        # Remote check.
        remote_proc = subprocess.run(
            [
                "git",
                "-C",
                str(install_root),
                "config",
                "--get",
                "remote.origin.url",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if remote_proc.returncode != 0:
            return False, (
                f"install_root remote mismatch: expected {SPELLBOOK_CCO_REPO_URL}, got <none>"
            )
        actual_remote = remote_proc.stdout.strip()
        if actual_remote != SPELLBOOK_CCO_REPO_URL:
            return False, (
                f"install_root remote mismatch: expected {SPELLBOOK_CCO_REPO_URL}, "
                f"got {actual_remote}"
            )

        # Dirty-tree check.
        status_proc = subprocess.run(
            ["git", "-C", str(install_root), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
        )
        if status_proc.returncode == 0 and status_proc.stdout.strip():
            return False, ("install_root has uncommitted changes; clean and re-run")

        fetch_proc = subprocess.run(
            ["git", "-C", str(install_root), "fetch", "--depth", "50", "origin"],
            capture_output=True,
            text=True,
            check=False,
        )
        if fetch_proc.returncode != 0:
            return False, (f"git fetch failed: {fetch_proc.stderr.strip() or 'unknown error'}")

    # Best-effort checkout of the pinned SHA. If the SHA is unreachable
    # from the fetched history (or invalid as a ref), we leave HEAD where
    # it landed naturally (master tip after clone, or whatever fetch
    # produced) and let ``_verify_pin`` produce the canonical
    # "pin verification failed" error. This matters for two reasons:
    # 1. In production with a real fork, the pinned commit IS reachable
    #    from master via --depth 50, so this checkout succeeds and lands
    #    HEAD on the pin before verification.
    # 2. In Tier-2 tests where the operator monkeypatches the pin to a
    #    sha that doesn't match the fixture's HEAD, this checkout fails
    #    silently and ``_verify_pin`` produces the right error message
    #    (rather than this helper masking it as "git checkout failed").
    subprocess.run(
        ["git", "-C", str(install_root), "checkout", SPELLBOOK_CCO_PINNED_SHA],
        capture_output=True,
        text=True,
        check=False,
    )
    return True, None


# ---------------------------------------------------------------------------
# Wrapper write helper
# ---------------------------------------------------------------------------


def _write_wrapper(install_root: Path, pinned_sha: str) -> str:
    """Write the spellbook-cco wrapper to ``SPELLBOOK_CCO_WRAPPER_PATH``.

    Returns the action taken (one of ``"installed"`` or ``"noop"``).

    Idempotency rule (orchestrator-locked):
        - missing                                          -> write, "installed"
        - present + tagged + byte-equal to canonical text  -> "noop"
        - present + tagged + byte-different (path drift)   -> overwrite, "installed"
        - present + untagged                               -> WARNING + overwrite, "installed"
    """
    wrapper_path = SPELLBOOK_CCO_WRAPPER_PATH
    wrapper_dir = SPELLBOOK_CCO_WRAPPER_DIR
    wrapper_dir.mkdir(parents=True, exist_ok=True)

    canonical_text = _wrapper_template(install_root.resolve(), pinned_sha)

    if not wrapper_path.exists():
        wrapper_path.write_text(canonical_text)
        wrapper_path.chmod(0o755)
        return "installed"

    existing = wrapper_path.read_text()
    if SPELLBOOK_CCO_WRAPPER_TAG in existing:
        if existing == canonical_text:
            return "noop"
        # Tagged but drifted -- overwrite quietly (we own this file).
        wrapper_path.write_text(canonical_text)
        wrapper_path.chmod(0o755)
        return "installed"

    # Untagged -- operator-rolled. Overwrite with a WARNING.
    _emit_warning(
        f"{_WARNING_PREFIX} existing wrapper at {wrapper_path} not "
        "spellbook-managed; overwriting.\n"
    )
    wrapper_path.write_text(canonical_text)
    wrapper_path.chmod(0o755)
    return "installed"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def install_spellbook_cco(
    install_root: Path | None = None,
    dry_run: bool = False,
) -> dict:
    """Install (or update to pin) the elijahr/cco fork and write the wrapper.

    Args:
        install_root: clone destination. Defaults to
            ``SPELLBOOK_CCO_DEFAULT_INSTALL_ROOT``. Tests override.
        dry_run: when ``True`` no subprocess or filesystem mutation
            occurs; the call returns a shape-only result.

    Returns:
        ``{"installed": bool, "path": str | None, "skipped_reason":
        str | None, "action": str, "install_root": str | None}``.
    """
    resolved_install_root = (
        Path(install_root) if install_root is not None else SPELLBOOK_CCO_DEFAULT_INSTALL_ROOT
    )

    # Dry-run short-circuit: no subprocess, no FS mutation.
    if dry_run:
        return {
            "installed": False,
            "path": str(SPELLBOOK_CCO_WRAPPER_PATH),
            "skipped_reason": "dry-run",
            "action": "noop",
            "install_root": str(resolved_install_root),
        }

    # Windows is a shape-only noop.
    if os.name == "nt":
        return {
            "installed": False,
            "path": None,
            "skipped_reason": "spellbook-cco unavailable on Windows",
            "action": "skipped",
            "install_root": None,
        }

    # Rollback override.
    if os.environ.get("SPELLBOOK_USE_VANILLA_CCO") == "1":
        _emit_warning(_WARNING_USE_VANILLA_CCO)
        return {
            "installed": False,
            "path": None,
            "skipped_reason": ("SPELLBOOK_USE_VANILLA_CCO=1 active; routing to legacy vanilla cco"),
            "action": "skipped",
            "install_root": None,
        }

    # Clone or fetch the fork to the pinned SHA.
    ok, reason = _clone_or_fetch(resolved_install_root)
    if not ok:
        return {
            "installed": False,
            "path": None,
            "skipped_reason": reason,
            "action": "skipped",
            "install_root": str(resolved_install_root.resolve()),
        }

    # Pin verification (with audited skip).
    if os.environ.get("SPELLBOOK_INSTALLER_SKIP_FORK_PIN") == "1":
        _emit_warning(_WARNING_SKIP_FORK_PIN)
    else:
        matched, observed = _verify_pin(resolved_install_root)
        if not matched:
            # Rollback: do NOT write wrapper; tear down the clone if we
            # created it (presence of the managed-marker is the test).
            if _is_managed_install_root(resolved_install_root):
                shutil.rmtree(resolved_install_root, ignore_errors=True)
            failure_msg = (
                f"pin verification failed: expected {SPELLBOOK_CCO_PINNED_SHA}, "
                f"got {observed or '<unparseable>'}"
            )
            _emit_warning(f"{_WARNING_PREFIX} {failure_msg}\n")
            return {
                "installed": False,
                "path": None,
                "skipped_reason": failure_msg,
                "action": "skipped",
                "install_root": str(resolved_install_root.resolve()),
            }

    # Wrapper write (idempotent).
    action = _write_wrapper(resolved_install_root, SPELLBOOK_CCO_PINNED_SHA)

    # PATH check.
    path_dirs = [Path(p) for p in os.environ.get("PATH", "").split(os.pathsep) if p]
    if SPELLBOOK_CCO_WRAPPER_DIR not in path_dirs:
        _emit_warning(_WARNING_PATH_NOT_SET)

    return {
        "installed": True,
        "path": str(SPELLBOOK_CCO_WRAPPER_PATH),
        "skipped_reason": None,
        "action": action,
        "install_root": str(resolved_install_root.resolve()),
    }


def uninstall_spellbook_cco(
    install_root: Path | None = None,
    dry_run: bool = False,
) -> dict:
    """Remove the spellbook-managed fork clone and wrapper.

    Wrapper removal: only when the file content contains
    ``SPELLBOOK_CCO_WRAPPER_TAG`` (operator-rolled wrappers preserved).

    Clone removal: only when the install_root contains the
    ``.spellbook-cco-managed`` marker we drop at install time. Foreign
    directories sharing the same path are preserved.

    Returns the orchestrator-locked dict shape.
    """
    resolved_install_root = (
        Path(install_root) if install_root is not None else SPELLBOOK_CCO_DEFAULT_INSTALL_ROOT
    )

    wrapper_path = SPELLBOOK_CCO_WRAPPER_PATH

    if dry_run:
        # Convey "would do work" via installed=True so the caller can tell
        # apart a populated machine from a clean one without performing
        # real I/O.
        wrapper_present = wrapper_path.exists()
        clone_present = resolved_install_root.exists()
        any_artifacts = wrapper_present or clone_present
        return {
            "installed": any_artifacts,
            "path": str(wrapper_path) if wrapper_present else None,
            "skipped_reason": "dry-run",
            "action": "noop",
        }

    # Wrapper disposition.
    wrapper_action: str | None = None
    if wrapper_path.exists():
        existing = wrapper_path.read_text()
        if SPELLBOOK_CCO_WRAPPER_TAG in existing:
            wrapper_path.unlink()
            wrapper_action = "removed"
        else:
            wrapper_action = "preserved-untagged"

    # Clone disposition: only remove if we created it.
    clone_action: str | None = None
    if resolved_install_root.exists():
        if _is_managed_install_root(resolved_install_root):
            shutil.rmtree(resolved_install_root, ignore_errors=True)
            clone_action = "removed"
        else:
            clone_action = "preserved-foreign"

    # Aggregate. Picks "worst-of" (preserve > remove > noop) so the
    # operator can see at a glance whether spellbook touched everything.
    if wrapper_action is None and clone_action is None:
        return {
            "installed": False,
            "path": None,
            "skipped_reason": "nothing to uninstall",
            "action": "noop",
        }

    if wrapper_action == "preserved-untagged":
        top_action = "preserved-untagged"
    elif clone_action == "preserved-foreign":
        top_action = "removed"  # wrapper removed; foreign clone untouched
    else:
        top_action = "removed"

    # Path: emit the wrapper path whenever we observed it (removed or
    # preserved); None only when there was no wrapper to act on.
    path_value = str(wrapper_path) if wrapper_action is not None else None

    return {
        "installed": True,
        "path": path_value,
        "skipped_reason": None,
        "action": top_action,
    }
