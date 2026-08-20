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

import ast
import json
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

import pytest

from installer.platforms.antigravity import AntigravityInstaller
from installer.platforms.codex import (
    _add_mcp_to_config_toml,
    _remove_mcp_from_config_toml,
)
from installer.platforms.forgecode import _write_mcp_config_secure
from installer.platforms.goose import (
    _remove_goose_mcp_config,
    _update_goose_mcp_config,
)
from installer.platforms.opencode import (
    OpenCodeInstaller,
    _remove_opencode_instructions,
    _remove_opencode_mcp_config,
    _update_opencode_config,
    _update_opencode_instructions,
)
from installer.platforms.pi import _write_mcp_config

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


# ---------------------------------------------------------------------------
# Site-level coverage
#
# The module-level floor above asks each token-bearing MODULE for ONE covered
# write path. Several modules write the token from more than one place --
# opencode alone rewrites its config from four functions -- so a module-level
# floor leaves every write site but the covered one unguarded. Reverting any
# of those to a plain ``write_text`` would put the token back in a
# world-readable file that nothing in this suite ever stats.
#
# The population below is DERIVED from the source: every file-writing call
# site in every token-bearing module, found by walking the AST. A hand-listed
# set of sites would be the same defect one level up.
#
# Deriving the set from calls to ``write_token_bearing_file`` alone would
# blind the guard to exactly the regression it exists to catch: a site
# reverted to ``write_text`` would leave the derived set rather than fail it.
# So raw ``write_text`` and ``open(..., "w")`` calls are part of the
# population too, and a reverted site stays under test.
#
# That leaves the assertion, not the population, to separate a config that
# carries the token from one that does not. Each runner seeds a realistic
# pre-existing config containing SENTINEL in an Authorization header, and the
# assertion sweeps the whole tree afterwards: any file whose bytes contain
# SENTINEL must be 0600. Nothing is exempted by name. OpenCode's gate-plugin
# write is in the population like every other site and passes because the
# TypeScript file it copies does not contain the token -- not because an
# allowlist excuses it. An allowlist would be a place for a real leak to hide;
# a content test has no such place, and cannot grow one.
# ---------------------------------------------------------------------------

# A stand-in bearer token seeded into the configs the runners hand to the
# code under test. It is what the sweep looks for, so it must not appear in
# any file the installers write from their own sources.
SENTINEL = "sb-sentinel-2f7c1a9e4d0b"

INSTRUCTIONS_PATH = "/opt/spellbook/AGENTS.md"


class WriteSite(NamedTuple):
    module: str
    qualname: str
    lineno: int
    kind: str

    @property
    def key(self) -> str:
        """Identity used for coverage: the function the write lives in."""
        return f"{self.module}::{self.qualname}"

    @property
    def site_id(self) -> str:
        return f"{self.module}::{self.qualname}:L{self.lineno}"


def _write_kind(call: ast.Call):
    """Classify ``call`` as a file write, or return None."""
    func = call.func
    if isinstance(func, ast.Name) and func.id == "write_token_bearing_file":
        return "helper"
    if isinstance(func, ast.Attribute) and func.attr == "write_text":
        return "write_text"
    modes: list[str] = []
    if isinstance(func, ast.Name) and func.id == "open":
        modes = [a.value for a in call.args[1:] if isinstance(a, ast.Constant)]
    elif isinstance(func, ast.Attribute) and func.attr == "open":
        modes = [a.value for a in call.args[:1] if isinstance(a, ast.Constant)]
    modes += [
        kw.value.value
        for kw in call.keywords
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant)
    ]
    for mode in modes:
        if isinstance(mode, str) and ("w" in mode or "a" in mode or "+" in mode):
            return "open_w"
    return None


def _walk_module(node, module: str, chain: list, sites: list) -> None:
    """Collect write sites under ``node``, tracking the enclosing scope."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            _walk_module(child, module, chain + [child.name], sites)
            continue
        if isinstance(child, ast.Call):
            kind = _write_kind(child)
            if kind is not None:
                sites.append(WriteSite(module, "::".join(chain), child.lineno, kind))
        _walk_module(child, module, chain, sites)


def _write_sites() -> list[WriteSite]:
    """Every file-writing call site in every token-bearing platform module."""
    sites: list[WriteSite] = []
    for module in sorted(DISCOVERED):
        source = (PLATFORMS_DIR / f"{module}.py").read_text(encoding="utf-8")
        _walk_module(ast.parse(source), module, [], sites)
    return sorted(set(sites))


WRITE_SITES = _write_sites()

# Measured by walking the AST at the time of writing: 15 write sites across
# the 6 token-bearing modules (14 through the helper, 1 raw write of the
# OpenCode gate plugin). A floor, not an equality: a new write site raises the
# real number and is caught by the coverage test below, not by this one. A
# scan that matched nothing would otherwise report a clean pass.
SITE_FLOOR = 15

# Sites whose seeded config still carries SENTINEL after the site has written
# it, so the sweep has something to assert on. Every site but OpenCode's
# gate-plugin write, whose file legitimately never holds a token. Also a
# floor: it exists so a seeding change that quietly stopped putting SENTINEL
# on disk cannot turn the sweep into a pass over nothing.
SENTINEL_OBSERVED_FLOOR = 12


# ---------------------------------------------------------------------------
# One runner per write site. Each seeds a realistic pre-existing config that
# carries SENTINEL, then drives the code the site lives in.
# ---------------------------------------------------------------------------


def _seed(path: Path, text: str) -> None:
    """Write a pre-existing config, leaving an already-present mode intact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_json(path: Path, data: dict) -> None:
    _seed(path, json.dumps(data, indent=2) + "\n")


