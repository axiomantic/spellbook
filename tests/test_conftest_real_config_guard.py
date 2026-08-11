"""Tests for the real-user-config guard's path resolution.

``tests/conftest.py`` fingerprints the developer's genuine ``spellbook.json``
before and after every test and fails the test that changed it. The guard is
only as good as the path it watches, and that path is platform-dependent --
``spellbook.core.compat.get_config_dir`` resolves ``%APPDATA%`` on Windows and
``$HOME/.config`` elsewhere.

It used to hardcode the POSIX path on every platform, so on Windows it watched
a file that does not exist: it fingerprinted "absent" before and after every
test and could never fire. The protection silently covered two of the three
platforms CI runs on, and the model-tier tests added in PR #447 walked straight
through it -- they redirected only HOME and USERPROFILE and wrote to the real
Windows config, with the guard saying nothing.

The Windows branch is exercised here from POSIX by injection, because a
platform branch only its own platform can run is exactly how that survived.
"""

from pathlib import Path

from tests.conftest import _real_user_config_path


class TestPosix:
    def test_resolves_under_dot_config(self):
        resolved = _real_user_config_path(platform="linux", env={}, home="/home/ada")
        assert resolved == Path("/home/ada/.config/spellbook/spellbook.json")

    def test_ignores_appdata(self):
        """APPDATA is meaningless on POSIX; honouring it would point the guard
        at a path the runtime never writes."""
        resolved = _real_user_config_path(
            platform="darwin", env={"APPDATA": "/nope"}, home="/Users/ada"
        )
        assert resolved == Path("/Users/ada/.config/spellbook/spellbook.json")


class TestWindows:
    def test_uses_appdata(self):
        resolved = _real_user_config_path(
            platform="win32",
            env={"APPDATA": r"C:\Users\ada\AppData\Roaming"},
            home=r"C:\Users\ada",
        )
        assert resolved == Path(r"C:\Users\ada\AppData\Roaming") / "spellbook" / "spellbook.json"

    def test_falls_back_to_roaming_under_home_without_appdata(self):
        resolved = _real_user_config_path(platform="win32", env={}, home=r"C:\Users\ada")
        assert resolved == Path(r"C:\Users\ada") / "AppData" / "Roaming" / "spellbook" / "spellbook.json"

    def test_does_not_resolve_to_the_posix_path(self):
        """The regression itself. The old code returned ~/.config/... here,
        which does not exist on Windows -- so the guard fingerprinted 'absent'
        forever and never fired."""
        resolved = _real_user_config_path(
            platform="win32",
            env={"APPDATA": r"C:\Users\ada\AppData\Roaming"},
            home=r"C:\Users\ada",
        )
        assert ".config" not in resolved.parts


class TestLiveResolution:
    def test_matches_the_runtime_resolver_on_this_platform(self):
        """The guard and the runtime must agree about where the real config
        is, or the guard watches the wrong file. Compared against the actual
        resolver rather than a second hardcoded literal."""
        from spellbook.core.compat import get_config_dir

        assert _real_user_config_path() == get_config_dir("spellbook") / "spellbook.json"

    def test_module_constant_is_absolute(self):
        from tests import conftest

        assert conftest.REAL_USER_CONFIG_PATH.is_absolute()
