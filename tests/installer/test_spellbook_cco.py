"""Tests for ``installer/components/spellbook_cco.py``.

The module installs the elijahr/cco hardened fork and writes the
``~/.local/bin/spellbook-cco`` wrapper that is the canonical entry point
for spellbook-managed cco invocations.

Tier 0 -- pure constant assertions (no SUT execution).

Tier 1 -- subprocess plumbing intercepted via ``tripwire.subprocess``.
The SUT runs inside a tripwire sandbox; ``mock_run`` returns canned
responses for each git/cco invocation in registration (FIFO) order.

Tier 2 -- a real ``file://`` bare git repo built per-test by the
``fake_cco_fork_repo`` fixture; the fork-installation code path
exercises ``git clone``, ``git fetch``, ``git rev-parse``, and ``cco
--version`` parsing against an actual on-disk repo. Tier 2 tests run
OUTSIDE the tripwire sandbox -- they need real subprocess for the
fixture-aware code paths, and tripwire's plugin interception cannot
coexist with passthrough subprocess inside ``with tripwire:`` (the
sandbox short-circuits the firewall ALLOW that ``@pytest.mark.allow``
provides).

Authoritative contract: the orchestrator's task brief at
``Phase 4 -- Task 1 / Task 2``. The wrapper template, SHA constant, and
module function signatures are reproduced verbatim below as test-time
expected values; deviations from the contract surface as test failures.

Mocking discipline -- tripwire only (per AGENTS.md):

The four module-level constants (``SPELLBOOK_CCO_WRAPPER_DIR``,
``_WRAPPER_PATH``, ``_REPO_URL``, ``_PINNED_SHA``) are bare attribute
reads and so are not interceptable by tripwire (which intercepts
callable invocations only). The SUT exposes keyword-only overrides
(``repo_url``, ``pinned_sha``, ``wrapper_dir``, ``wrapper_path``,
``verify_pin_fn``) on ``install_spellbook_cco`` and ``wrapper_path`` on
``uninstall_spellbook_cco`` so tests pass redirected paths/values
directly without monkeypatching module attributes (forbidden) or
mocking the getters via tripwire (cannot coexist with real subprocess
in Tier 2). Production callers leave the overrides at ``None`` and the
SUT falls back to the module-level getters.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest
import tripwire

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
#   {install_root}:     absolute, resolved path of the fork clone
#   {pinned_sha}:       SPELLBOOK_CCO_PINNED_SHA at write time
#   {project_encoded}:  spellbook repo root with '/' -> '-', leading slash
#                       stripped (matches CLAUDE.md project-encoded
#                       convention). Used to address the per-repo
#                       ``~/.local/spellbook/docs/<project-encoded>/``
#                       audit-doc subtree.
# ---------------------------------------------------------------------------
EXPECTED_WRAPPER_TEMPLATE = (
    "#!/usr/bin/env bash\n"
    "# spellbook-cco-managed: v1\n"
    "# Source:    {install_root} (fork of nikvdp/cco @ {pinned_sha})\n"
    "# Audit:     ~/.local/spellbook/docs/{project_encoded}"
    "/verifications/sec_9_3_result.md\n"
    'exec "{install_root}/cco" "$@"\n'
)


def _expected_wrapper_text(
    install_root: Path,
    pinned_sha: str,
    spellbook_repo_root: Path | None = None,
) -> str:
    repo_root = (
        spellbook_repo_root
        if spellbook_repo_root is not None
        else spellbook_cco._get_spellbook_repo_root()
    )
    project_encoded = str(repo_root).lstrip("/").replace("/", "-")
    return EXPECTED_WRAPPER_TEMPLATE.format(
        install_root=str(install_root.resolve()),
        pinned_sha=pinned_sha,
        project_encoded=project_encoded,
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

    Single-commit pattern: the stub queries its own clone's git HEAD at
    runtime so the ``cco --version`` output ALWAYS matches whatever the
    clone's HEAD short SHA is, no matter how many times the fixture's
    commit gets amended. This dodges the "stub body contains a SHA which
    is itself part of the SHA computation" chicken-and-egg problem.
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
    subprocess.run(
        ["git", "-C", str(work), "checkout", "-B", "master"],
        check=True,
        capture_output=True,
    )

    cco = work / "cco"
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


# ---------------------------------------------------------------------------
# Tier-1 helper: stack tripwire.subprocess.mock_run FIFO for a happy
# install path.
# ---------------------------------------------------------------------------


def _stack_happy_install_subprocess(
    install_root: Path, pinned_sha: str, repo_url: str
) -> list[tuple[list[str], str]]:
    """Pre-stack tripwire.subprocess.mock_run FIFO for a happy install path.

    Returns a list of ``(command, stdout)`` pairs (one per stacked call) so
    callers can pass them to ``assert_run`` after the sandbox exits.

    The SUT issues these subprocess.run calls during a fresh install
    (install_root absent + use-vanilla off + skip-fork-pin off):

        1. git clone --depth 50 <repo_url> <install_root>
        2. git -C <install_root> checkout <pinned_sha>
        3. git -C <install_root> rev-parse --short=7 HEAD
        4. <install_root>/cco --version

    Per ``tripwire.subprocess.mock_run`` semantics, calls are matched in
    REGISTRATION order against the EXACT ``command=`` list. We register
    one mock per anticipated call. We do NOT pre-create install_root --
    doing so would route the SUT through the "install_root present"
    branch (remote.origin.url lookup) instead of clone. The SUT's
    marker-write logic creates ``<install_root>/.git/`` as a side-effect
    after the mocked clone.
    """
    expected: list[tuple[list[str], str]] = []

    clone_cmd = ["git", "clone", "--depth", "50", repo_url, install_root]
    tripwire.subprocess.mock_run(command=clone_cmd, returncode=0, stdout="")
    expected.append((clone_cmd, ""))

    checkout_cmd = ["git", "-C", install_root, "checkout", pinned_sha]
    tripwire.subprocess.mock_run(command=checkout_cmd, returncode=0, stdout="")
    expected.append((checkout_cmd, ""))

    rev_parse_cmd = ["git", "-C", install_root, "rev-parse", "--short=7", "HEAD"]
    rev_parse_stdout = pinned_sha + "\n"
    tripwire.subprocess.mock_run(
        command=rev_parse_cmd, returncode=0, stdout=rev_parse_stdout
    )
    expected.append((rev_parse_cmd, rev_parse_stdout))

    version_cmd = [install_root / "cco", "--version"]
    version_stdout = f"cco {pinned_sha} (installation)\n"
    tripwire.subprocess.mock_run(
        command=version_cmd, returncode=0, stdout=version_stdout
    )
    expected.append((version_cmd, version_stdout))

    return expected


# ===========================================================================
# Tier 0 -- pure constant assertions (no mocking needed)
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
    """The namespaced wrapper tag is ``# spellbook-cco-managed: v1``."""
    assert SPELLBOOK_CCO_WRAPPER_TAG == "# spellbook-cco-managed: v1"


