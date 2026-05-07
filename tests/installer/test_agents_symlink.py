"""Tests for the install_agents installer component.

The ``install_agents`` component populates ``$CLAUDE_CONFIG_DIR/agents/`` by
symlinking each ``.md`` file in ``$SPELLBOOK_DIR/agents/`` to a same-named
target file in the config dir. Agents are not auto-discovered from
``$SPELLBOOK_DIR``; Claude Code only discovers from
``$CLAUDE_CONFIG_DIR/agents/``, ``<cwd>/.claude/agents/``, or plugin sources.

The component diverges from ``create_skill_symlinks``/``create_command_symlinks``
in two ways:

1. **Skip+warn on user-authored target files** -- if the target is a regular
   file or a symlink to a non-spellbook path, do NOT clobber.
2. **Source narrowing on uninstall** -- only remove symlinks at the target dir
   whose ``resolve()`` points back into ``$SPELLBOOK_DIR/agents/``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from installer.components.agents import install_agents, uninstall_agents
from installer.components.symlinks import SymlinkResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def spellbook_dir(tmp_path):
    """Pre-create ``$SPELLBOOK_DIR/agents/`` directory."""
    sb = tmp_path / "spellbook"
    (sb / "agents").mkdir(parents=True)
    return sb


@pytest.fixture
def config_dir(tmp_path):
    """Pre-create ``$CLAUDE_CONFIG_DIR/agents/`` directory.

    The component assumes the caller has already created the target
    ``agents/`` subdir; this fixture makes that explicit.
    """
    cfg = tmp_path / "claude-config"
    (cfg / "agents").mkdir(parents=True)
    return cfg


def _write_agent(spellbook_dir: Path, name: str, body: str = "agent body") -> Path:
    """Create an agent .md file in ``$SPELLBOOK_DIR/agents/`` and return its path."""
    path = spellbook_dir / "agents" / name
    path.write_text(body, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Install tests
# ---------------------------------------------------------------------------


class TestInstallAgents:
    """Cover the 5-branch idempotence precedence and the empty/dry-run cases."""

    def test_empty_source_dir_returns_skipped_singleton(self, spellbook_dir, config_dir):
        # agents/ exists but is empty.
        results = install_agents(spellbook_dir=spellbook_dir, config_dir=config_dir)

        assert results == [
            SymlinkResult(
                source=spellbook_dir / "agents",
                target=config_dir / "agents",
                success=True,
                action="skipped",
                message="no source agents",
            )
        ]
        assert list((config_dir / "agents").iterdir()) == []

    def test_missing_source_dir_returns_skipped_singleton(self, tmp_path, config_dir):
        # SPELLBOOK_DIR with no agents/ subdir at all.
        sb = tmp_path / "no-agents-spellbook"
        sb.mkdir()

        results = install_agents(spellbook_dir=sb, config_dir=config_dir)

        assert results == [
            SymlinkResult(
                source=sb / "agents",
                target=config_dir / "agents",
                success=True,
                action="skipped",
                message="no source agents",
            )
        ]
        assert list((config_dir / "agents").iterdir()) == []

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink semantics")
    def test_single_source_target_missing_creates_symlink(
        self, spellbook_dir, config_dir
    ):
        source = _write_agent(spellbook_dir, "alpha.md", body="alpha content")
        target = config_dir / "agents" / "alpha.md"

        results = install_agents(spellbook_dir=spellbook_dir, config_dir=config_dir)

        assert results == [
            SymlinkResult(
                source=source,
                target=target,
                success=True,
                action="installed",
                message="installed symlink: alpha.md",
            )
        ]
        assert target.is_symlink()
        assert target.resolve() == source.resolve()
        assert target.read_text(encoding="utf-8") == "alpha content"

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink semantics")
    def test_multiple_sources_all_installed(self, spellbook_dir, config_dir):
        names = ["a.md", "b.md", "c.md"]
        sources = [_write_agent(spellbook_dir, n, body=f"body-{n}") for n in names]

        results = install_agents(spellbook_dir=spellbook_dir, config_dir=config_dir)

        results_sorted = sorted(results, key=lambda r: r.target.name)
        expected = sorted(
            [
                SymlinkResult(
                    source=src,
                    target=config_dir / "agents" / src.name,
                    success=True,
                    action="installed",
                    message=f"installed symlink: {src.name}",
                )
                for src in sources
            ],
            key=lambda r: r.target.name,
        )
        assert results_sorted == expected
        for src in sources:
            tgt = config_dir / "agents" / src.name
            assert tgt.is_symlink()
            assert tgt.resolve() == src.resolve()
            assert tgt.read_text(encoding="utf-8") == f"body-{src.name}"

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink semantics")
    def test_idempotent_re_run_reports_unchanged(self, spellbook_dir, config_dir):
        sources = [_write_agent(spellbook_dir, n) for n in ("a.md", "b.md")]
        # First install.
        install_agents(spellbook_dir=spellbook_dir, config_dir=config_dir)
        # Snapshot inode/mtime via lstat to verify second run does not touch them.
        targets = [config_dir / "agents" / s.name for s in sources]
        before = [t.lstat() for t in targets]

        results = install_agents(spellbook_dir=spellbook_dir, config_dir=config_dir)

        results_sorted = sorted(results, key=lambda r: r.target.name)
        expected = sorted(
            [
                SymlinkResult(
                    source=src,
                    target=config_dir / "agents" / src.name,
                    success=True,
                    action="unchanged",
                    message=f"already linked: {src.name}",
                )
                for src in sources
            ],
            key=lambda r: r.target.name,
        )
        assert results_sorted == expected
        after = [t.lstat() for t in targets]
        for b, a in zip(before, after):
            assert (b.st_ino, b.st_mtime_ns) == (a.st_ino, a.st_mtime_ns)

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink semantics")
    def test_stale_source_path_replaced(self, spellbook_dir, config_dir, tmp_path):
        # Simulate a worktree change: target points to an old source path that
        # no longer exists, but a same-basename source is now in spellbook_dir.
        old_source = tmp_path / "old-worktree" / "agents" / "alpha.md"
        old_source.parent.mkdir(parents=True)
        old_source.write_text("old", encoding="utf-8")
        target = config_dir / "agents" / "alpha.md"
        target.symlink_to(old_source)
        # Now remove the old source so the existing symlink is broken.
        old_source.unlink()
        new_source = _write_agent(spellbook_dir, "alpha.md", body="new content")

        results = install_agents(spellbook_dir=spellbook_dir, config_dir=config_dir)

        assert results == [
            SymlinkResult(
                source=new_source,
                target=target,
                success=True,
                action="upgraded",
                message="upgraded symlink: alpha.md",
            )
        ]
        assert target.is_symlink()
        assert target.resolve() == new_source.resolve()
        assert target.read_text(encoding="utf-8") == "new content"

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink semantics")
    def test_broken_symlink_replaced(self, spellbook_dir, config_dir, tmp_path):
        # Symlink at target points to a path that has never existed.
        target = config_dir / "agents" / "alpha.md"
        nonexistent = tmp_path / "never-existed" / "alpha.md"
        target.symlink_to(nonexistent)
        source = _write_agent(spellbook_dir, "alpha.md", body="fresh")

        results = install_agents(spellbook_dir=spellbook_dir, config_dir=config_dir)

        assert results == [
            SymlinkResult(
                source=source,
                target=target,
                success=True,
                action="upgraded",
                message="upgraded symlink: alpha.md",
            )
        ]
        assert target.is_symlink()
        assert target.resolve() == source.resolve()

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink semantics")
    def test_user_regular_file_at_target_skipped(self, spellbook_dir, config_dir):
        target = config_dir / "agents" / "alpha.md"
        target.write_text("user content", encoding="utf-8")
        source = _write_agent(spellbook_dir, "alpha.md", body="spellbook content")

        results = install_agents(spellbook_dir=spellbook_dir, config_dir=config_dir)

        assert results == [
            SymlinkResult(
                source=source,
                target=target,
                success=True,
                action="skipped",
                message="user file preserved: alpha.md",
            )
        ]
        # User content untouched.
        assert not target.is_symlink()
        assert target.read_text(encoding="utf-8") == "user content"

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink semantics")
    def test_user_symlink_to_non_spellbook_skipped(
        self, spellbook_dir, config_dir, tmp_path
    ):
        external = tmp_path / "external" / "alpha.md"
        external.parent.mkdir(parents=True)
        external.write_text("external content", encoding="utf-8")
        target = config_dir / "agents" / "alpha.md"
        target.symlink_to(external)
        source = _write_agent(spellbook_dir, "alpha.md", body="spellbook content")

        results = install_agents(spellbook_dir=spellbook_dir, config_dir=config_dir)

        assert results == [
            SymlinkResult(
                source=source,
                target=target,
                success=True,
                action="skipped",
                message=f"user symlink preserved: alpha.md -> {external.resolve()}",
            )
        ]
        assert target.is_symlink()
        assert target.resolve() == external.resolve()
        assert target.read_text(encoding="utf-8") == "external content"

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink semantics")
    def test_dry_run_reports_intent_without_side_effects(
        self, spellbook_dir, config_dir
    ):
        names = ["a.md", "b.md", "c.md"]
        sources = [_write_agent(spellbook_dir, n) for n in names]

        results = install_agents(
            spellbook_dir=spellbook_dir, config_dir=config_dir, dry_run=True
        )

        results_sorted = sorted(results, key=lambda r: r.target.name)
        # All entries are intended-installs; SymlinkResult delegates message
        # text to create_symlink under dry_run, so we verify shape, action,
        # and absence of side effects rather than the exact message string.
        assert [(r.source, r.target, r.success, r.action) for r in results_sorted] == [
            (
                src,
                config_dir / "agents" / src.name,
                True,
                "installed",
            )
            for src in sorted(sources, key=lambda p: p.name)
        ]
        # No targets created on disk.
        for src in sources:
            tgt = config_dir / "agents" / src.name
            assert not tgt.exists()
            assert not tgt.is_symlink()

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink semantics")
    def test_mixed_states_in_one_run(self, spellbook_dir, config_dir, tmp_path):
        # Sources: a.md, b.md, c.md.
        a = _write_agent(spellbook_dir, "a.md", body="A")
        b = _write_agent(spellbook_dir, "b.md", body="B")
        c = _write_agent(spellbook_dir, "c.md", body="C")
        # Target state:
        #   a.md missing -> "installed"
        #   b.md correct spellbook symlink -> "unchanged"
        #   c.md user-authored regular file -> "skipped"
        (config_dir / "agents" / "b.md").symlink_to(b)
        (config_dir / "agents" / "c.md").write_text("user-c", encoding="utf-8")

        results = install_agents(spellbook_dir=spellbook_dir, config_dir=config_dir)

        results_sorted = sorted(results, key=lambda r: r.target.name)
        assert results_sorted == [
            SymlinkResult(
                source=a,
                target=config_dir / "agents" / "a.md",
                success=True,
                action="installed",
                message="installed symlink: a.md",
            ),
            SymlinkResult(
                source=b,
                target=config_dir / "agents" / "b.md",
                success=True,
                action="unchanged",
                message="already linked: b.md",
            ),
            SymlinkResult(
                source=c,
                target=config_dir / "agents" / "c.md",
                success=True,
                action="skipped",
                message="user file preserved: c.md",
            ),
        ]
        # Filesystem state:
        assert (config_dir / "agents" / "a.md").is_symlink()
        assert (config_dir / "agents" / "a.md").resolve() == a.resolve()
        assert (config_dir / "agents" / "b.md").is_symlink()
        assert (config_dir / "agents" / "b.md").resolve() == b.resolve()
        assert not (config_dir / "agents" / "c.md").is_symlink()
        assert (config_dir / "agents" / "c.md").read_text(encoding="utf-8") == "user-c"

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink semantics")
    def test_top_level_md_files_only_installed(self, spellbook_dir, config_dir):
        """Only top-level ``.md`` files are installed as agents.

        Verifies three behaviors at once:
        (a) any top-level ``.md`` file is installed (including ``README.md``,
            which is intentionally treated as an agent — matches the
            ``create_skill_symlinks``/``create_command_symlinks`` glob);
        (b) non-``.md`` files (e.g. ``.txt``) at the top level are ignored;
        (c) ``.md`` files in subdirectories are ignored (no recursion).
        """
        # Top-level .md is symlinked.
        agent = _write_agent(spellbook_dir, "agent.md", body="A")
        # README.md is also top-level .md -> WILL be symlinked (matches
        # create_skill_symlinks/create_command_symlinks glob behavior; the
        # test name's "non_md" filter only excludes .txt and subdir files).
        readme = _write_agent(spellbook_dir, "README.md", body="R")
        # Non-.md file ignored.
        (spellbook_dir / "agents" / "notes.txt").write_text("notes", encoding="utf-8")
        # Subdirectory .md ignored (not top-level).
        sub = spellbook_dir / "agents" / "subdir"
        sub.mkdir()
        (sub / "x.md").write_text("X", encoding="utf-8")

        results = install_agents(spellbook_dir=spellbook_dir, config_dir=config_dir)

        results_sorted = sorted(results, key=lambda r: r.target.name)
        assert results_sorted == [
            SymlinkResult(
                source=readme,
                target=config_dir / "agents" / "README.md",
                success=True,
                action="installed",
                message="installed symlink: README.md",
            ),
            SymlinkResult(
                source=agent,
                target=config_dir / "agents" / "agent.md",
                success=True,
                action="installed",
                message="installed symlink: agent.md",
            ),
        ]
        # notes.txt and subdir/x.md NOT mirrored into target.
        assert not (config_dir / "agents" / "notes.txt").exists()
        assert not (config_dir / "agents" / "subdir").exists()
        assert not (config_dir / "agents" / "x.md").exists()

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink semantics")
    def test_source_path_resolution_matches_spellbook_agents(
        self, spellbook_dir, config_dir
    ):
        source = _write_agent(spellbook_dir, "alpha.md")

        install_agents(spellbook_dir=spellbook_dir, config_dir=config_dir)

        target = config_dir / "agents" / "alpha.md"
        assert target.resolve() == (spellbook_dir / "agents" / "alpha.md").resolve()
        assert target.resolve() == source.resolve()


# ---------------------------------------------------------------------------
# Uninstall tests
# ---------------------------------------------------------------------------


class TestUninstallAgents:
    """Cover the spellbook-only narrowing on uninstall."""

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink semantics")
    def test_removes_spellbook_symlinks(self, spellbook_dir, config_dir):
        sources = [_write_agent(spellbook_dir, n) for n in ("a.md", "b.md", "c.md")]
        install_agents(spellbook_dir=spellbook_dir, config_dir=config_dir)
        # Sanity: targets present.
        for src in sources:
            assert (config_dir / "agents" / src.name).is_symlink()

        results = uninstall_agents(config_dir=config_dir, spellbook_dir=spellbook_dir)

        results_sorted = sorted(results, key=lambda r: r.target.name)
        # The remove_symlink helper records the resolved source as
        # ``source``. After unlink the target is absent, but source is the
        # resolved spellbook path.
        expected = []
        for src in sorted(sources, key=lambda p: p.name):
            target = config_dir / "agents" / src.name
            expected.append(
                SymlinkResult(
                    source=src.resolve(),
                    target=target,
                    success=True,
                    action="removed",
                    message=f"Removed symlink: {src.name}",
                )
            )
        assert results_sorted == expected
        # Filesystem: all targets gone.
        for src in sources:
            target = config_dir / "agents" / src.name
            assert not target.exists()
            assert not target.is_symlink()
        # Source files untouched.
        for src in sources:
            assert src.exists()
            assert src.is_file()

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink semantics")
    def test_preserves_user_regular_files(self, spellbook_dir, config_dir):
        spellbook_sources = [_write_agent(spellbook_dir, n) for n in ("a.md", "b.md")]
        install_agents(spellbook_dir=spellbook_dir, config_dir=config_dir)
        # User adds their own agent (regular file).
        user_file = config_dir / "agents" / "my-custom.md"
        user_file.write_text("user agent", encoding="utf-8")

        results = uninstall_agents(config_dir=config_dir, spellbook_dir=spellbook_dir)

        # Spellbook symlinks removed; user file is NOT in results (we only
        # iterate the .md entries in the dir but the user file is neither
        # a symlink to spellbook nor needs to be touched -> implementation
        # may either skip-no-record or include action="skipped"). Verify
        # filesystem state authoritatively and assert the spellbook entries
        # are present in the result.
        removed_targets = sorted(
            r.target.name for r in results if r.action == "removed"
        )
        assert removed_targets == ["a.md", "b.md"]
        # User file preserved.
        assert user_file.exists()
        assert not user_file.is_symlink()
        assert user_file.read_text(encoding="utf-8") == "user agent"
        # Spellbook targets gone.
        for src in spellbook_sources:
            assert not (config_dir / "agents" / src.name).exists()

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink semantics")
    def test_preserves_user_non_spellbook_symlinks(
        self, spellbook_dir, config_dir, tmp_path
    ):
        spellbook_sources = [_write_agent(spellbook_dir, n) for n in ("a.md",)]
        install_agents(spellbook_dir=spellbook_dir, config_dir=config_dir)
        # User adds a symlink pointing outside spellbook.
        external = tmp_path / "external" / "user.md"
        external.parent.mkdir(parents=True)
        external.write_text("external user agent", encoding="utf-8")
        user_link = config_dir / "agents" / "user.md"
        user_link.symlink_to(external)

        results = uninstall_agents(config_dir=config_dir, spellbook_dir=spellbook_dir)

        removed_targets = sorted(
            r.target.name for r in results if r.action == "removed"
        )
        assert removed_targets == ["a.md"]
        # User symlink preserved.
        assert user_link.is_symlink()
        assert user_link.resolve() == external.resolve()
        # Spellbook symlink gone.
        for src in spellbook_sources:
            assert not (config_dir / "agents" / src.name).exists()

    def test_missing_target_dir_returns_unchanged(self, spellbook_dir, tmp_path):
        # config_dir without an agents/ subdir.
        cfg = tmp_path / "no-agents-config"
        cfg.mkdir()

        results = uninstall_agents(config_dir=cfg, spellbook_dir=spellbook_dir)

        assert results == [
            SymlinkResult(
                source=spellbook_dir / "agents",
                target=cfg / "agents",
                success=True,
                action="unchanged",
                message="no agents dir to clean",
            )
        ]

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink semantics")
    def test_idempotent_uninstall(self, spellbook_dir, config_dir):
        _write_agent(spellbook_dir, "a.md")
        install_agents(spellbook_dir=spellbook_dir, config_dir=config_dir)
        # First uninstall.
        first = uninstall_agents(config_dir=config_dir, spellbook_dir=spellbook_dir)
        assert [r.action for r in first] == ["removed"]

        # Second uninstall: nothing to remove.
        second = uninstall_agents(config_dir=config_dir, spellbook_dir=spellbook_dir)

        # No "removed" entries in the second pass; agents/ directory still
        # exists but is empty.
        assert [r for r in second if r.action == "removed"] == []
        assert (config_dir / "agents").exists()
        assert list((config_dir / "agents").iterdir()) == []


# ---------------------------------------------------------------------------
# ClaudeCodeInstaller wiring tests (Task A2 integration)
# ---------------------------------------------------------------------------


def _scaffold_spellbook(spellbook_root: Path) -> Path:
    """Create the minimum scaffolding ``ClaudeCodeInstaller.install()`` expects.

    The installer enumerates skills/, commands/, scripts/, patterns/, docs/,
    profiles/, and agents/ subdirs. We pre-create empty placeholders for
    every directory the installer touches so that the install path runs to
    completion. Callers populate ``agents/`` with the test's source files.
    """
    for sub in (
        "skills",
        "commands",
        "scripts",
        "patterns",
        "docs",
        "profiles",
        "agents",
    ):
        (spellbook_root / sub).mkdir(parents=True, exist_ok=True)
    return spellbook_root


class TestClaudeCodeInstallerWiring:
    """Verify install_agents/uninstall_agents are wired into ClaudeCodeInstaller.

    The unit tests above exercise the component in isolation. These tests
    verify it is invoked by the platform installer, that its results land in
    ``installer.results`` as a properly shaped ``InstallResult``, that the
    install-time symlink cleanup includes ``agents`` (so renamed/removed
    source files don't leave stale symlinks), and that the symmetric
    uninstall step preserves user-authored files.
    """

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink semantics")
    def test_install_creates_agent_symlinks_in_config_dir(self, tmp_path):
        from installer.platforms.claude_code import ClaudeCodeInstaller

        spellbook_dir = _scaffold_spellbook(tmp_path / "spellbook")
        config_dir = tmp_path / "claude-config"
        config_dir.mkdir()

        agent_names = ("alpha.md", "beta.md", "gamma.md")
        sources = {
            name: _write_agent(spellbook_dir, name, body=f"body-{name}")
            for name in agent_names
        }

        installer = ClaudeCodeInstaller(
            spellbook_dir=spellbook_dir,
            config_dir=config_dir,
            version="0.0.0-test",
            dry_run=False,
        )
        installer.install(skip_global_steps=True)

        for name, source in sources.items():
            target = config_dir / "agents" / name
            assert target.is_symlink()
            assert target.resolve() == source.resolve()
            assert target.read_text(encoding="utf-8") == f"body-{name}"

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink semantics")
    def test_install_returns_install_result_for_agents_step(self, tmp_path):
        from installer.core import InstallResult
        from installer.platforms.claude_code import ClaudeCodeInstaller

        spellbook_dir = _scaffold_spellbook(tmp_path / "spellbook")
        config_dir = tmp_path / "claude-config"
        config_dir.mkdir()
        for name in ("alpha.md", "beta.md", "gamma.md"):
            _write_agent(spellbook_dir, name)

        installer = ClaudeCodeInstaller(
            spellbook_dir=spellbook_dir,
            config_dir=config_dir,
            version="0.0.0-test",
            dry_run=False,
        )
        results = installer.install(skip_global_steps=True)

        agent_results = [r for r in results if r.component == "agents"]
        assert agent_results == [
            InstallResult(
                component="agents",
                platform="claude_code",
                success=True,
                action="installed",
                message="agents: 3 installed, 0 upgraded, 0 unchanged, 0 skipped",
            )
        ]

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink semantics")
    def test_install_dry_run_creates_no_files(self, tmp_path):
        from installer.core import InstallResult
        from installer.platforms.claude_code import ClaudeCodeInstaller

        spellbook_dir = _scaffold_spellbook(tmp_path / "spellbook")
        config_dir = tmp_path / "claude-config"
        config_dir.mkdir()
        for name in ("alpha.md", "beta.md"):
            _write_agent(spellbook_dir, name)

        installer = ClaudeCodeInstaller(
            spellbook_dir=spellbook_dir,
            config_dir=config_dir,
            version="0.0.0-test",
            dry_run=True,
        )
        results = installer.install(skip_global_steps=True)

        # No filesystem writes under config_dir/agents.
        agents_target = config_dir / "agents"
        if agents_target.exists():
            assert list(agents_target.iterdir()) == []

        # Agents step still reports its intended action.
        agent_results = [r for r in results if r.component == "agents"]
        assert agent_results == [
            InstallResult(
                component="agents",
                platform="claude_code",
                success=True,
                action="installed",
                message="agents: 2 installed, 0 upgraded, 0 unchanged, 0 skipped",
            )
        ]

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink semantics")
    def test_uninstall_removes_agent_symlinks_only_spellbook_pointing(
        self, tmp_path
    ):
        from installer.platforms.claude_code import ClaudeCodeInstaller

        spellbook_dir = _scaffold_spellbook(tmp_path / "spellbook")
        config_dir = tmp_path / "claude-config"
        config_dir.mkdir()
        spellbook_names = ("alpha.md", "beta.md")
        sources = [_write_agent(spellbook_dir, n) for n in spellbook_names]

        installer = ClaudeCodeInstaller(
            spellbook_dir=spellbook_dir,
            config_dir=config_dir,
            version="0.0.0-test",
            dry_run=False,
        )
        installer.install(skip_global_steps=True)

        # Pre-create a user-authored regular file alongside spellbook symlinks.
        user_file = config_dir / "agents" / "my-user-agent.md"
        user_file.write_text("user content", encoding="utf-8")

        installer.uninstall(skip_global_steps=True)

        # All spellbook-pointing symlinks gone.
        for src in sources:
            assert not (config_dir / "agents" / src.name).exists()
        # User file preserved verbatim.
        assert user_file.exists()
        assert not user_file.is_symlink()
        assert user_file.read_text(encoding="utf-8") == "user content"

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink semantics")
    def test_install_idempotent_re_run_no_duplicates(self, tmp_path):
        from installer.core import InstallResult
        from installer.platforms.claude_code import ClaudeCodeInstaller

        spellbook_dir = _scaffold_spellbook(tmp_path / "spellbook")
        config_dir = tmp_path / "claude-config"
        config_dir.mkdir()
        names = ("alpha.md", "beta.md")
        for n in names:
            _write_agent(spellbook_dir, n)

        installer = ClaudeCodeInstaller(
            spellbook_dir=spellbook_dir,
            config_dir=config_dir,
            version="0.0.0-test",
            dry_run=False,
        )
        installer.install(skip_global_steps=True)

        targets = [config_dir / "agents" / n for n in names]
        before = [(t.resolve(), t.lstat().st_ino) for t in targets]

        # Second install on a fresh installer instance to simulate re-running.
        installer2 = ClaudeCodeInstaller(
            spellbook_dir=spellbook_dir,
            config_dir=config_dir,
            version="0.0.0-test",
            dry_run=False,
        )
        results = installer2.install(skip_global_steps=True)

        agent_results = [r for r in results if r.component == "agents"]
        assert agent_results == [
            InstallResult(
                component="agents",
                platform="claude_code",
                success=True,
                action="unchanged",
                message="agents: 0 installed, 0 upgraded, 2 unchanged, 0 skipped",
            )
        ]
        after = [(t.resolve(), t.lstat().st_ino) for t in targets]
        assert before == after

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink semantics")
    def test_install_cleanup_purges_stale_agent_symlink(self, tmp_path):
        """Install-time cleanup purges stale symlinks into THIS spellbook.

        When a source agent is renamed/removed, the prior symlink at
        ``$CLAUDE_CONFIG_DIR/agents/<old>.md`` points into this install's
        ``agents/`` dir but its target is gone. The narrowed inline
        pre-pass must purge it (parent-dir equality with this install's
        ``agents/`` source) before install_agents runs. (Foreign-spellbook
        broken links are NOT in scope for this cleanup -- see
        ``test_install_cleanup_preserves_other_spellbook_broken_symlinks``.)
        """
        from installer.platforms.claude_code import ClaudeCodeInstaller

        spellbook_dir = _scaffold_spellbook(tmp_path / "spellbook")
        config_dir = tmp_path / "claude-config"
        config_dir.mkdir()
        # Pre-create a stale symlink pointing into THIS spellbook's agents
        # dir, whose source file once existed but has since been removed
        # (the rename/removal scenario the cleanup is meant to cover).
        stale_source = spellbook_dir / "agents" / "obsolete.md"
        stale_source.write_text("obsolete", encoding="utf-8")
        (config_dir / "agents").mkdir(parents=True, exist_ok=True)
        stale_target = config_dir / "agents" / "obsolete.md"
        stale_target.symlink_to(stale_source)
        stale_source.unlink()  # break the link
        # Add a fresh source agent.
        fresh_source = _write_agent(spellbook_dir, "fresh.md", body="fresh body")

        installer = ClaudeCodeInstaller(
            spellbook_dir=spellbook_dir,
            config_dir=config_dir,
            version="0.0.0-test",
            dry_run=False,
        )
        installer.install(skip_global_steps=True)

        # Stale symlink purged.
        assert not stale_target.exists()
        assert not stale_target.is_symlink()
        # Fresh symlink present.
        fresh_target = config_dir / "agents" / "fresh.md"
        assert fresh_target.is_symlink()
        assert fresh_target.resolve() == fresh_source.resolve()

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink semantics")
    def test_install_cleanup_preserves_other_spellbook_broken_symlinks(
        self, tmp_path
    ):
        """Broken-symlink heuristic must not remove links into a *different*
        spellbook installation.

        The pre-pass that removes stale agent symlinks falls back to a
        path-based heuristic when a symlink target is broken. Earlier the
        heuristic relied on a ``"spellbook"`` substring match, which would
        false-positive remove broken symlinks pointing at any installation
        whose path happened to contain "spellbook" -- not just OUR install.
        The tightened heuristic compares the broken symlink's parent dir
        against THIS install's ``agents/`` dir via exact resolved-path
        equality. A broken symlink whose path contains "spellbook" but
        points into a different installation must be preserved.
        """
        from installer.platforms.claude_code import ClaudeCodeInstaller

        spellbook_dir = _scaffold_spellbook(tmp_path / "spellbook")
        config_dir = tmp_path / "claude-config"
        config_dir.mkdir()

        # Pre-create a broken symlink that points at a *different* spellbook
        # checkout's agents/ dir. The directory is created (so the parent
        # resolves) but the leaf file is missing, making the symlink broken.
        foreign_root = tmp_path / "other-spellbook"
        foreign_agents = foreign_root / "agents"
        foreign_agents.mkdir(parents=True)
        foreign_target_path = foreign_agents / "foreign.md"
        # Do NOT create foreign_target_path -- we want a broken symlink.
        (config_dir / "agents").mkdir(parents=True, exist_ok=True)
        foreign_link = config_dir / "agents" / "foreign.md"
        foreign_link.symlink_to(foreign_target_path)
        # Sanity: link is broken, points at a path containing "spellbook".
        assert foreign_link.is_symlink()
        assert not foreign_link.exists()
        assert "spellbook" in str(foreign_link.readlink()).lower()

        # Add a fresh source agent so install proceeds normally.
        _write_agent(spellbook_dir, "fresh.md", body="fresh body")

        installer = ClaudeCodeInstaller(
            spellbook_dir=spellbook_dir,
            config_dir=config_dir,
            version="0.0.0-test",
            dry_run=False,
        )
        installer.install(skip_global_steps=True)

        # The foreign broken symlink must be preserved -- it points at a
        # different spellbook installation, not ours.
        assert foreign_link.is_symlink()
        assert foreign_link.readlink() == foreign_target_path