def _foreign_server() -> dict:
    """Another tool's MCP entry, carrying its own bearer token."""
    return {
        "url": "http://127.0.0.1:9/mcp",
        "headers": {"Authorization": f"Bearer {SENTINEL}"},
    }


def _antigravity_installer(config_dir: Path) -> AntigravityInstaller:
    return AntigravityInstaller(
        spellbook_dir=REPO_ROOT, config_dir=config_dir, version="0.0.0"
    )


def _site_antigravity_update(config_dir: Path) -> None:
    installer = _antigravity_installer(config_dir)
    _seed_json(installer.mcp_config_path, {"mcpServers": {"other": _foreign_server()}})
    installer._update_mcp_config()


def _site_antigravity_uninstall(config_dir: Path) -> None:
    installer = _antigravity_installer(config_dir)
    _seed_json(installer.mcp_config_path, {"mcpServers": {"other": _foreign_server()}})
    installer._update_mcp_config()
    installer.uninstall()


CODEX_FOREIGN = (
    "[mcp_servers.other]\n"
    'url = "http://127.0.0.1:9/mcp"\n'
    "\n"
    "[mcp_servers.other.headers]\n"
    f'Authorization = "Bearer {SENTINEL}"\n'
)


def _site_codex_add(config_dir: Path) -> None:
    """Drive all three writes in ``_add_mcp_to_config_toml``."""
    created = config_dir / "created.toml"
    _add_mcp_to_config_toml(created)  # no file yet -> create

    appended = config_dir / "config.toml"
    _seed(appended, CODEX_FOREIGN)
    _add_mcp_to_config_toml(appended)  # no marker -> append
    _add_mcp_to_config_toml(appended)  # marker present -> update in place


def _site_codex_remove(config_dir: Path) -> None:
    path = config_dir / "config.toml"
    _seed(path, CODEX_FOREIGN)
    _add_mcp_to_config_toml(path)
    _remove_mcp_from_config_toml(path)


def _site_forgecode_write(config_dir: Path) -> None:
    _write_mcp_config_secure(
        config_dir / ".mcp.json", {"mcpServers": {"other": _foreign_server()}}
    )


GOOSE_FOREIGN = (
    "GOOSE_PROVIDER: openai\n" f'upstream_header: "Authorization: Bearer {SENTINEL}"\n'
)


def _site_goose_update(config_dir: Path) -> None:
    path = config_dir / "config.yaml"
    _seed(path, GOOSE_FOREIGN)
    _update_goose_mcp_config(path)


def _site_goose_remove(config_dir: Path) -> None:
    path = config_dir / "config.yaml"
    _seed(path, GOOSE_FOREIGN)
    _update_goose_mcp_config(path)
    _remove_goose_mcp_config(path)


def _opencode_seed(config_dir: Path) -> Path:
    path = config_dir / "opencode.json"
    _seed_json(
        path,
        {
            "$schema": "https://opencode.ai/config.json",
            "mcp": {"other": _foreign_server()},
        },
    )
    return path


def _site_opencode_update_config(config_dir: Path) -> None:
    _update_opencode_config(_opencode_seed(config_dir))


def _site_opencode_update_instructions(config_dir: Path) -> None:
    _update_opencode_instructions(_opencode_seed(config_dir), INSTRUCTIONS_PATH)


def _site_opencode_remove_instructions(config_dir: Path) -> None:
    path = _opencode_seed(config_dir)
    _update_opencode_instructions(path, INSTRUCTIONS_PATH)
    _remove_opencode_instructions(path, INSTRUCTIONS_PATH)


def _site_opencode_remove_mcp(config_dir: Path) -> None:
    path = _opencode_seed(config_dir)
    _update_opencode_config(path)
    _remove_opencode_mcp_config(path)


def _site_opencode_install(config_dir: Path) -> None:
    OpenCodeInstaller(REPO_ROOT, config_dir, "0.0.0").install()


def _site_pi_write(config_dir: Path) -> None:
    _write_mcp_config(
        config_dir / "mcp.json", {"mcpServers": {"other": _foreign_server()}}
    )