# ===========================================================================
# Tier 1 -- subprocess plumbing intercepted via tripwire.subprocess
# ===========================================================================


@pytest.mark.posix_only
def test_install_calls_git_clone(monkeypatch, tmp_path):
    """The install path invokes ``git clone`` on the configured remote URL."""
    install_root = tmp_path / "clone"
    wrapper_dir, wrapper_path = _empty_wrapper_dir(tmp_path)

    monkeypatch.delenv("SPELLBOOK_USE_VANILLA_CCO", raising=False)
    monkeypatch.delenv("SPELLBOOK_INSTALLER_SKIP_FORK_PIN", raising=False)
    # Put wrapper_dir on PATH so the no-PATH warning does not fire.
    monkeypatch.setenv("PATH", f"{wrapper_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    expected = _stack_happy_install_subprocess(
        install_root, SPELLBOOK_CCO_PINNED_SHA, SPELLBOOK_CCO_REPO_URL
    )

    with tripwire:
        result = install_spellbook_cco(
            install_root=install_root,
            dry_run=False,
            wrapper_dir=wrapper_dir,
            wrapper_path=wrapper_path,
        )

    for cmd, stdout in expected:
        tripwire.subprocess.assert_run(
            command=cmd, returncode=0, stdout=stdout, stderr=""
        )

    assert result["installed"] is True
    clone_cmds = [c for c, _ in expected if c[:2] == ["git", "clone"]]
    assert len(clone_cmds) == 1
    assert SPELLBOOK_CCO_REPO_URL in clone_cmds[0]
    assert install_root in clone_cmds[0]


def test_install_dry_run_does_not_clone(monkeypatch, tmp_path):
    """``dry_run=True`` performs zero subprocess + zero filesystem writes.

    Tripwire enforces the "zero subprocess" property automatically: no
    ``mock_run`` is registered, so any subprocess.run invocation would
    raise ``UnmockedInteractionError`` inside the sandbox.
    """
    install_root = tmp_path / "clone"
    wrapper_dir, wrapper_path = _empty_wrapper_dir(tmp_path)

    monkeypatch.delenv("SPELLBOOK_USE_VANILLA_CCO", raising=False)

    with tripwire:
        result = install_spellbook_cco(
            install_root=install_root,
            dry_run=True,
            wrapper_dir=wrapper_dir,
            wrapper_path=wrapper_path,
        )

    assert install_root.exists() is False
    assert wrapper_path.exists() is False
    assert result == {
        "installed": False,
        "path": str(wrapper_path),
        "skipped_reason": "dry-run",
        "action": "noop",
        "install_root": str(install_root),
    }


