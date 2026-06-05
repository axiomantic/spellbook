"""Tests for the ``admin_build`` installer component.

The ``admin_build`` component compiles the admin SPA at install/update time
by running ``npm ci --legacy-peer-deps`` followed by ``npm run build`` in
``spellbook/admin/frontend``. The built bundle (previously committed to the
repo under ``spellbook/admin/static/``) is now generated on the operator's
machine during installation.

Node and npm are a HARD requirement: if either binary is missing, the
component fails the install with an actionable error instead of silently
shipping a stale or absent bundle.

All ``subprocess.run`` calls are mocked so the real ``npm`` binary is never
invoked. ``shutil.which`` is patched to control node/npm availability.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import pytest


@dataclass
class _FakeCompleted:
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


@dataclass
class _RunRecorder:
    """Records every ``subprocess.run`` invocation (argv, cwd, timeout).

    ``cwd`` is recorded verbatim (a ``pathlib.Path``, not stringified) so
    tests can assert the component passes the frontend directory as a
    ``Path`` rather than a ``str``. ``timeout`` is recorded so tests can pin
    the per-call timeout contract. If a recorded result is a
    ``BaseException`` instance it is raised instead of returned, letting
    tests simulate ``subprocess.TimeoutExpired``.
    """

    calls: List[Tuple[List[str], Optional[Path], Optional[int]]] = field(
        default_factory=list
    )
    results: Optional[List[object]] = None

    def __call__(self, cmd, *args, **kwargs):
        argv = list(cmd) if isinstance(cmd, list) else [cmd]
        cwd = kwargs.get("cwd")
        timeout = kwargs.get("timeout")
        self.calls.append((argv, cwd, timeout))
        if self.results:
            result = self.results.pop(0)
            if isinstance(result, BaseException):
                raise result
            return result
        return _FakeCompleted(returncode=0, stdout="", stderr="")


@pytest.fixture
def frontend_dir(tmp_path):
    """A fake spellbook_dir whose admin frontend directory exists."""
    spellbook_dir = tmp_path / "spellbook-src"
    fe = spellbook_dir / "spellbook" / "admin" / "frontend"
    fe.mkdir(parents=True)
    (fe / "package.json").write_text('{"name": "spellbook-admin"}\n')
    return spellbook_dir


def _which_factory(available: dict):
    """Build a ``shutil.which`` replacement from a {name: path} map."""
    def fake_which(name, *args, **kwargs):
        return available.get(name)
    return fake_which


def test_build_runs_npm_ci_then_build_in_frontend_dir(frontend_dir, monkeypatch):
    """Happy path: both node and npm present -> exactly two subprocess
    calls in order, each cwd'd to the frontend directory (passed as a
    ``Path``, not a ``str``), each with an explicit ``timeout=300``, with
    the exact argv contract (``npm ci --legacy-peer-deps`` then
    ``npm run build``).
    """
    import installer.components.admin_build as admin_build_mod

    recorder = _RunRecorder()
    monkeypatch.setattr(admin_build_mod.subprocess, "run", recorder)
    monkeypatch.setattr(
        admin_build_mod.shutil,
        "which",
        _which_factory({"node": "/usr/bin/node", "npm": "/usr/bin/npm"}),
    )

    fe = frontend_dir / "spellbook" / "admin" / "frontend"

    ok, msg = admin_build_mod.build_admin_frontend(frontend_dir)

    assert (ok, msg) == (True, "Admin SPA built (npm ci + npm run build)")
    assert recorder.calls == [
        (["npm", "ci", "--legacy-peer-deps"], fe, 300),
        (["npm", "run", "build"], fe, 300),
    ]


def test_missing_node_hard_fails_with_actionable_message(frontend_dir, monkeypatch):
    """node absent -> hard fail, no subprocess invoked, exact error text."""
    import installer.components.admin_build as admin_build_mod

    recorder = _RunRecorder()
    monkeypatch.setattr(admin_build_mod.subprocess, "run", recorder)
    monkeypatch.setattr(
        admin_build_mod.shutil,
        "which",
        _which_factory({"npm": "/usr/bin/npm"}),  # node missing
    )

    ok, msg = admin_build_mod.build_admin_frontend(frontend_dir)

    assert (ok, msg) == (
        False,
        "node is required to build the admin SPA but was not found on PATH. "
        "Install Node.js (https://nodejs.org) and re-run the spellbook installer.",
    )
    assert recorder.calls == []


def test_missing_npm_hard_fails_with_actionable_message(frontend_dir, monkeypatch):
    """npm absent -> hard fail, no subprocess invoked, exact error text."""
    import installer.components.admin_build as admin_build_mod

    recorder = _RunRecorder()
    monkeypatch.setattr(admin_build_mod.subprocess, "run", recorder)
    monkeypatch.setattr(
        admin_build_mod.shutil,
        "which",
        _which_factory({"node": "/usr/bin/node"}),  # npm missing
    )

    ok, msg = admin_build_mod.build_admin_frontend(frontend_dir)

    assert (ok, msg) == (
        False,
        "npm is required to build the admin SPA but was not found on PATH. "
        "Install Node.js (https://nodejs.org) and re-run the spellbook installer.",
    )
    assert recorder.calls == []


def test_npm_ci_failure_aborts_before_build(frontend_dir, monkeypatch):
    """If ``npm ci`` exits non-zero, the build step must NOT run and the
    failure (stderr) is surfaced verbatim.
    """
    import installer.components.admin_build as admin_build_mod

    recorder = _RunRecorder(results=[
        _FakeCompleted(returncode=1, stdout="", stderr="ERESOLVE could not resolve"),
    ])
    monkeypatch.setattr(admin_build_mod.subprocess, "run", recorder)
    monkeypatch.setattr(
        admin_build_mod.shutil,
        "which",
        _which_factory({"node": "/usr/bin/node", "npm": "/usr/bin/npm"}),
    )

    fe = frontend_dir / "spellbook" / "admin" / "frontend"

    ok, msg = admin_build_mod.build_admin_frontend(frontend_dir)

    assert (ok, msg) == (
        False,
        "npm ci --legacy-peer-deps failed: ERESOLVE could not resolve",
    )
    # Only the ci call ran; build was never attempted.
    assert recorder.calls == [
        (["npm", "ci", "--legacy-peer-deps"], fe, 300),
    ]


def test_npm_build_failure_is_surfaced(frontend_dir, monkeypatch):
    """``npm ci`` succeeds but ``npm run build`` fails -> both calls ran,
    build stderr surfaced verbatim.
    """
    import installer.components.admin_build as admin_build_mod

    recorder = _RunRecorder(results=[
        _FakeCompleted(returncode=0),
        _FakeCompleted(returncode=2, stdout="", stderr="tsc error TS2304"),
    ])
    monkeypatch.setattr(admin_build_mod.subprocess, "run", recorder)
    monkeypatch.setattr(
        admin_build_mod.shutil,
        "which",
        _which_factory({"node": "/usr/bin/node", "npm": "/usr/bin/npm"}),
    )

    fe = frontend_dir / "spellbook" / "admin" / "frontend"

    ok, msg = admin_build_mod.build_admin_frontend(frontend_dir)

    assert (ok, msg) == (
        False,
        "npm run build failed: tsc error TS2304",
    )
    assert recorder.calls == [
        (["npm", "ci", "--legacy-peer-deps"], fe, 300),
        (["npm", "run", "build"], fe, 300),
    ]


def test_npm_ci_timeout_hard_fails_before_build(frontend_dir, monkeypatch):
    """If ``npm ci`` exceeds its 300s timeout, ``subprocess.TimeoutExpired``
    is caught and surfaced as an exact failure message; the build step must
    NOT run.

    ESCAPE: test_npm_ci_timeout_hard_fails_before_build
      CLAIM: A TimeoutExpired from the ci call is caught and converted to an
             exact (False, "npm ci timed out after 300s") return, aborting
             before ``npm run build``.
      PATH:  which(node)+which(npm) pass -> frontend exists -> ci
             subprocess.run raises TimeoutExpired -> except branch returns.
      CHECK: (ok, msg) == (False, "npm ci timed out after 300s") AND only the
             ci call was recorded (build never attempted).
      MUTATION: (a) Omitting the ``timeout=300`` kwarg means the recorded
                call's third element would not be 300 -- the call-list
                equality fails. (b) Not catching TimeoutExpired lets the
                exception propagate, so the function never returns and the
                tuple assertion errors. (c) A wrong message string ("build
                timed out", missing "300s") fails the exact-equality check.
                (d) Failing to abort (running build anyway) makes the
                recorded call list have 2 entries, failing equality.
      ESCAPE: An implementation that caught TimeoutExpired but returned the
              build-timeout message would fail the exact message check.
      IMPACT: Without the timeout the installer can hang forever on a stuck
              npm registry; without the exact abort the build runs against a
              half-populated node_modules.
    """
    import installer.components.admin_build as admin_build_mod

    recorder = _RunRecorder(results=[
        subprocess.TimeoutExpired(cmd=["npm", "ci", "--legacy-peer-deps"], timeout=300),
    ])
    monkeypatch.setattr(admin_build_mod.subprocess, "run", recorder)
    monkeypatch.setattr(
        admin_build_mod.shutil,
        "which",
        _which_factory({"node": "/usr/bin/node", "npm": "/usr/bin/npm"}),
    )

    fe = frontend_dir / "spellbook" / "admin" / "frontend"

    ok, msg = admin_build_mod.build_admin_frontend(frontend_dir)

    assert (ok, msg) == (False, "npm ci timed out after 300s")
    assert recorder.calls == [
        (["npm", "ci", "--legacy-peer-deps"], fe, 300),
    ]


def test_npm_build_timeout_is_surfaced(frontend_dir, monkeypatch):
    """``npm ci`` succeeds but ``npm run build`` exceeds its 300s timeout ->
    both calls ran, the build TimeoutExpired is caught and surfaced as an
    exact failure message.

    ESCAPE: test_npm_build_timeout_is_surfaced
      CLAIM: A TimeoutExpired from the build call is caught and converted to
             an exact (False, "npm run build timed out after 300s") return.
      PATH:  which passes -> ci returns rc=0 -> build subprocess.run raises
             TimeoutExpired -> except branch returns.
      CHECK: (ok, msg) == (False, "npm run build timed out after 300s") AND
             both calls recorded, each with timeout=300.
      MUTATION: (a) Omitting ``timeout=300`` on the build call makes the
                recorded third element None, failing the call-list equality.
                (b) Not catching the build TimeoutExpired propagates the
                exception, erroring the assertion. (c) A swapped message
                (the ci-timeout text) fails the exact check.
      ESCAPE: An implementation reusing the ci-timeout message for the build
              path would fail the exact message assertion.
      IMPACT: A stuck tsc/vite build would hang the installer forever
              without the timeout; a wrong message misleads the operator.
    """
    import installer.components.admin_build as admin_build_mod

    recorder = _RunRecorder(results=[
        _FakeCompleted(returncode=0),
        subprocess.TimeoutExpired(cmd=["npm", "run", "build"], timeout=300),
    ])
    monkeypatch.setattr(admin_build_mod.subprocess, "run", recorder)
    monkeypatch.setattr(
        admin_build_mod.shutil,
        "which",
        _which_factory({"node": "/usr/bin/node", "npm": "/usr/bin/npm"}),
    )

    fe = frontend_dir / "spellbook" / "admin" / "frontend"

    ok, msg = admin_build_mod.build_admin_frontend(frontend_dir)

    assert (ok, msg) == (False, "npm run build timed out after 300s")
    assert recorder.calls == [
        (["npm", "ci", "--legacy-peer-deps"], fe, 300),
        (["npm", "run", "build"], fe, 300),
    ]


def test_missing_frontend_dir_hard_fails(tmp_path, monkeypatch):
    """If the frontend source directory is absent (corrupt checkout), the
    component hard-fails naming the expected path; no subprocess runs.
    """
    import installer.components.admin_build as admin_build_mod

    recorder = _RunRecorder()
    monkeypatch.setattr(admin_build_mod.subprocess, "run", recorder)
    monkeypatch.setattr(
        admin_build_mod.shutil,
        "which",
        _which_factory({"node": "/usr/bin/node", "npm": "/usr/bin/npm"}),
    )

    spellbook_dir = tmp_path / "spellbook-src"
    spellbook_dir.mkdir()
    expected_fe = spellbook_dir / "spellbook" / "admin" / "frontend"

    ok, msg = admin_build_mod.build_admin_frontend(spellbook_dir)

    assert (ok, msg) == (
        False,
        f"Admin frontend source not found at {expected_fe}; cannot build admin SPA.",
    )
    assert recorder.calls == []


def test_dry_run_makes_no_subprocess_calls(frontend_dir, monkeypatch):
    """dry_run reports intent and runs nothing, even with node/npm present."""
    import installer.components.admin_build as admin_build_mod

    recorder = _RunRecorder()
    monkeypatch.setattr(admin_build_mod.subprocess, "run", recorder)
    monkeypatch.setattr(
        admin_build_mod.shutil,
        "which",
        _which_factory({"node": "/usr/bin/node", "npm": "/usr/bin/npm"}),
    )

    ok, msg = admin_build_mod.build_admin_frontend(frontend_dir, dry_run=True)

    assert (ok, msg) == (
        True,
        "Would build admin SPA (npm ci --legacy-peer-deps + npm run build)",
    )
    assert recorder.calls == []


def test_dry_run_still_hard_fails_when_node_missing(frontend_dir, monkeypatch):
    """dry_run must NOT mask a missing-node failure: node is a hard
    requirement, so a dry-run install still reports the blocker.
    """
    import installer.components.admin_build as admin_build_mod

    recorder = _RunRecorder()
    monkeypatch.setattr(admin_build_mod.subprocess, "run", recorder)
    monkeypatch.setattr(
        admin_build_mod.shutil,
        "which",
        _which_factory({"npm": "/usr/bin/npm"}),  # node missing
    )

    ok, msg = admin_build_mod.build_admin_frontend(frontend_dir, dry_run=True)

    assert (ok, msg) == (
        False,
        "node is required to build the admin SPA but was not found on PATH. "
        "Install Node.js (https://nodejs.org) and re-run the spellbook installer.",
    )
    assert recorder.calls == []
