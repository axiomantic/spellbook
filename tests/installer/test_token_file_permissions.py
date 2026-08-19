"""Every installer that writes the MCP bearer token must write mode 0600.

The bearer token at ``~/.local/spellbook/.mcp-token`` is mode 0600 at its
source. Installers copy it into per-platform config files, and those copies
must not be readable by other local accounts.

The set of installers under test is DERIVED from ``installer/platforms/``
rather than hand-listed, so a platform added later is covered without anyone
remembering to extend this file. Discovery has a floor: a scan that finds
nothing would report a clean pass over an unchecked tree.

The pre-existing-file case is the one that matters. ``os.open``'s ``mode``
argument applies only to files it CREATES; a config file already on disk at
0644 survives ``O_TRUNC`` with its mode intact. Only an explicit ``fchmod``
tightens it.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PLATFORMS_DIR = REPO_ROOT / "installer" / "platforms"

# A platform module reads the token only through this accessor, so its
# presence in the source is what makes a module token-bearing.
TOKEN_ACCESSOR = "get_mcp_auth_token"

# Measured: 6 modules mention TOKEN_ACCESSOR at the time of writing
# (antigravity, codex, forgecode, goose, opencode, pi). The floor is the
# anti-no-op guard, not the exact count -- a new platform raises the real
# number without touching this constant.
MODULE_FLOOR = 6


def _token_bearing_modules() -> set:
    """Return the stem of every platform module that reads the bearer token."""
    found = set()
    for path in sorted(PLATFORMS_DIR.glob("*.py")):
        if path.name == "__init__.py":
            continue
        if TOKEN_ACCESSOR in path.read_text(encoding="utf-8"):
            found.add(path.stem)
    return found


DISCOVERED = _token_bearing_modules()


# ---------------------------------------------------------------------------
# Write-path entry points, one per token-bearing platform
# ---------------------------------------------------------------------------


def _run_antigravity(config_dir: Path) -> Path:
    from installer.platforms.antigravity import AntigravityInstaller

    installer = AntigravityInstaller(
        spellbook_dir=REPO_ROOT, config_dir=config_dir, version="0.0.0"
    )
    installer._update_mcp_config()
    return installer.mcp_config_path


def _run_codex(config_dir: Path) -> Path:
    from installer.platforms.codex import _add_mcp_to_config_toml

    path = config_dir / "config.toml"
    _add_mcp_to_config_toml(path)
    return path


def _run_forgecode(config_dir: Path) -> Path:
    from installer.platforms.forgecode import _update_forgecode_mcp_config

    path = config_dir / ".mcp.json"
    _update_forgecode_mcp_config(path)
    return path


def _run_goose(config_dir: Path) -> Path:
    from installer.platforms.goose import _update_goose_mcp_config

    path = config_dir / "config.yaml"
    _update_goose_mcp_config(path)
    return path


def _run_opencode(config_dir: Path) -> Path:
    from installer.platforms.opencode import _update_opencode_config

    path = config_dir / "opencode.json"
    _update_opencode_config(path)
    return path


def _run_pi(config_dir: Path) -> Path:
    from installer.platforms.pi import _update_pi_mcp_config

    path = config_dir / "mcp.json"
    _update_pi_mcp_config(path)
    return path


WRITERS = {
    "antigravity": _run_antigravity,
    "codex": _run_codex,
    "forgecode": _run_forgecode,
    "goose": _run_goose,
    "opencode": _run_opencode,
    "pi": _run_pi,
}


# ---------------------------------------------------------------------------
# Discovery floor and coverage -- the silent-no-op guards
# ---------------------------------------------------------------------------


def test_discovery_finds_at_least_its_floor():
    """A scan that matched nothing would pass every assertion below."""
    assert len(DISCOVERED) >= MODULE_FLOOR, (
        f"Discovered {len(DISCOVERED)} token-bearing platform modules "
        f"({sorted(DISCOVERED)}), below the floor of {MODULE_FLOOR}. Either "
        f"{TOKEN_ACCESSOR!r} is no longer how platforms read the token, or "
        f"{PLATFORMS_DIR} moved. A scan that finds nothing reports a clean "
        f"pass over an unchecked tree."
    )


def test_every_token_bearing_module_has_a_write_path_under_test():
    """A new token-bearing platform fails here until its write path is covered."""
    uncovered = DISCOVERED - set(WRITERS)
    assert not uncovered, (
        f"Platform module(s) {sorted(uncovered)} read the bearer token but "
        f"have no entry in WRITERS, so nothing checks the mode of the config "
        f"file they write. Add an entry pointing at the module's write path."
    )


# ---------------------------------------------------------------------------
# The permission assertions
# ---------------------------------------------------------------------------


@pytest.mark.posix_only
@pytest.mark.parametrize("platform", sorted(WRITERS), ids=sorted(WRITERS))
def test_pre_existing_world_readable_config_is_tightened(platform, tmp_path):
    """An existing 0644 config must not survive the install at 0644.

    This is the case ``os.open``'s mode argument does not cover: the file
    already exists, so ``O_TRUNC`` reuses its inode and its mode.
    """
    config_dir = tmp_path / platform
    config_dir.mkdir()
    written = WRITERS[platform](config_dir)

    # Seed the *same* path the installer writes, at a broad mode, then re-run.
    written.write_text(written.read_text(encoding="utf-8"), encoding="utf-8")
    written.chmod(0o644)
    assert written.stat().st_mode & 0o777 == 0o644

    WRITERS[platform](config_dir)

    mode = written.stat().st_mode & 0o777
    assert mode == 0o600, (
        f"{platform}: {written} carries the bearer token but was left at "
        f"{oct(mode)}; any local account can read it."
    )


@pytest.mark.posix_only
@pytest.mark.parametrize("platform", sorted(WRITERS), ids=sorted(WRITERS))
def test_newly_created_config_is_private(platform, tmp_path):
    """A config file the installer creates must be owner-only from the start."""
    config_dir = tmp_path / platform
    config_dir.mkdir()

    written = WRITERS[platform](config_dir)

    assert written.exists(), f"{platform}: write path produced no file"
    mode = written.stat().st_mode & 0o777
    assert mode == 0o600, (
        f"{platform}: newly created {written} is {oct(mode)}, expected 0600."
    )