def test_uninstall_dry_run_does_not_remove(tmp_path):
    """``dry_run=True`` for uninstall returns shape; no FS mutation."""
    wrapper_dir = tmp_path / "wrapper-bin"
    wrapper_dir.mkdir()
    wrapper_path = wrapper_dir / "spellbook-cco"
    install_root = tmp_path / "clone"
    install_root.mkdir()
    wrapper_text = _expected_wrapper_text(install_root, SPELLBOOK_CCO_PINNED_SHA)
    wrapper_path.write_text(wrapper_text)
    wrapper_path.chmod(0o755)
    (install_root / ".spellbook-cco-managed").write_text("v1\n")

    with tripwire:
        result = uninstall_spellbook_cco(
            install_root=install_root,
            dry_run=True,
            wrapper_path=wrapper_path,
        )

    assert wrapper_path.exists() is True
    assert install_root.exists() is True
    assert result == {
        "installed": True,
        "path": str(wrapper_path),
        "skipped_reason": "dry-run",
        "action": "noop",
    }


@pytest.mark.posix_only
def test_install_returns_dict_shape_on_success(monkeypatch, tmp_path):
    """Full success path returns the orchestrator-locked dict shape."""
    install_root = tmp_path / "clone"
    wrapper_dir, wrapper_path = _empty_wrapper_dir(tmp_path)

    monkeypatch.delenv("SPELLBOOK_USE_VANILLA_CCO", raising=False)
    monkeypatch.delenv("SPELLBOOK_INSTALLER_SKIP_FORK_PIN", raising=False)
    monkeypatch.setenv("PATH", f"{wrapper_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    expected = _stack_happy_install_subprocess(
        install_root, SPELLBOOK_CCO_PINNED_SHA, SPELLBOOK_CCO_REPO_URL
    )

    with tripwire:
        result = install_spellbook_cco(
            install_root=install_root,
            dry_run=False,
            wrapper_dir=wrapper_dir,
            wrapper_path=wrapper_path,
        )

    for cmd, stdout in expected:
        tripwire.subprocess.assert_run(
            command=cmd, returncode=0, stdout=stdout, stderr=""
        )

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
    assert result["path"] == str(wrapper_path)
    assert result["install_root"] == str(install_root.resolve())


def test_uninstall_returns_dict_shape(tmp_path):
    """Uninstall on a clean machine returns the noop shape."""
    wrapper_dir = tmp_path / "wrapper-bin"
    wrapper_dir.mkdir()
    wrapper_path = wrapper_dir / "spellbook-cco"
    install_root = tmp_path / "clone"  # absent

    with tripwire:
        result = uninstall_spellbook_cco(
            install_root=install_root,
            dry_run=False,
            wrapper_path=wrapper_path,
        )

    assert result == {
        "installed": False,
        "path": None,
        "skipped_reason": "nothing to uninstall",
        "action": "noop",
    }


# ===========================================================================
# Tier 2 -- real `file://` bare repo + real subprocess + real wrapper writes
#
# These tests run OUTSIDE the tripwire sandbox because they need real
# subprocess for ``git clone file://...``, ``git fetch``, etc. The
# SUT's overrides (``repo_url=``, ``pinned_sha=``, ``wrapper_dir=``,
# ``wrapper_path=``, ``verify_pin_fn=``) replace the constants/helpers
# directly, so no mocking is needed -- the SUT runs with explicit
# dependencies instead.
# ===========================================================================


