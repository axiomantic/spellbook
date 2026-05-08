"""Tests for ``installer/components/spellbook_cco.py``.

The module installs the elijahr/cco hardened fork and writes the
``~/.local/bin/spellbook-cco`` wrapper that is the canonical entry point
for spellbook-managed cco invocations.

Tier 0 -- pure attribute reads against the imported module (no subprocess,
no filesystem, no env).

Tier 1 -- subprocess plumbing mocked / dispatch-shape checks. Filesystem
writes redirected to ``tmp_path``; ``subprocess.run`` is patched so the
tests do not invoke real ``git`` / ``cco`` binaries.

Tier 2 -- a real ``file://`` bare git repo built per-test by the
``fake_cco_fork_repo`` fixture; the fork-installation code path exercises
``git clone``, ``git fetch``, ``git rev-parse``, and ``cco --version``
parsing against an actual on-disk repo. Network is the only thing we keep
mocked (the ``file://`` URL is a local-disk substitute for the real
remote).

Authoritative contract: the orchestrator's task brief at
``Phase 4 -- Task 1 / Task 2`` (see plan
``2026-05-07-spellbook-cco-integration-impl.md``). The wrapper template,
SHA constant, and module function signatures are reproduced verbatim
below as test-time expected values; deviations from the contract surface
as test failures.
"""

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from installer.components import spellbook_cco
from installer.components.spellbook_cco import (
    SPELLBOOK_CCO_DEFAULT_INSTALL_ROOT,
    SPELLBOOK_CCO_PINNED_SHA,
    SPELLBOOK_CCO_REPO_URL,
    SPELLBOOK_CCO_WRAPPER_PATH,
    SPELLBOOK_CCO_WRAPPER_TAG,
    _WARNING_PATH_NOT_SET,
    _WARNING_SKIP_FORK_PIN,
    _WARNING_USE_VANILLA_CCO,
    install_spellbook_cco,
    uninstall_spellbook_cco,
)


# ---------------------------------------------------------------------------
# Expected wrapper template (orchestrator contract -- 5-line spec).
#
# Format substitutions:
#   {install_root}: absolute, resolved path of the fork clone
#   {pinned_sha}:   SPELLBOOK_CCO_PINNED_SHA at write time
# ---------------------------------------------------------------------------
EXPECTED_WRAPPER_TEMPLATE = (
    "#!/usr/bin/env bash\n"
    "# spellbook-cco-managed: v1\n"
    "# Source:    {install_root} (fork of nikvdp/cco @ {pinned_sha})\n"
    "# Audit:     ~/.local/spellbook/docs/Users-eek-Development-spellbook"
    "/verifications/sec_9_3_result.md\n"
    'exec {install_root}/cco "$@"\n'
)


def _expected_wrapper_text(install_root: Path, pinned_sha: str) -> str:
    return EXPECTED_WRAPPER_TEMPLATE.format(
        install_root=str(install_root.resolve()),
        pinned_sha=pinned_sha,
    )


def _empty_wrapper_dir(tmp_path: Path) -> tuple[Path, Path]:
    """Return (wrapper_dir, wrapper_path) under tmp_path with the dir created."""
    wrapper_dir = tmp_path / "wrapper-bin"
    wrapper_dir.mkdir()
    return wrapper_dir, wrapper_dir / "spellbook-cco"