SITE_RUNNERS: dict[str, Callable[[Path], None]] = {
    "antigravity::AntigravityInstaller::_update_mcp_config": _site_antigravity_update,
    "antigravity::AntigravityInstaller::uninstall": _site_antigravity_uninstall,
    "codex::_add_mcp_to_config_toml": _site_codex_add,
    "codex::_remove_mcp_from_config_toml": _site_codex_remove,
    "forgecode::_write_mcp_config_secure": _site_forgecode_write,
    "goose::_update_goose_mcp_config": _site_goose_update,
    "goose::_remove_goose_mcp_config": _site_goose_remove,
    "opencode::OpenCodeInstaller::install": _site_opencode_install,
    "opencode::_remove_opencode_instructions": _site_opencode_remove_instructions,
    "opencode::_remove_opencode_mcp_config": _site_opencode_remove_mcp,
    "opencode::_update_opencode_config": _site_opencode_update_config,
    "opencode::_update_opencode_instructions": _site_opencode_update_instructions,
    "pi::_write_mcp_config": _site_pi_write,
}


def _sentinel_bearing_files(root: Path) -> list[Path]:
    """Every file under ``root`` whose bytes contain the seeded token."""
    needle = SENTINEL.encode("utf-8")
    return sorted(
        p
        for p in root.rglob("*")
        if p.is_file() and not p.is_symlink() and needle in p.read_bytes()
    )


def _exercise(key: str, config_dir: Path) -> list[Path]:
    """Run a site twice, the second time over a world-readable config.

    The first run establishes the files; they are then broadened to 0644 and
    the site runs again. ``os.open``'s mode argument does not cover that case
    -- an existing inode keeps its mode through ``O_TRUNC`` -- so this is the
    run that can leave the token world-readable.
    """
    config_dir.mkdir(parents=True, exist_ok=True)
    SITE_RUNNERS[key](config_dir)
    for path in config_dir.rglob("*"):
        if path.is_file() and not path.is_symlink():
            path.chmod(0o644)
    SITE_RUNNERS[key](config_dir)
    return _sentinel_bearing_files(config_dir)


# ---------------------------------------------------------------------------
# Site-level floor and coverage
# ---------------------------------------------------------------------------


def test_write_site_discovery_finds_at_least_its_floor():
    """A scan that matched no write sites would pass every assertion below."""
    assert len(WRITE_SITES) >= SITE_FLOOR, (
        f"Discovered {len(WRITE_SITES)} write sites across {sorted(DISCOVERED)}, "
        f"below the floor of {SITE_FLOOR}. Either the write helpers were "
        f"renamed or the AST scan stopped matching. A scan that finds nothing "
        f"reports a clean pass over an unchecked tree."
    )


def test_every_write_site_is_exercised():
    """Every place a token-bearing module writes a file has a runner."""
    uncovered = {s.site_id for s in WRITE_SITES if s.key not in SITE_RUNNERS}
    assert not uncovered, (
        f"Write site(s) {sorted(uncovered)} live in a token-bearing platform "
        f"module but no SITE_RUNNERS entry drives them, so nothing checks the "
        f"mode of the file they write. A module-level floor does not cover "
        f"this: these modules write from more than one function."
    )


def test_no_runner_outlives_its_write_site():
    """A runner for a site that no longer exists is coverage that isn't there."""
    live = {s.key for s in WRITE_SITES}
    stale = set(SITE_RUNNERS) - live
    assert not stale, (
        f"SITE_RUNNERS entr(ies) {sorted(stale)} name functions that no longer "
        f"contain a file write. Either the write moved -- in which case its new "
        f"home needs a runner -- or the entry is dead weight that makes the "
        f"coverage count look larger than it is."
    )


# ---------------------------------------------------------------------------
# The site-level permission assertion
# ---------------------------------------------------------------------------


@pytest.mark.posix_only
@pytest.mark.parametrize("key", sorted(SITE_RUNNERS), ids=sorted(SITE_RUNNERS))
def test_no_file_carrying_the_token_is_world_readable(key, tmp_path):
    """After any token-bearing module writes, no file holding a token is loose.

    The sweep is over content, not over a list of paths: a file is checked
    because it contains the token, so a write site cannot escape by writing
    somewhere this test did not think to look, and a file that legitimately
    holds no token needs no exemption.
    """
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    bearing = _exercise(key, config_dir)

    loose = {
        str(p.relative_to(config_dir)): oct(p.stat().st_mode & 0o777)
        for p in bearing
        if p.stat().st_mode & 0o777 != 0o600
    }
    assert not loose, (
        f"{key}: {loose} contain the bearer token but are not 0600; any local "
        f"account can read them."
    )


@pytest.mark.posix_only
def test_the_sweep_actually_inspects_files_holding_a_token(tmp_path):
    """The permission sweep above passes trivially over a tree with no token.

    Its assertion is conditional on content, so seeding that quietly stopped
    putting a token on disk would turn every case green while checking
    nothing. This pins how many sites really do leave a token behind.
    """
    observed = sorted(
        key
        for key in SITE_RUNNERS
        if _exercise(key, (tmp_path / key.replace("::", "-")))
    )
    assert len(observed) >= SENTINEL_OBSERVED_FLOOR, (
        f"Only {len(observed)} of {len(SITE_RUNNERS)} sites left a file "
        f"containing the token ({observed}), below the floor of "
        f"{SENTINEL_OBSERVED_FLOOR}. The permission sweep is passing over "
        f"trees with nothing in them to check."
    )