@pytest.mark.posix_only
def test_install_clones_then_verifies_pin_against_fake_repo(
    fake_cco_fork_repo, monkeypatch, tmp_path
):
    """Full happy path against the real `file://` fixture.

    Step 1 (``git rev-parse``) and step 2 (``cco --version`` awk parse)
    are healthy because the fixture's stub emits the fixture's actual
    head_sha verbatim. We override ``repo_url`` and ``pinned_sha`` to
    align with the fixture's URL + head_sha.
    """
    install_root = tmp_path / "clone"
    wrapper_dir, wrapper_path = _empty_wrapper_dir(tmp_path)

    monkeypatch.delenv("SPELLBOOK_USE_VANILLA_CCO", raising=False)
    monkeypatch.delenv("SPELLBOOK_INSTALLER_SKIP_FORK_PIN", raising=False)
    monkeypatch.setenv("PATH", f"{wrapper_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    result = install_spellbook_cco(
        install_root=install_root,
        dry_run=False,
        repo_url=fake_cco_fork_repo["url"],
        pinned_sha=fake_cco_fork_repo["head_sha"],
        wrapper_dir=wrapper_dir,
        wrapper_path=wrapper_path,
    )

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
    fake_cco_fork_repo, monkeypatch, tmp_path, capsys
):
    """``_verify_pin`` step 1 mismatch -> rollback + no wrapper write."""
    install_root = tmp_path / "clone"
    wrapper_dir, wrapper_path = _empty_wrapper_dir(tmp_path)

    monkeypatch.delenv("SPELLBOOK_USE_VANILLA_CCO", raising=False)
    monkeypatch.delenv("SPELLBOOK_INSTALLER_SKIP_FORK_PIN", raising=False)

    result = install_spellbook_cco(
        install_root=install_root,
        dry_run=False,
        repo_url=fake_cco_fork_repo["url"],
        pinned_sha="deadbee",  # intentionally != fixture's head_sha
        wrapper_dir=wrapper_dir,
        wrapper_path=wrapper_path,
    )

    assert wrapper_path.exists() is False
    assert install_root.exists() is False
    assert result["installed"] is False
    assert result["action"] == "skipped"
    expected_failure = (
        f"pin verification failed: expected deadbee, got {fake_cco_fork_repo['head_sha']}"
    )
    assert result["skipped_reason"] == expected_failure

    captured = capsys.readouterr()
    assert captured.err == f"WARNING: {expected_failure}\n"


@pytest.mark.posix_only
def test_install_rolls_back_when_version_parse_mismatch(
    fake_cco_fork_repo, monkeypatch, tmp_path, capsys
):
    """``_verify_pin`` step 2 mismatch -> rollback.

    We inject a ``verify_pin_fn`` wrapper that first overwrites the
    fixture's cco stub with a STATIC stub emitting ``cco deadbee``, then
    delegates to the real ``_verify_pin``. Step 1 still matches (git
    rev-parse = fixture head_sha = configured pin), but step 2 diverges
    because the patched stub hardcodes a different sha.
    """
    install_root = tmp_path / "clone"
    wrapper_dir, wrapper_path = _empty_wrapper_dir(tmp_path)

    monkeypatch.delenv("SPELLBOOK_USE_VANILLA_CCO", raising=False)
    monkeypatch.delenv("SPELLBOOK_INSTALLER_SKIP_FORK_PIN", raising=False)

    real_verify = spellbook_cco._verify_pin

    def patched_verify(root, sha):
        # Overwrite the dynamic self-querying stub with a STATIC stub
        # that hardcodes a wrong SHA so step 2 (--version awk parse)
        # diverges from step 1 (git rev-parse, which still reports the
        # real HEAD).
        cco_path = Path(root) / "cco"
        cco_path.write_text("#!/bin/sh\nprintf 'cco deadbee (installation)\\n'\n")
        cco_path.chmod(0o755)
        return real_verify(root, sha)

    result = install_spellbook_cco(
        install_root=install_root,
        dry_run=False,
        repo_url=fake_cco_fork_repo["url"],
        pinned_sha=fake_cco_fork_repo["head_sha"],
        wrapper_dir=wrapper_dir,
        wrapper_path=wrapper_path,
        verify_pin_fn=patched_verify,
    )

    assert wrapper_path.exists() is False
    assert install_root.exists() is False
    assert result["installed"] is False
    assert result["action"] == "skipped"
    expected_failure = (
        f"pin verification failed: expected {fake_cco_fork_repo['head_sha']}, got deadbee"
    )
    assert result["skipped_reason"] == expected_failure

    captured = capsys.readouterr()
    assert captured.err == f"WARNING: {expected_failure}\n"