# ---------------------------------------------------------------------------
# Tier-2 fixture: real `file://` bare repo with a stub `cco` whose
# `--version` output emits the fixture's actual head_sha verbatim.
# Single-commit fixture (option a per plan §3) so step-1 (git rev-parse)
# and step-2 (--version awk) compare against the same value.
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_cco_fork_repo(tmp_path):
    """Build a `file://`-served bare repo with a working `cco` stub at HEAD.

    Returns ``{"url": "file://...", "head_sha": "<7-char short>",
    "bare_path": Path, "work_path": Path}``.

    Single-commit pattern: the stub's body is built via f-string AFTER the
    head_sha is known. We do this by:

        1. init the bare + clone work tree
        2. write the stub with a placeholder body and stage+commit
        3. capture head_sha from rev-parse --short=7 HEAD
        4. rewrite the stub with the real head_sha and amend the commit
        5. push to bare's master ref

    The amend step is what makes step 1 (``git rev-parse``) and step 2
    (``cco --version`` awk-parse) compare against the same value: the
    file content matches HEAD because we edited the file BEFORE the
    amend operation that produced HEAD.
    """
    bare = tmp_path / "cco-fork.git"
    work = tmp_path / "cco-fork-work"

    subprocess.run(
        ["git", "init", "--bare", "--initial-branch=master", str(bare)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "clone", str(bare), str(work)],
        check=True,
        capture_output=True,
    )
    # Make sure the local branch is named master (clone of empty bare may
    # leave HEAD detached; we create the master branch explicitly).
    subprocess.run(
        ["git", "-C", str(work), "checkout", "-B", "master"],
        check=True,
        capture_output=True,
    )

    cco = work / "cco"
    # The stub queries its own clone's git HEAD at runtime so the
    # ``cco --version`` output ALWAYS matches whatever the clone's HEAD
    # short SHA is, no matter how many times the fixture's commit gets
    # amended. This dodges the "stub body contains a SHA which is itself
    # part of the SHA computation" chicken-and-egg problem (plan §3
    # option-(a) is theoretically impossible -- the stub body affects
    # the tree which affects the SHA, so writing head_sha into the stub
    # CHANGES head_sha). Self-derivation makes the stub body
    # SHA-independent, so a single commit suffices.
    cco.write_text(
        "#!/bin/sh\n"
        'CCO_REPO_DIR="$(cd "$(dirname "$0")" && pwd)"\n'
        'short_sha="$(git -C "$CCO_REPO_DIR" rev-parse --short=7 HEAD)"\n'
        'printf "cco %s (installation)\\n" "$short_sha"\n'
    )
    cco.chmod(0o755)
    subprocess.run(
        ["git", "-C", str(work), "add", "cco"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(work),
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "commit",
            "-m",
            "fixture",
        ],
        check=True,
        capture_output=True,
    )

    head_sha = subprocess.run(
        ["git", "-C", str(work), "rev-parse", "--short=7", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    subprocess.run(
        ["git", "-C", str(work), "push", "origin", "master"],
        check=True,
        capture_output=True,
    )

    return {
        "url": f"file://{bare}",
        "head_sha": head_sha,
        "bare_path": bare,
        "work_path": work,
    }


@pytest.fixture
def isolated_wrapper(tmp_path, monkeypatch):
    """Redirect SPELLBOOK_CCO_WRAPPER_DIR / _PATH to tmp_path.

    Returns the (dir, path) pair so tests can assert against the redirected
    location without writing to ``~/.local/bin``.
    """
    wrapper_dir, wrapper_path = _empty_wrapper_dir(tmp_path)
    monkeypatch.setattr(spellbook_cco, "SPELLBOOK_CCO_WRAPPER_DIR", wrapper_dir)
    monkeypatch.setattr(spellbook_cco, "SPELLBOOK_CCO_WRAPPER_PATH", wrapper_path)
    return wrapper_dir, wrapper_path


@pytest.fixture
def path_with_local_bin(monkeypatch, isolated_wrapper):
    """Ensure isolated_wrapper's dir IS on PATH so the PATH-warning test path
    is suppressed for unrelated tests."""
    wrapper_dir, _ = isolated_wrapper
    existing = os.environ.get("PATH", "")
    monkeypatch.setenv("PATH", f"{wrapper_dir}{os.pathsep}{existing}")
    return wrapper_dir


# ===========================================================================
# Tier 0 -- pure constant assertions
# ===========================================================================


def test_pinned_sha_constant():
    """SPELLBOOK_CCO_PINNED_SHA == 'd7044ef' (audit anchor)."""
    assert SPELLBOOK_CCO_PINNED_SHA == "d7044ef"


def test_repo_url_constant():
    """HTTPS-only fork URL (the installer cannot assume SSH keys)."""
    assert SPELLBOOK_CCO_REPO_URL == "https://github.com/elijahr/cco.git"


def test_default_install_root_constant():
    """Default install root is per-user under ``$HOME/.local/spellbook/cco``."""
    assert SPELLBOOK_CCO_DEFAULT_INSTALL_ROOT == (Path.home() / ".local" / "spellbook" / "cco")


def test_wrapper_path_constant():
    """Wrapper path is ``$HOME/.local/bin/spellbook-cco``."""
    assert SPELLBOOK_CCO_WRAPPER_PATH == (Path.home() / ".local" / "bin" / "spellbook-cco")


def test_wrapper_tag_constant():
    """The namespaced wrapper tag is ``# spellbook-cco-managed: v1`` (NOT
    ``# Source:``, which collides with the operator's existing dev-script
    signature)."""
    assert SPELLBOOK_CCO_WRAPPER_TAG == "# spellbook-cco-managed: v1"


# ===========================================================================
# Tier 1 -- subprocess plumbing mocked / shape checks
# ===========================================================================


@pytest.mark.posix_only
def test_install_calls_git_clone(monkeypatch, tmp_path, isolated_wrapper):
    """The install path invokes ``git clone`` on the configured remote URL."""
    install_root = tmp_path / "clone"
    calls: list[list[str]] = []

    def fake_run(cmd, *args, **kwargs):
        calls.append(list(cmd))
        # Simulate the directory existing after "clone".
        if len(cmd) >= 2 and cmd[0] == "git" and cmd[1] == "clone":
            Path(cmd[-1]).mkdir(parents=True, exist_ok=True)
        # Mimic git rev-parse short SHA = pinned, --version output = pinned.
        out = ""
        if cmd[0] == "git" and "rev-parse" in cmd:
            out = SPELLBOOK_CCO_PINNED_SHA + "\n"
        elif cmd[-1] == "--version":
            out = f"cco {SPELLBOOK_CCO_PINNED_SHA} (installation)\n"
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=out, stderr="")

    monkeypatch.setattr(spellbook_cco.subprocess, "run", fake_run)
    monkeypatch.delenv("SPELLBOOK_USE_VANILLA_CCO", raising=False)
    monkeypatch.delenv("SPELLBOOK_INSTALLER_SKIP_FORK_PIN", raising=False)

    result = install_spellbook_cco(install_root=install_root, dry_run=False)

    assert result["installed"] is True
    clone_cmds = [c for c in calls if c[:2] == ["git", "clone"]]
    assert len(clone_cmds) == 1
    assert SPELLBOOK_CCO_REPO_URL in clone_cmds[0]
    assert str(install_root) in clone_cmds[0]


def test_install_dry_run_does_not_clone(monkeypatch, tmp_path, isolated_wrapper):
    """``dry_run=True`` performs zero subprocess + zero filesystem writes."""
    install_root = tmp_path / "clone"
    calls: list[list[str]] = []

    def fake_run(cmd, *args, **kwargs):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(spellbook_cco.subprocess, "run", fake_run)
    monkeypatch.delenv("SPELLBOOK_USE_VANILLA_CCO", raising=False)

    _, wrapper_path = isolated_wrapper

    result = install_spellbook_cco(install_root=install_root, dry_run=True)

    assert calls == []
    assert install_root.exists() is False
    assert wrapper_path.exists() is False
    assert result == {
        "installed": False,
        "path": str(wrapper_path),
        "skipped_reason": "dry-run",
        "action": "noop",
        "install_root": str(install_root),
    }


def test_uninstall_dry_run_does_not_remove(monkeypatch, tmp_path):
    """``dry_run=True`` for uninstall returns shape; no FS mutation."""
    # Pre-create a tagged wrapper so we can prove it's preserved under dry-run.
    wrapper_dir = tmp_path / "wrapper-bin"
    wrapper_dir.mkdir()
    wrapper_path = wrapper_dir / "spellbook-cco"
    install_root = tmp_path / "clone"
    install_root.mkdir()
    wrapper_text = _expected_wrapper_text(install_root, SPELLBOOK_CCO_PINNED_SHA)
    wrapper_path.write_text(wrapper_text)
    wrapper_path.chmod(0o755)
    (install_root / ".spellbook-cco-managed").write_text("v1\n")

    monkeypatch.setattr(spellbook_cco, "SPELLBOOK_CCO_WRAPPER_DIR", wrapper_dir)
    monkeypatch.setattr(spellbook_cco, "SPELLBOOK_CCO_WRAPPER_PATH", wrapper_path)

    result = uninstall_spellbook_cco(install_root=install_root, dry_run=True)

    assert wrapper_path.exists() is True
    assert install_root.exists() is True
    assert result == {
        "installed": True,
        "path": str(wrapper_path),
        "skipped_reason": "dry-run",
        "action": "noop",
    }


@pytest.mark.posix_only
def test_install_returns_dict_shape_on_success(monkeypatch, tmp_path, path_with_local_bin):
    """Full success path returns the orchestrator-locked dict shape."""
    install_root = tmp_path / "clone"

    def fake_run(cmd, *args, **kwargs):
        if cmd[0] == "git" and "clone" in cmd:
            Path(cmd[-1]).mkdir(parents=True, exist_ok=True)
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")
        if cmd[0] == "git" and "rev-parse" in cmd:
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout=SPELLBOOK_CCO_PINNED_SHA + "\n",
                stderr="",
            )
        if len(cmd) >= 2 and cmd[-1] == "--version":
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout=f"cco {SPELLBOOK_CCO_PINNED_SHA} (installation)\n",
                stderr="",
            )
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(spellbook_cco.subprocess, "run", fake_run)
    monkeypatch.delenv("SPELLBOOK_USE_VANILLA_CCO", raising=False)
    monkeypatch.delenv("SPELLBOOK_INSTALLER_SKIP_FORK_PIN", raising=False)

    result = install_spellbook_cco(install_root=install_root, dry_run=False)

    assert set(result.keys()) == {
        "installed",
        "path",
        "skipped_reason",
        "action",
        "install_root",
    }
    assert result["installed"] is True
    assert result["action"] == "installed"
    assert result["skipped_reason"] is None
    assert result["path"] == str(spellbook_cco.SPELLBOOK_CCO_WRAPPER_PATH)
    assert result["install_root"] == str(install_root.resolve())


