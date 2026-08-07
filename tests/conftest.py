"""Pytest configuration for spellbook tests."""

import hashlib
import os
import sys
from pathlib import Path

import pytest

# Resolved at conftest import, before any test can redirect ``HOME``. This is
# the developer's (or CI user's) genuine config file -- the one no test is ever
# allowed to touch.
REAL_USER_CONFIG_PATH = Path(os.path.expanduser("~")) / ".config" / "spellbook" / "spellbook.json"


def _real_user_config_fingerprint() -> tuple:
    """(exists, sha256, mtime_ns, size) of the real user config file.

    Absent file is a valid state and fingerprints as such, so a test that
    *creates* the real config is caught just as loudly as one that edits it.
    """
    try:
        raw = REAL_USER_CONFIG_PATH.read_bytes()
        st = REAL_USER_CONFIG_PATH.stat()
    except FileNotFoundError:
        return (False, None, None, None)
    except OSError:
        return (False, None, None, None)
    return (True, hashlib.sha256(raw).hexdigest(), st.st_mtime_ns, st.st_size)


_REAL_CONFIG_GUARD_MESSAGE = (
    "TEST ISOLATION FAILURE: the real user config at {path} was modified during "
    "the test run.\n"
    "  before: {before}\n"
    "  after:  {after}\n\n"
    "``spellbook.core.compat.get_config_dir`` resolves ``Path.home()/.config/spellbook`` "
    "and does NOT consult $SPELLBOOK_CONFIG_DIR. Setting that env var therefore isolates "
    "nothing for anything routed through ``spellbook.core.config`` (config_get, config_set, "
    "config_set_many, config_is_explicitly_set, get_config_path).\n"
    "Fix: redirect HOME instead -- ``monkeypatch.setenv(\"HOME\", str(tmp_path))``."
)


@pytest.fixture(scope="session", autouse=True)
def _guard_real_user_config_session():
    """Backstop: catch real-config writes from session fixtures or collection.

    The per-test guard below attributes pollution to a specific test. This one
    covers everything that happens outside a test body.
    """
    before = _real_user_config_fingerprint()
    yield
    after = _real_user_config_fingerprint()
    if before != after:
        raise AssertionError(
            _REAL_CONFIG_GUARD_MESSAGE.format(
                path=REAL_USER_CONFIG_PATH, before=before, after=after
            )
        )


@pytest.fixture(autouse=True)
def _guard_real_user_config(request):
    """Fail the offending test if it mutates the developer's real config file.

    Function-scoped so the failure names the exact test rather than surfacing
    at session teardown with no attribution. The file is small; two reads per
    test is a negligible cost for closing a defect that already wrote 14 stray
    ``rules.module.*`` keys into a real user's ``spellbook.json``.

    Tests that deliberately exercise this guard mark themselves
    ``allow_real_config_write`` and opt out.
    """
    if request.node.get_closest_marker("allow_real_config_write"):
        yield
        return
    before = _real_user_config_fingerprint()
    yield
    after = _real_user_config_fingerprint()
    if before != after:
        raise AssertionError(
            _REAL_CONFIG_GUARD_MESSAGE.format(
                path=REAL_USER_CONFIG_PATH, before=before, after=after
            )
        )



def _current_platform() -> str:
    """Return the current ``sys.platform``.

    Indirection so tests can redirect the platform probe (see ``tests/installer/test_marks.py``)
    via ``tripwire.mock("tests.conftest:_current_platform")`` instead of patching
    the module-level ``sys.platform`` attribute.
    """
    return sys.platform


def pytest_collection_modifyitems(config, items):
    skip_docker = pytest.mark.skip(reason="docker tests only run in CI (use --run-docker)")
    skip_posix_only = pytest.mark.skip(reason="POSIX only")
    skip_windows_only = pytest.mark.skip(reason="Windows only")
    run_docker = config.getoption("--run-docker")
    is_windows = _current_platform().startswith("win")

    for item in items:
        if not run_docker and "docker" in item.keywords:
            item.add_marker(skip_docker)
        if "windows_only" in item.keywords and not is_windows:
            item.add_marker(skip_windows_only)
        if "posix_only" in item.keywords and is_windows:
            item.add_marker(skip_posix_only)


def pytest_addoption(parser):
    parser.addoption(
        "--run-docker",
        action="store_true",
        default=False,
        help="Run docker-marked tests (skipped by default, intended for CI)",
    )