@pytest.mark.posix_only
def test_install_idempotent_on_second_run(fake_cco_fork_repo, monkeypatch, tmp_path):
    """Second run on a healthy install returns ``action="noop"`` and does
    NOT rewrite the wrapper bytes."""
    install_root = tmp_path / "clone"
    wrapper_dir, wrapper_path = _empty_wrapper_dir(tmp_path)

    monkeypatch.delenv("SPELLBOOK_USE_VANILLA_CCO", raising=False)
    monkeypatch.delenv("SPELLBOOK_INSTALLER_SKIP_FORK_PIN", raising=False)
    monkeypatch.setenv("PATH", f"{wrapper_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    kwargs = dict(
        install_root=install_root,
        dry_run=False,
        repo_url=fake_cco_fork_repo["url"],
        pinned_sha=fake_cco_fork_repo["head_sha"],
        wrapper_dir=wrapper_dir,
        wrapper_path=wrapper_path,
    )

    first = install_spellbook_cco(**kwargs)
    assert first["installed"] is True
    assert first["action"] == "installed"
    first_text = wrapper_path.read_text()
    first_mtime = wrapper_path.stat().st_mtime_ns

    second = install_spellbook_cco(**kwargs)

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
    fake_cco_fork_repo, monkeypatch, tmp_path, capsys
):
    """An untagged operator-rolled wrapper at the target path is overwritten
    AND a WARNING is emitted to stderr."""
    install_root = tmp_path / "clone"
    wrapper_dir, wrapper_path = _empty_wrapper_dir(tmp_path)

    monkeypatch.delenv("SPELLBOOK_USE_VANILLA_CCO", raising=False)
    monkeypatch.setenv("PATH", f"{wrapper_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    wrapper_path.write_text('#!/bin/sh\n# Source: /home/op/dev/cco-checkout\nexec cco "$@"\n')
    wrapper_path.chmod(0o755)

    result = install_spellbook_cco(
        install_root=install_root,
        dry_run=False,
        repo_url=fake_cco_fork_repo["url"],
        pinned_sha=fake_cco_fork_repo["head_sha"],
        wrapper_dir=wrapper_dir,
        wrapper_path=wrapper_path,
    )

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
    fake_cco_fork_repo, monkeypatch, tmp_path, capsys
):
    """When the wrapper dir is not on PATH, the installer writes the wrapper
    anyway, returns ``installed=True``, and emits a stderr WARNING."""
    install_root = tmp_path / "clone"
    wrapper_dir, wrapper_path = _empty_wrapper_dir(tmp_path)

    monkeypatch.delenv("SPELLBOOK_USE_VANILLA_CCO", raising=False)
    monkeypatch.delenv("SPELLBOOK_INSTALLER_SKIP_FORK_PIN", raising=False)
    # Strip the wrapper dir out of PATH.
    sanitized_path = os.pathsep.join(
        p
        for p in os.environ.get("PATH", "").split(os.pathsep)
        if p and Path(p) != wrapper_dir
    )
    monkeypatch.setenv("PATH", sanitized_path)

    result = install_spellbook_cco(
        install_root=install_root,
        dry_run=False,
        repo_url=fake_cco_fork_repo["url"],
        pinned_sha=fake_cco_fork_repo["head_sha"],
        wrapper_dir=wrapper_dir,
        wrapper_path=wrapper_path,
    )

    assert wrapper_path.exists()
    assert result["installed"] is True

    captured = capsys.readouterr()
    assert captured.err == _WARNING_PATH_NOT_SET


@pytest.mark.posix_only
def test_install_accepts_tilde_prefix_path_entry(
    fake_cco_fork_repo, monkeypatch, tmp_path, capsys
):
    """A PATH entry written as ``~/...`` (literal tilde) MUST be treated
    as equivalent to its ``expanduser``'d form.

    Regression guard for the PATH-membership normalization: the SUT
    resolves each PATH entry via ``Path(raw).expanduser().resolve()``
    before comparing against the resolved wrapper dir, so a tilde-prefix
    entry that names the wrapper dir must NOT trip the
    "not on PATH" WARNING.
    """
    install_root = tmp_path / "clone"

    # Place the wrapper dir UNDER a fake HOME so the tilde-prefix entry
    # is meaningful: ``~/wrapper-bin`` expands to ``<fake_home>/wrapper-bin``.
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    wrapper_dir = fake_home / "wrapper-bin"
    wrapper_dir.mkdir()
    wrapper_path = wrapper_dir / "spellbook-cco"

    monkeypatch.delenv("SPELLBOOK_USE_VANILLA_CCO", raising=False)
    monkeypatch.delenv("SPELLBOOK_INSTALLER_SKIP_FORK_PIN", raising=False)
    # Literal tilde in PATH entry -- this is the variant under test.
    monkeypatch.setenv(
        "PATH", f"~/wrapper-bin{os.pathsep}{os.environ.get('PATH', '')}"
    )

    result = install_spellbook_cco(
        install_root=install_root,
        dry_run=False,
        repo_url=fake_cco_fork_repo["url"],
        pinned_sha=fake_cco_fork_repo["head_sha"],
        wrapper_dir=wrapper_dir,
        wrapper_path=wrapper_path,
    )

    assert wrapper_path.exists()
    assert result["installed"] is True

    captured = capsys.readouterr()
    # The PATH-not-set WARNING must NOT fire: the tilde entry expanded
    # to the wrapper dir.
    assert _WARNING_PATH_NOT_SET not in captured.err