def test_uninstall_returns_dict_shape(tmp_path, monkeypatch):
    """Uninstall on a clean machine returns the noop shape."""
    wrapper_dir = tmp_path / "wrapper-bin"
    wrapper_dir.mkdir()
    wrapper_path = wrapper_dir / "spellbook-cco"
    install_root = tmp_path / "clone"  # absent

    monkeypatch.setattr(spellbook_cco, "SPELLBOOK_CCO_WRAPPER_DIR", wrapper_dir)
    monkeypatch.setattr(spellbook_cco, "SPELLBOOK_CCO_WRAPPER_PATH", wrapper_path)

    result = uninstall_spellbook_cco(install_root=install_root, dry_run=False)

    assert result == {
        "installed": False,
        "path": None,
        "skipped_reason": "nothing to uninstall",
        "action": "noop",
    }


# ===========================================================================
# Tier 2 -- real `file://` bare repo + real subprocess + real wrapper writes
# ===========================================================================


@pytest.mark.posix_only
def test_install_clones_then_verifies_pin_against_fake_repo(
    fake_cco_fork_repo, monkeypatch, tmp_path, path_with_local_bin
):
    """Full happy path against the real `file://` fixture.

    Step 1 (``git rev-parse``) and step 2 (``cco --version`` awk parse)
    are healthy because the fixture's stub emits the fixture's actual
    head_sha verbatim. We monkeypatch the production constants to align
    with the fixture's URL + head_sha.
    """
    install_root = tmp_path / "clone"
    monkeypatch.setattr(spellbook_cco, "SPELLBOOK_CCO_REPO_URL", fake_cco_fork_repo["url"])
    monkeypatch.setattr(
        spellbook_cco,
        "SPELLBOOK_CCO_PINNED_SHA",
        fake_cco_fork_repo["head_sha"],
    )
    monkeypatch.delenv("SPELLBOOK_USE_VANILLA_CCO", raising=False)
    monkeypatch.delenv("SPELLBOOK_INSTALLER_SKIP_FORK_PIN", raising=False)

    result = install_spellbook_cco(install_root=install_root, dry_run=False)

    _, wrapper_path = path_with_local_bin, spellbook_cco.SPELLBOOK_CCO_WRAPPER_PATH

    expected_wrapper = _expected_wrapper_text(install_root, fake_cco_fork_repo["head_sha"])
    assert wrapper_path.exists()
    assert wrapper_path.read_text() == expected_wrapper
    mode_bits = stat.S_IMODE(wrapper_path.stat().st_mode)
    assert mode_bits == 0o755

    head_after = subprocess.run(
        ["git", "-C", str(install_root), "rev-parse", "--short=7", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert head_after == fake_cco_fork_repo["head_sha"]

    assert result == {
        "installed": True,
        "path": str(wrapper_path),
        "skipped_reason": None,
        "action": "installed",
        "install_root": str(install_root.resolve()),
    }


@pytest.mark.posix_only
def test_install_rolls_back_when_git_rev_parse_mismatch(
    fake_cco_fork_repo, monkeypatch, tmp_path, isolated_wrapper, capsys
):
    """``_verify_pin`` step 1 mismatch -> rollback + no wrapper write.

    Setup: fixture HEAD = X (real head_sha); pin Y = "deadbee"; stub still
    emits X (consistent with HEAD). Step 1 (rev-parse=X vs pin=Y) fails
    BEFORE step 2 ever runs. Rollback removes the install_root clone and
    leaves the wrapper absent.
    """
    install_root = tmp_path / "clone"
    monkeypatch.setattr(spellbook_cco, "SPELLBOOK_CCO_REPO_URL", fake_cco_fork_repo["url"])
    monkeypatch.setattr(spellbook_cco, "SPELLBOOK_CCO_PINNED_SHA", "deadbee")
    monkeypatch.delenv("SPELLBOOK_USE_VANILLA_CCO", raising=False)
    monkeypatch.delenv("SPELLBOOK_INSTALLER_SKIP_FORK_PIN", raising=False)

    _, wrapper_path = isolated_wrapper

    result = install_spellbook_cco(install_root=install_root, dry_run=False)

    assert wrapper_path.exists() is False
    assert install_root.exists() is False
    assert result["installed"] is False
    assert result["action"] == "skipped"
    expected_failure = (
        f"pin verification failed: expected deadbee, got {fake_cco_fork_repo['head_sha']}"
    )
    assert result["skipped_reason"] == expected_failure

    # Dynamic WARNING (no module constant): assert full equality with the
    # canonical f-string format used in the production rollback path
    # (``f"WARNING: {failure_msg}\n"``).
    captured = capsys.readouterr()
    assert captured.err == f"WARNING: {expected_failure}\n"


@pytest.mark.posix_only
def test_install_rolls_back_when_version_parse_mismatch(
    fake_cco_fork_repo, monkeypatch, tmp_path, isolated_wrapper, capsys
):
    """``_verify_pin`` step 2 mismatch -> rollback (per option-c sibling).

    Setup: pin = X (matches fixture's HEAD); after `git clone`, we
    overwrite ``<install_root>/cco`` so its --version emits Y != X.
    Step 1 passes (rev-parse=X vs pin=X); step 2 fails (--version=Y vs
    pin=X). Rollback removes the install_root.

    To inject the post-clone stub overwrite, we patch
    ``_clone_or_fetch`` (the helper that ends with the clone in place)
    to the original implementation but then immediately rewrite the cco
    stub before ``_verify_pin`` runs. We do this via a
    ``monkeypatch`` of ``_verify_pin`` itself: keep the real impl but
    wrap it to first overwrite the stub. Simpler: patch the module-level
    ``_verify_pin`` to call the real one after rewriting the stub.
    """
    install_root = tmp_path / "clone"
    monkeypatch.setattr(spellbook_cco, "SPELLBOOK_CCO_REPO_URL", fake_cco_fork_repo["url"])
    monkeypatch.setattr(
        spellbook_cco,
        "SPELLBOOK_CCO_PINNED_SHA",
        fake_cco_fork_repo["head_sha"],
    )
    monkeypatch.delenv("SPELLBOOK_USE_VANILLA_CCO", raising=False)
    monkeypatch.delenv("SPELLBOOK_INSTALLER_SKIP_FORK_PIN", raising=False)

    real_verify = spellbook_cco._verify_pin

    def patched_verify(root):
        # Overwrite the dynamic self-querying stub with a STATIC stub
        # that hardcodes a wrong SHA so step 2 (--version awk parse)
        # diverges from step 1 (git rev-parse, which still reports the
        # real HEAD).
        cco_path = Path(root) / "cco"
        cco_path.write_text("#!/bin/sh\nprintf 'cco deadbee (installation)\\n'\n")
        cco_path.chmod(0o755)
        return real_verify(root)

    monkeypatch.setattr(spellbook_cco, "_verify_pin", patched_verify)

    _, wrapper_path = isolated_wrapper

    result = install_spellbook_cco(install_root=install_root, dry_run=False)

    assert wrapper_path.exists() is False
    assert install_root.exists() is False
    assert result["installed"] is False
    assert result["action"] == "skipped"
    # Step 1 of _verify_pin matches (rev-parse=head_sha == pin); step 2
    # diverges because the patched stub hardcodes `cco deadbee` so the
    # awk-parsed runtime SHA is "deadbee".
    expected_failure = (
        f"pin verification failed: expected {fake_cco_fork_repo['head_sha']}, got deadbee"
    )
    assert result["skipped_reason"] == expected_failure

    # Dynamic WARNING (no module constant): assert full equality with the
    # canonical f-string format used in the production rollback path.
    captured = capsys.readouterr()
    assert captured.err == f"WARNING: {expected_failure}\n"


@pytest.mark.posix_only
def test_install_idempotent_on_second_run(
    fake_cco_fork_repo, monkeypatch, tmp_path, path_with_local_bin
):
    """Second run on a healthy install returns ``action="noop"`` and does
    NOT rewrite the wrapper bytes."""
    install_root = tmp_path / "clone"
    monkeypatch.setattr(spellbook_cco, "SPELLBOOK_CCO_REPO_URL", fake_cco_fork_repo["url"])
    monkeypatch.setattr(
        spellbook_cco,
        "SPELLBOOK_CCO_PINNED_SHA",
        fake_cco_fork_repo["head_sha"],
    )
    monkeypatch.delenv("SPELLBOOK_USE_VANILLA_CCO", raising=False)
    monkeypatch.delenv("SPELLBOOK_INSTALLER_SKIP_FORK_PIN", raising=False)

    wrapper_path = spellbook_cco.SPELLBOOK_CCO_WRAPPER_PATH

    first = install_spellbook_cco(install_root=install_root, dry_run=False)
    assert first["installed"] is True
    assert first["action"] == "installed"
    first_text = wrapper_path.read_text()
    first_mtime = wrapper_path.stat().st_mtime_ns

    second = install_spellbook_cco(install_root=install_root, dry_run=False)

    assert second == {
        "installed": True,
        "path": str(wrapper_path),
        "skipped_reason": None,
        "action": "noop",
        "install_root": str(install_root.resolve()),
    }
    assert wrapper_path.read_text() == first_text
    assert wrapper_path.stat().st_mtime_ns == first_mtime


@pytest.mark.posix_only
def test_install_overwrites_untagged_wrapper_with_warning(
    fake_cco_fork_repo, monkeypatch, tmp_path, path_with_local_bin, capsys
):
    """An untagged operator-rolled wrapper at the target path is overwritten
    AND a WARNING is emitted to stderr."""
    install_root = tmp_path / "clone"
    monkeypatch.setattr(spellbook_cco, "SPELLBOOK_CCO_REPO_URL", fake_cco_fork_repo["url"])
    monkeypatch.setattr(
        spellbook_cco,
        "SPELLBOOK_CCO_PINNED_SHA",
        fake_cco_fork_repo["head_sha"],
    )
    monkeypatch.delenv("SPELLBOOK_USE_VANILLA_CCO", raising=False)

    wrapper_path = spellbook_cco.SPELLBOOK_CCO_WRAPPER_PATH
    wrapper_path.write_text('#!/bin/sh\n# Source: /home/op/dev/cco-checkout\nexec cco "$@"\n')
    wrapper_path.chmod(0o755)

    result = install_spellbook_cco(install_root=install_root, dry_run=False)

    expected_text = _expected_wrapper_text(install_root, fake_cco_fork_repo["head_sha"])
    assert wrapper_path.read_text() == expected_text
    assert result["installed"] is True
    assert result["action"] == "installed"

    captured = capsys.readouterr()
    assert "WARNING" in captured.err
    assert "not spellbook-managed" in captured.err
    assert str(wrapper_path) in captured.err


@pytest.mark.posix_only
def test_install_warns_when_local_bin_not_on_path(
    fake_cco_fork_repo, monkeypatch, tmp_path, isolated_wrapper, capsys
):
    """When ``~/.local/bin`` is not on PATH, the installer writes the wrapper
    anyway, returns ``installed=True``, and emits a stderr WARNING with a
    reproduction command."""
    install_root = tmp_path / "clone"
    monkeypatch.setattr(spellbook_cco, "SPELLBOOK_CCO_REPO_URL", fake_cco_fork_repo["url"])
    monkeypatch.setattr(
        spellbook_cco,
        "SPELLBOOK_CCO_PINNED_SHA",
        fake_cco_fork_repo["head_sha"],
    )
    monkeypatch.delenv("SPELLBOOK_USE_VANILLA_CCO", raising=False)
    monkeypatch.delenv("SPELLBOOK_INSTALLER_SKIP_FORK_PIN", raising=False)
    # Strip the wrapper dir out of PATH.
    sanitized_path = os.pathsep.join(
        p
        for p in os.environ.get("PATH", "").split(os.pathsep)
        if p and Path(p) != spellbook_cco.SPELLBOOK_CCO_WRAPPER_DIR
    )
    monkeypatch.setenv("PATH", sanitized_path)

    _, wrapper_path = isolated_wrapper

    result = install_spellbook_cco(install_root=install_root, dry_run=False)

    assert wrapper_path.exists()
    assert result["installed"] is True

    # Full-equality on the imported canonical constant: catches drift in
    # any of the three pieces (WARNING prefix, "not on PATH" phrase, and
    # the exact reproduction-command quoting) in a single assertion.
    captured = capsys.readouterr()
    assert captured.err == _WARNING_PATH_NOT_SET


@pytest.mark.posix_only
def test_use_vanilla_cco_env_routes_to_skipped(monkeypatch, tmp_path, isolated_wrapper, capsys):
    """``SPELLBOOK_USE_VANILLA_CCO=1`` returns the rollback shape AND emits
    a stderr WARNING. Does NOT clone, does NOT touch the wrapper."""
    monkeypatch.setenv("SPELLBOOK_USE_VANILLA_CCO", "1")
    install_root = tmp_path / "clone"
    _, wrapper_path = isolated_wrapper

    calls: list[list[str]] = []

    def fake_run(cmd, *args, **kwargs):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(spellbook_cco.subprocess, "run", fake_run)

    result = install_spellbook_cco(install_root=install_root, dry_run=False)

    assert calls == []
    assert install_root.exists() is False
    assert wrapper_path.exists() is False
    assert result == {
        "installed": False,
        "path": None,
        "skipped_reason": ("SPELLBOOK_USE_VANILLA_CCO=1 active; routing to legacy vanilla cco"),
        "action": "skipped",
        "install_root": None,
    }

    # Full-equality on the imported canonical constant catches drift in
    # the module-level warning text.
    captured = capsys.readouterr()
    assert captured.err == _WARNING_USE_VANILLA_CCO


@pytest.mark.posix_only
def test_install_succeeds_with_SKIP_FORK_PIN_at_wrong_sha(
    fake_cco_fork_repo, monkeypatch, tmp_path, path_with_local_bin, capsys
):
    """``SPELLBOOK_INSTALLER_SKIP_FORK_PIN=1`` skips BOTH pin steps even at
    a mismatched pin, emits the canonical stderr WARNING, and the install
    succeeds with the wrapper written and mode 0755.
    """
    install_root = tmp_path / "clone"
    monkeypatch.setattr(spellbook_cco, "SPELLBOOK_CCO_REPO_URL", fake_cco_fork_repo["url"])
    # Intentionally do NOT monkeypatch the pinned SHA -- it stays at
    # production's "d7044ef", which deliberately mismatches the fixture's
    # head_sha. The skip-env-var must make the install succeed anyway.
    assert SPELLBOOK_CCO_PINNED_SHA != fake_cco_fork_repo["head_sha"]
    monkeypatch.setenv("SPELLBOOK_INSTALLER_SKIP_FORK_PIN", "1")
    monkeypatch.delenv("SPELLBOOK_USE_VANILLA_CCO", raising=False)

    wrapper_path = spellbook_cco.SPELLBOOK_CCO_WRAPPER_PATH

    result = install_spellbook_cco(install_root=install_root, dry_run=False)

    expected_text = _expected_wrapper_text(install_root, SPELLBOOK_CCO_PINNED_SHA)
    assert wrapper_path.exists()
    assert wrapper_path.read_text() == expected_text
    assert stat.S_IMODE(wrapper_path.stat().st_mode) == 0o755
    assert result["installed"] is True
    assert result["action"] == "installed"
    assert result["skipped_reason"] is None

    # Full-equality on the imported canonical constant catches drift in
    # the module-level warning text. ``path_with_local_bin`` ensures the
    # PATH-not-set warning is suppressed, so this is the ONLY emission.
    captured = capsys.readouterr()
    assert captured.err == _WARNING_SKIP_FORK_PIN


def test_uninstall_removes_only_tagged_wrapper(monkeypatch, tmp_path, capsys):
    """Uninstall removes the wrapper iff it bears the tag; an
    operator-rolled untagged wrapper is preserved."""
    wrapper_dir = tmp_path / "wrapper-bin"
    wrapper_dir.mkdir()
    wrapper_path = wrapper_dir / "spellbook-cco"
    install_root = tmp_path / "clone"
    install_root.mkdir()
    (install_root / ".spellbook-cco-managed").write_text("v1\n")

    monkeypatch.setattr(spellbook_cco, "SPELLBOOK_CCO_WRAPPER_DIR", wrapper_dir)
    monkeypatch.setattr(spellbook_cco, "SPELLBOOK_CCO_WRAPPER_PATH", wrapper_path)

    # Case A: untagged wrapper -- preserved.
    untagged = '#!/bin/sh\n# operator-rolled\nexec /opt/local/cco "$@"\n'
    wrapper_path.write_text(untagged)
    wrapper_path.chmod(0o755)

    result_a = uninstall_spellbook_cco(install_root=install_root, dry_run=False)

    assert wrapper_path.exists()
    assert wrapper_path.read_text() == untagged
    assert result_a["action"] == "preserved-untagged"

    # Case B: tagged wrapper -- removed.
    tagged = _expected_wrapper_text(install_root, SPELLBOOK_CCO_PINNED_SHA)
    wrapper_path.write_text(tagged)
    wrapper_path.chmod(0o755)
    # Recreate install_root since case A may have removed it.
    if not install_root.exists():
        install_root.mkdir()
        (install_root / ".spellbook-cco-managed").write_text("v1\n")

    result_b = uninstall_spellbook_cco(install_root=install_root, dry_run=False)

    assert wrapper_path.exists() is False
    assert result_b["installed"] is True
    assert result_b["action"] == "removed"


def test_uninstall_removes_clone_only_if_we_created_it(monkeypatch, tmp_path):
    """Uninstall removes the install_root only if we created it (detected via
    the ``.spellbook-cco-managed`` marker we drop at install time). Other
    directories at the same path are preserved."""
    wrapper_dir = tmp_path / "wrapper-bin"
    wrapper_dir.mkdir()
    wrapper_path = wrapper_dir / "spellbook-cco"
    monkeypatch.setattr(spellbook_cco, "SPELLBOOK_CCO_WRAPPER_DIR", wrapper_dir)
    monkeypatch.setattr(spellbook_cco, "SPELLBOOK_CCO_WRAPPER_PATH", wrapper_path)

    # Case A: install_root WITHOUT the managed marker -- preserved.
    foreign_root = tmp_path / "foreign-clone"
    foreign_root.mkdir()
    (foreign_root / "operator-data.txt").write_text("important")
    # Wrapper is tagged so the wrapper is removed; only the clone preservation
    # path is exercised here.
    wrapper_path.write_text(_expected_wrapper_text(foreign_root, SPELLBOOK_CCO_PINNED_SHA))
    wrapper_path.chmod(0o755)

    result_a = uninstall_spellbook_cco(install_root=foreign_root, dry_run=False)

    assert foreign_root.exists()
    assert (foreign_root / "operator-data.txt").read_text() == "important"
    # Wrapper itself was removed (it was tagged).
    assert wrapper_path.exists() is False
    assert result_a["installed"] is True
    # Tagged wrapper removed + foreign clone preserved -> aggregation
    # is deterministic "removed" (per uninstall aggregation logic).
    assert result_a["action"] == "removed"

    # Case B: install_root WITH the managed marker -- removed.
    managed_root = tmp_path / "managed-clone"
    managed_root.mkdir()
    (managed_root / ".spellbook-cco-managed").write_text("v1\n")
    (managed_root / "cco").write_text("#!/bin/sh\nexit 0\n")
    wrapper_path.write_text(_expected_wrapper_text(managed_root, SPELLBOOK_CCO_PINNED_SHA))
    wrapper_path.chmod(0o755)

    result_b = uninstall_spellbook_cco(install_root=managed_root, dry_run=False)

    assert managed_root.exists() is False
    assert wrapper_path.exists() is False
    assert result_b["installed"] is True
    assert result_b["action"] == "removed"


def test_uninstall_aggregation_untagged_wrapper_with_managed_clone(monkeypatch, tmp_path):
    """Aggregation branch: untagged wrapper + managed clone.

    Exercises the ``wrapper_action == "preserved-untagged"`` first-arm of
    the aggregation at module lines 526-531. The wrapper is preserved
    (operator-rolled), and the managed clone IS removed silently. The
    top-level action MUST be "preserved-untagged" to surface the
    user-visible artifact (the wrapper) the operator most cares about.
    """
    wrapper_dir = tmp_path / "wrapper-bin"
    wrapper_dir.mkdir()
    wrapper_path = wrapper_dir / "spellbook-cco"
    monkeypatch.setattr(spellbook_cco, "SPELLBOOK_CCO_WRAPPER_DIR", wrapper_dir)
    monkeypatch.setattr(spellbook_cco, "SPELLBOOK_CCO_WRAPPER_PATH", wrapper_path)

    # Untagged operator-rolled wrapper.
    untagged = '#!/bin/sh\n# operator-rolled\nexec /opt/local/cco "$@"\n'
    wrapper_path.write_text(untagged)
    wrapper_path.chmod(0o755)

    # Managed clone (marker present) at install_root.
    install_root = tmp_path / "managed-clone"
    install_root.mkdir()
    (install_root / ".spellbook-cco-managed").write_text("v1\n")
    (install_root / "cco").write_text("#!/bin/sh\nexit 0\n")

    result = uninstall_spellbook_cco(install_root=install_root, dry_run=False)

    # Wrapper preserved (untagged); clone removed (managed).
    assert wrapper_path.exists()
    assert wrapper_path.read_text() == untagged
    assert install_root.exists() is False
    assert result["installed"] is True
    assert result["action"] == "preserved-untagged"


# ===========================================================================
# Tier 2 -- real-install smoke (AC #13)
# ===========================================================================


@pytest.mark.posix_only
def test_real_install_smoke_against_fake_fork_repo(
    fake_cco_fork_repo, monkeypatch, tmp_path, path_with_local_bin
):
    """End-to-end smoke against the `file://` fixture: wrapper executes,
    --version matches the fixture's head_sha, then uninstall removes both
    artifacts cleanly. Replaces the dry-run AC #13 with a real-bytes
    smoke per F-C."""
    install_root = tmp_path / "clone"
    monkeypatch.setattr(spellbook_cco, "SPELLBOOK_CCO_REPO_URL", fake_cco_fork_repo["url"])
    monkeypatch.setattr(
        spellbook_cco,
        "SPELLBOOK_CCO_PINNED_SHA",
        fake_cco_fork_repo["head_sha"],
    )
    monkeypatch.delenv("SPELLBOOK_USE_VANILLA_CCO", raising=False)
    monkeypatch.delenv("SPELLBOOK_INSTALLER_SKIP_FORK_PIN", raising=False)

    install_result = install_spellbook_cco(install_root=install_root, dry_run=False)

    wrapper_path = spellbook_cco.SPELLBOOK_CCO_WRAPPER_PATH
    assert install_result["installed"] is True
    assert install_result["action"] == "installed"

    # The wrapper must `exec <install_root>/cco "$@"`. We invoke it with
    # `--version` and assert the captured stdout matches the install
    # clone's HEAD (the dynamic stub queries the clone's git at
    # runtime, so its output is the clone's short HEAD).
    assert wrapper_path.exists()
    proc = subprocess.run(
        [str(wrapper_path), "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    expected_head = subprocess.run(
        ["git", "-C", str(install_root), "rev-parse", "--short=7", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert proc.stdout == f"cco {expected_head} (installation)\n"
    # And that head MUST match the fixture's reported head_sha (because
    # `git checkout SPELLBOOK_CCO_PINNED_SHA` on a single-commit clone
    # is a no-op).
    assert expected_head == fake_cco_fork_repo["head_sha"]

    # Uninstall removes wrapper AND clone (clone was created by us, marker
    # file is present).
    uninstall_result = uninstall_spellbook_cco(install_root=install_root, dry_run=False)

    assert wrapper_path.exists() is False
    assert install_root.exists() is False
    assert uninstall_result["installed"] is True
    assert uninstall_result["action"] == "removed"


# Sanity: keep shutil/Path imports referenced under linters even if a future
# refactor drops a usage. These two are exercised above; pyflakes-clean.
_ = shutil
_ = Path