@pytest.mark.posix_only
def test_install_accepts_trailing_slash_path_entry(
    fake_cco_fork_repo, monkeypatch, tmp_path, capsys
):
    """A PATH entry with a trailing slash MUST be treated as equivalent
    to the no-trailing-slash form.

    Regression guard for the PATH-membership normalization.
    """
    install_root = tmp_path / "clone"
    wrapper_dir, wrapper_path = _empty_wrapper_dir(tmp_path)

    monkeypatch.delenv("SPELLBOOK_USE_VANILLA_CCO", raising=False)
    monkeypatch.delenv("SPELLBOOK_INSTALLER_SKIP_FORK_PIN", raising=False)
    # Trailing-slash variant under test.
    monkeypatch.setenv(
        "PATH", f"{wrapper_dir}/{os.pathsep}{os.environ.get('PATH', '')}"
    )

    result = install_spellbook_cco(
        install_root=install_root,
        dry_run=False,
        repo_url=fake_cco_fork_repo["url"],
        pinned_sha=fake_cco_fork_repo["head_sha"],
        wrapper_dir=wrapper_dir,
        wrapper_path=wrapper_path,
    )

    assert wrapper_path.exists()
    assert result["installed"] is True

    captured = capsys.readouterr()
    assert _WARNING_PATH_NOT_SET not in captured.err


@pytest.mark.posix_only
def test_install_skips_empty_path_entries(
    fake_cco_fork_repo, monkeypatch, tmp_path, capsys
):
    """Empty entries in PATH (consecutive ``:`` on POSIX) MUST be
    skipped silently without raising or producing a spurious WARNING.

    Regression guard for the ``if not raw: continue`` short-circuit.
    """
    install_root = tmp_path / "clone"
    wrapper_dir, wrapper_path = _empty_wrapper_dir(tmp_path)

    monkeypatch.delenv("SPELLBOOK_USE_VANILLA_CCO", raising=False)
    monkeypatch.delenv("SPELLBOOK_INSTALLER_SKIP_FORK_PIN", raising=False)
    # Surround the wrapper dir with empty entries (leading, embedded,
    # trailing) so the empty-entry handler is exercised in all positions.
    sep = os.pathsep
    monkeypatch.setenv(
        "PATH",
        f"{sep}{sep}{wrapper_dir}{sep}{sep}{os.environ.get('PATH', '')}{sep}",
    )

    result = install_spellbook_cco(
        install_root=install_root,
        dry_run=False,
        repo_url=fake_cco_fork_repo["url"],
        pinned_sha=fake_cco_fork_repo["head_sha"],
        wrapper_dir=wrapper_dir,
        wrapper_path=wrapper_path,
    )

    assert wrapper_path.exists()
    assert result["installed"] is True

    captured = capsys.readouterr()
    # No spurious WARNING from empty-entry handling, and no exception.
    assert _WARNING_PATH_NOT_SET not in captured.err


# Note on the unresolvable-PATH-entry / logger.debug branch: triggering
# ``OSError``/``RuntimeError`` from ``Path(raw).expanduser().resolve(
# strict=False)`` on a real on-disk path is not portable -- ``strict=False``
# is intentionally forgiving (broken symlinks, missing components, perm
# errors on parents all return a non-canonicalized Path rather than raise).
# A reliable trigger requires patching ``pathlib.Path.resolve``, which
# this project's mocking discipline reserves for tripwire (see AGENTS.md
# section "Testing with Tripwire") and tripwire cannot scope a Path-method
# mock narrowly enough without breaking the SUT's other ``resolve()``
# calls in the same code path. The branch is exercised by inspection
# during code review instead; the tilde, trailing-slash, and empty-entry
# tests above cover the call-site's other normalization branches.


@pytest.mark.posix_only
def test_use_vanilla_cco_env_routes_to_skipped(monkeypatch, tmp_path, capsys):
    """``SPELLBOOK_USE_VANILLA_CCO=1`` returns the rollback shape AND emits
    a stderr WARNING. Does NOT clone, does NOT touch the wrapper.

    Tripwire enforces "does not clone" automatically: no ``mock_run`` is
    registered inside the sandbox so any subprocess.run would raise
    ``UnmockedInteractionError``.
    """
    monkeypatch.setenv("SPELLBOOK_USE_VANILLA_CCO", "1")
    install_root = tmp_path / "clone"
    wrapper_dir, wrapper_path = _empty_wrapper_dir(tmp_path)

    with tripwire:
        result = install_spellbook_cco(
            install_root=install_root,
            dry_run=False,
            wrapper_dir=wrapper_dir,
            wrapper_path=wrapper_path,
        )

    assert install_root.exists() is False
    assert wrapper_path.exists() is False
    assert result == {
        "installed": False,
        "path": None,
        "skipped_reason": ("SPELLBOOK_USE_VANILLA_CCO=1 active; routing to legacy vanilla cco"),
        "action": "skipped",
        "install_root": None,
    }

    captured = capsys.readouterr()
    assert captured.err == _WARNING_USE_VANILLA_CCO


@pytest.mark.posix_only
def test_install_succeeds_with_SKIP_FORK_PIN_at_wrong_sha(
    fake_cco_fork_repo, monkeypatch, tmp_path, capsys
):
    """``SPELLBOOK_INSTALLER_SKIP_FORK_PIN=1`` skips BOTH pin steps even at
    a mismatched pin, emits the canonical stderr WARNING, and the install
    succeeds with the wrapper written and mode 0755.
    """
    install_root = tmp_path / "clone"
    wrapper_dir, wrapper_path = _empty_wrapper_dir(tmp_path)

    # Intentionally pass production's pinned_sha which deliberately
    # mismatches the fixture's head_sha. The skip-env-var must make the
    # install succeed anyway.
    assert SPELLBOOK_CCO_PINNED_SHA != fake_cco_fork_repo["head_sha"]
    monkeypatch.setenv("SPELLBOOK_INSTALLER_SKIP_FORK_PIN", "1")
    monkeypatch.delenv("SPELLBOOK_USE_VANILLA_CCO", raising=False)
    monkeypatch.setenv("PATH", f"{wrapper_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    result = install_spellbook_cco(
        install_root=install_root,
        dry_run=False,
        repo_url=fake_cco_fork_repo["url"],
        pinned_sha=SPELLBOOK_CCO_PINNED_SHA,  # mismatched intentionally
        wrapper_dir=wrapper_dir,
        wrapper_path=wrapper_path,
    )

    expected_text = _expected_wrapper_text(install_root, SPELLBOOK_CCO_PINNED_SHA)
    assert wrapper_path.exists()
    assert wrapper_path.read_text() == expected_text
    assert stat.S_IMODE(wrapper_path.stat().st_mode) == 0o755
    assert result["installed"] is True
    assert result["action"] == "installed"
    assert result["skipped_reason"] is None

    captured = capsys.readouterr()
    assert captured.err == _WARNING_SKIP_FORK_PIN


def test_uninstall_removes_only_tagged_wrapper(tmp_path):
    """Uninstall removes the wrapper iff it bears the tag; an
    operator-rolled untagged wrapper is preserved."""
    wrapper_dir = tmp_path / "wrapper-bin"
    wrapper_dir.mkdir()
    wrapper_path = wrapper_dir / "spellbook-cco"
    install_root = tmp_path / "clone"
    install_root.mkdir()
    (install_root / ".spellbook-cco-managed").write_text("v1\n")

    # Case A: untagged wrapper -- preserved.
    untagged = '#!/bin/sh\n# operator-rolled\nexec /opt/local/cco "$@"\n'
    wrapper_path.write_text(untagged)
    wrapper_path.chmod(0o755)

    with tripwire:
        result_a = uninstall_spellbook_cco(
            install_root=install_root, dry_run=False, wrapper_path=wrapper_path
        )

    assert wrapper_path.exists()
    assert wrapper_path.read_text() == untagged
    assert result_a["action"] == "preserved-untagged"

    # Case B: tagged wrapper -- removed.
    tagged = _expected_wrapper_text(install_root, SPELLBOOK_CCO_PINNED_SHA)
    wrapper_path.write_text(tagged)
    wrapper_path.chmod(0o755)
    if not install_root.exists():
        install_root.mkdir()
        (install_root / ".spellbook-cco-managed").write_text("v1\n")

    with tripwire:
        result_b = uninstall_spellbook_cco(
            install_root=install_root, dry_run=False, wrapper_path=wrapper_path
        )

    assert wrapper_path.exists() is False
    assert result_b["installed"] is True
    assert result_b["action"] == "removed"


def test_uninstall_removes_clone_only_if_we_created_it(tmp_path):
    """Uninstall removes the install_root only if we created it (detected via
    the ``.spellbook-cco-managed`` marker we drop at install time). Other
    directories at the same path are preserved."""
    wrapper_dir = tmp_path / "wrapper-bin"
    wrapper_dir.mkdir()
    wrapper_path = wrapper_dir / "spellbook-cco"

    # Case A: install_root WITHOUT the managed marker -- preserved.
    foreign_root = tmp_path / "foreign-clone"
    foreign_root.mkdir()
    (foreign_root / "operator-data.txt").write_text("important")
    wrapper_path.write_text(_expected_wrapper_text(foreign_root, SPELLBOOK_CCO_PINNED_SHA))
    wrapper_path.chmod(0o755)

    with tripwire:
        result_a = uninstall_spellbook_cco(
            install_root=foreign_root, dry_run=False, wrapper_path=wrapper_path
        )

    assert foreign_root.exists()
    assert (foreign_root / "operator-data.txt").read_text() == "important"
    assert wrapper_path.exists() is False
    assert result_a["installed"] is True
    assert result_a["action"] == "removed"

    # Case B: install_root WITH the managed marker -- removed.
    managed_root = tmp_path / "managed-clone"
    managed_root.mkdir()
    (managed_root / ".spellbook-cco-managed").write_text("v1\n")
    (managed_root / "cco").write_text("#!/bin/sh\nexit 0\n")
    wrapper_path.write_text(_expected_wrapper_text(managed_root, SPELLBOOK_CCO_PINNED_SHA))
    wrapper_path.chmod(0o755)

    with tripwire:
        result_b = uninstall_spellbook_cco(
            install_root=managed_root, dry_run=False, wrapper_path=wrapper_path
        )

    assert managed_root.exists() is False
    assert wrapper_path.exists() is False
    assert result_b["installed"] is True
    assert result_b["action"] == "removed"


def test_uninstall_aggregation_untagged_wrapper_with_managed_clone(tmp_path):
    """Aggregation branch: untagged wrapper + managed clone.

    The wrapper is preserved (operator-rolled), and the managed clone
    IS removed silently. The top-level action MUST be
    "preserved-untagged" to surface the user-visible artifact.
    """
    wrapper_dir = tmp_path / "wrapper-bin"
    wrapper_dir.mkdir()
    wrapper_path = wrapper_dir / "spellbook-cco"

    untagged = '#!/bin/sh\n# operator-rolled\nexec /opt/local/cco "$@"\n'
    wrapper_path.write_text(untagged)
    wrapper_path.chmod(0o755)

    install_root = tmp_path / "managed-clone"
    install_root.mkdir()
    (install_root / ".spellbook-cco-managed").write_text("v1\n")
    (install_root / "cco").write_text("#!/bin/sh\nexit 0\n")

    with tripwire:
        result = uninstall_spellbook_cco(
            install_root=install_root, dry_run=False, wrapper_path=wrapper_path
        )

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
    fake_cco_fork_repo, monkeypatch, tmp_path
):
    """End-to-end smoke against the `file://` fixture: wrapper executes,
    --version matches the fixture's head_sha, then uninstall removes both
    artifacts cleanly."""
    install_root = tmp_path / "clone"
    wrapper_dir, wrapper_path = _empty_wrapper_dir(tmp_path)

    monkeypatch.delenv("SPELLBOOK_USE_VANILLA_CCO", raising=False)
    monkeypatch.delenv("SPELLBOOK_INSTALLER_SKIP_FORK_PIN", raising=False)
    monkeypatch.setenv("PATH", f"{wrapper_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    install_result = install_spellbook_cco(
        install_root=install_root,
        dry_run=False,
        repo_url=fake_cco_fork_repo["url"],
        pinned_sha=fake_cco_fork_repo["head_sha"],
        wrapper_dir=wrapper_dir,
        wrapper_path=wrapper_path,
    )

    assert install_result["installed"] is True
    assert install_result["action"] == "installed"

    # The wrapper must `exec <install_root>/cco "$@"`. We invoke it
    # with `--version` and assert the captured stdout matches the
    # install clone's HEAD.
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
    assert expected_head == fake_cco_fork_repo["head_sha"]

    # Uninstall removes wrapper AND clone (clone was created by us,
    # marker file is present).
    uninstall_result = uninstall_spellbook_cco(
        install_root=install_root, dry_run=False, wrapper_path=wrapper_path
    )

    assert wrapper_path.exists() is False
    assert install_root.exists() is False
    assert uninstall_result["installed"] is True
    assert uninstall_result["action"] == "removed"


# Sanity: keep shutil/Path imports referenced under linters even if a future
# refactor drops a usage. These two are exercised above; pyflakes-clean.
_ = shutil
_ = Path
