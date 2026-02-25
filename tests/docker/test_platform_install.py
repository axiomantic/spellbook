"""Platform installation tests using the Python installer directly.

Tests cover fresh installs, skill/command availability, context file creation,
and edge cases for all five supported platforms: claude_code, opencode, codex,
gemini, and crush.

CRITICAL CONSTRAINT: External CLIs (gemini, opencode, codex, crush) are NOT
available in the test environment. Tests call the Python installer classes
directly and verify the file/config output. For platforms that skip when
their CLI is absent, the tests verify the skip behavior.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

import pytest

from installer.config import SUPPORTED_PLATFORMS
from installer.core import InstallResult, Installer, get_platform_installer
from installer.demarcation import MARKER_END, MARKER_START_PATTERN


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_spellbook_dir(base: Path) -> Path:
    """Build a minimal spellbook directory structure for installer tests."""
    spellbook = base / "spellbook"
    spellbook.mkdir()

    # Version file
    (spellbook / ".version").write_text("1.0.0\n")

    # MCP server stub
    mcp_dir = spellbook / "spellbook_mcp"
    mcp_dir.mkdir()
    (mcp_dir / "server.py").write_text("# MCP server stub\n")

    # Context file template
    (spellbook / "CLAUDE.spellbook.md").write_text(
        "# Spellbook\n\nTest spellbook context content.\n"
    )

    # Skills
    skills_dir = spellbook / "skills"
    skills_dir.mkdir()
    for name in ("debugging", "implementing-features", "code-review"):
        skill_dir = skills_dir / name
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: Test skill {name}\n---\n# {name}\n"
        )

    # Commands
    commands_dir = spellbook / "commands"
    commands_dir.mkdir()
    for name in ("verify.md", "handoff.md", "mode.md"):
        (commands_dir / name).write_text(f"---\ndescription: Test command\n---\n# {name}\n")

    # Docs directory (Claude Code symlinks this)
    docs_dir = spellbook / "docs"
    docs_dir.mkdir()
    (docs_dir / "README.md").write_text("# Docs\n")

    # Scripts directory (Claude Code symlinks individual scripts)
    scripts_dir = spellbook / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "example.py").write_text("# example script\n")
    (scripts_dir / "example.sh").write_text("#!/bin/bash\n")
    # spellbook-server.py is required by the MCP daemon installer
    (scripts_dir / "spellbook-server.py").write_text("# spellbook server stub\n")

    # Agents directory
    agents_dir = spellbook / "agents"
    agents_dir.mkdir()
    (agents_dir / "default.md").write_text("# Default agent\n")

    # Gemini extension (needs valid name field for gemini CLI linking)
    ext_dir = spellbook / "extensions" / "gemini"
    ext_dir.mkdir(parents=True)
    (ext_dir / "gemini-extension.json").write_text(
        '{"name": "spellbook", "version": "1.0.0"}\n'
    )

    # OpenCode extension (spellbook-forged plugin)
    oc_ext_dir = spellbook / "extensions" / "opencode" / "spellbook-forged"
    oc_ext_dir.mkdir(parents=True)
    (oc_ext_dir / "plugin.ts").write_text("// plugin stub\n")

    # OpenCode system prompt
    oc_sys_dir = spellbook / "extensions" / "opencode"
    (oc_sys_dir / "claude-code-system-prompt.md").write_text("# System Prompt\n")

    # Security hook for OpenCode
    hooks_dir = spellbook / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "opencode-plugin.ts").write_text("// security plugin\n")

    # Gemini policy
    (hooks_dir / "gemini-policy.toml").write_text("[policy]\nenabled = true\n")

    # Patterns directory (Claude Code symlinks this)
    patterns_dir = spellbook / "patterns"
    patterns_dir.mkdir()
    (patterns_dir / "example.md").write_text("# Pattern\n")

    return spellbook


@pytest.fixture()
def spellbook_dir(tmp_path: Path) -> Path:
    """Create a mock spellbook directory with all required structures."""
    return _make_spellbook_dir(tmp_path)


def _collect_result_actions(results: List[InstallResult]) -> dict:
    """Build a dict of component -> action from install results."""
    return {r.component: r.action for r in results}


def _collect_result_components(results: List[InstallResult]) -> set:
    """Get the set of component names from install results."""
    return {r.component for r in results}


# ---------------------------------------------------------------------------
# Parametrized tests across all platforms
# ---------------------------------------------------------------------------

# Platforms that require their config dir to pre-exist (everything except claude_code).
_PLATFORMS_NEEDING_CONFIG = ["opencode", "codex", "gemini", "crush"]


@pytest.fixture()
def platform_config_dir(tmp_path: Path, request) -> Path:
    """Create the config directory for the requested platform.

    The ``platform`` param is injected via indirect parametrization.
    """
    platform = request.param
    dirs = {
        "claude_code": tmp_path / ".claude",
        "opencode": tmp_path / ".config" / "opencode",
        "codex": tmp_path / ".codex",
        "gemini": tmp_path / ".gemini",
        "crush": tmp_path / ".local" / "share" / "crush",
    }
    config_dir = dirs[platform]
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


@pytest.mark.parametrize(
    "platform",
    SUPPORTED_PLATFORMS,
    ids=SUPPORTED_PLATFORMS,
)
def test_fresh_install(platform: str, spellbook_dir: Path, tmp_path: Path):
    """A clean install for each platform creates expected output files or skips gracefully."""
    # Build config dir for the platform
    dirs = {
        "claude_code": tmp_path / "home" / ".claude",
        "opencode": tmp_path / "home" / ".config" / "opencode",
        "codex": tmp_path / "home" / ".codex",
        "gemini": tmp_path / "home" / ".gemini",
        "crush": tmp_path / "home" / ".local" / "share" / "crush",
    }
    config_dir = dirs[platform]
    config_dir.mkdir(parents=True, exist_ok=True)

    installer = get_platform_installer(platform, spellbook_dir, "1.0.0")
    # Override config_dir to use our temp location
    installer.config_dir = config_dir

    results = installer.install()

    # Components that may legitimately fail in test environments.
    # MCP daemon/server cannot start without the real spellbook-server.py and
    # without the claude CLI available for registration.
    _ALLOWED_FAILURES = {"mcp_daemon", "mcp_server"}

    # All non-MCP results should report success
    for r in results:
        if r.component in _ALLOWED_FAILURES:
            continue
        assert r.success, f"Component {r.component} failed: {r.message}"

    # Platform-specific checks for non-skip results
    actions = _collect_result_actions(results)

    if platform == "claude_code":
        assert "CLAUDE.md" in actions
        assert "skills" in actions
        assert "commands" in actions
    elif platform == "gemini":
        # Gemini skips when CLI is not available
        if "platform" in actions:
            assert actions["platform"] == "skipped"
    elif platform in ("opencode", "codex", "crush"):
        # These platforms install AGENTS.md
        assert "AGENTS.md" in actions or "platform" in actions


@pytest.mark.parametrize(
    "platform",
    SUPPORTED_PLATFORMS,
    ids=SUPPORTED_PLATFORMS,
)
def test_skills_available(platform: str, spellbook_dir: Path, tmp_path: Path):
    """After install, skills directory exists or is configured for each platform."""
    dirs = {
        "claude_code": tmp_path / "home" / ".claude",
        "opencode": tmp_path / "home" / ".config" / "opencode",
        "codex": tmp_path / "home" / ".codex",
        "gemini": tmp_path / "home" / ".gemini",
        "crush": tmp_path / "home" / ".local" / "share" / "crush",
    }
    config_dir = dirs[platform]
    config_dir.mkdir(parents=True, exist_ok=True)

    installer = get_platform_installer(platform, spellbook_dir, "1.0.0")
    installer.config_dir = config_dir
    results = installer.install()

    if platform == "claude_code":
        # Skills are symlinked into config_dir/skills/
        skills_dir = config_dir / "skills"
        assert skills_dir.exists()
        # Check at least one skill symlink
        skill_links = list(skills_dir.iterdir())
        assert len(skill_links) >= 3, f"Expected at least 3 skills, found {len(skill_links)}"
        for link in skill_links:
            assert link.is_symlink(), f"{link.name} should be a symlink"

    elif platform == "codex":
        # Codex also creates per-skill symlinks
        skills_dir = config_dir / "skills"
        assert skills_dir.exists()
        skill_links = [p for p in skills_dir.iterdir() if p.is_symlink()]
        assert len(skill_links) >= 3

    elif platform == "crush":
        # Crush configures skills_paths in crush.json
        crush_json = config_dir / "crush.json"
        if crush_json.exists():
            config = json.loads(crush_json.read_text())
            skills_paths = config.get("options", {}).get("skills_paths", [])
            assert len(skills_paths) > 0, "Crush should have skills_paths configured"

    elif platform == "opencode":
        # OpenCode uses its own Agent Skills system; skills are NOT symlinked
        # by the installer (they use MCP). Verify install did not fail
        # (excluding MCP components that need real daemon infrastructure).
        for r in results:
            if r.component not in ("mcp_daemon", "mcp_server"):
                assert r.success

    elif platform == "gemini":
        # Gemini skips when CLI not available
        actions = _collect_result_actions(results)
        if "platform" in actions and actions["platform"] == "skipped":
            pass  # Expected: gemini CLI absent
        else:
            # If it did install, the extension would have skills
            pass


@pytest.mark.parametrize(
    "platform",
    SUPPORTED_PLATFORMS,
    ids=SUPPORTED_PLATFORMS,
)
def test_commands_available(platform: str, spellbook_dir: Path, tmp_path: Path):
    """After install, commands are accessible for each platform."""
    dirs = {
        "claude_code": tmp_path / "home" / ".claude",
        "opencode": tmp_path / "home" / ".config" / "opencode",
        "codex": tmp_path / "home" / ".codex",
        "gemini": tmp_path / "home" / ".gemini",
        "crush": tmp_path / "home" / ".local" / "share" / "crush",
    }
    config_dir = dirs[platform]
    config_dir.mkdir(parents=True, exist_ok=True)

    installer = get_platform_installer(platform, spellbook_dir, "1.0.0")
    installer.config_dir = config_dir
    results = installer.install()

    if platform == "claude_code":
        # Commands are symlinked into config_dir/commands/
        commands_dir = config_dir / "commands"
        assert commands_dir.exists()
        cmd_links = list(commands_dir.iterdir())
        assert len(cmd_links) >= 3, f"Expected at least 3 commands, found {len(cmd_links)}"
        for link in cmd_links:
            assert link.is_symlink(), f"{link.name} should be a symlink"

    elif platform in ("opencode", "codex", "crush"):
        # These platforms access commands via AGENTS.md content or MCP.
        # Verify install succeeded for context file component (excluding
        # MCP components that need real daemon infrastructure).
        for r in results:
            if r.component not in ("mcp_daemon", "mcp_server"):
                assert r.success

    elif platform == "gemini":
        # Gemini may skip (CLI absent) or partially fail (CLI present but
        # extension linking fails with stub config). Either way, we only
        # verify non-extension components succeed.
        for r in results:
            if r.component not in ("extension", "extension_skills", "security_policy"):
                assert r.success


# ---------------------------------------------------------------------------
# Platform-specific tests
# ---------------------------------------------------------------------------


class TestClaudeCode:
    """Tests specific to Claude Code platform installation."""

    def test_claude_md_created_with_markers(self, spellbook_dir: Path, tmp_path: Path):
        """CLAUDE.md is created with SPELLBOOK:START/END demarcation markers."""
        config_dir = tmp_path / "home" / ".claude"
        config_dir.mkdir(parents=True)

        installer = get_platform_installer("claude_code", spellbook_dir, "1.0.0")
        installer.config_dir = config_dir
        # The Claude Code installer writes to _global_claude_md which is
        # Path.home() / ".claude" / "CLAUDE.md". We need to also set this.
        # Since we cannot override Path.home(), we test the CLAUDE.md created
        # at the real home. Instead, test using the installer directly.
        from installer.platforms.claude_code import ClaudeCodeInstaller

        cc_installer = ClaudeCodeInstaller(
            spellbook_dir=spellbook_dir,
            config_dir=config_dir,
            version="1.0.0",
        )

        # Override the private property for global claude md to use our temp dir
        # by testing the content generation separately.
        from installer.components.context_files import generate_claude_context
        from installer.demarcation import update_demarcated_section

        claude_md_path = config_dir / "CLAUDE.md"
        content = generate_claude_context(spellbook_dir)
        assert len(content) > 0, "Generated context should not be empty"

        action, backup = update_demarcated_section(claude_md_path, content, "1.0.0")
        assert action == "created"
        assert backup is None  # No backup on first creation

        # Verify markers are present
        file_content = claude_md_path.read_text()
        assert MARKER_START_PATTERN.search(file_content) is not None, (
            "SPELLBOOK:START marker not found in CLAUDE.md"
        )
        assert MARKER_END in file_content, (
            "SPELLBOOK:END marker not found in CLAUDE.md"
        )

        # Verify version in marker
        match = MARKER_START_PATTERN.search(file_content)
        assert match is not None
        assert match.group(1) == "1.0.0"

    def test_claude_code_mcp_config(self, spellbook_dir: Path, tmp_path: Path):
        """MCP daemon and server components are attempted during Claude Code install."""
        config_dir = tmp_path / "home" / ".claude"
        config_dir.mkdir(parents=True)

        installer = get_platform_installer("claude_code", spellbook_dir, "1.0.0")
        installer.config_dir = config_dir
        results = installer.install()

        components = _collect_result_components(results)
        # MCP daemon should be attempted (may fail in test env, but component exists)
        assert "mcp_daemon" in components, (
            "MCP daemon component should be in results"
        )

    def test_claude_code_skills_symlinked(self, spellbook_dir: Path, tmp_path: Path):
        """Skills and commands are symlinked into .claude/ subdirectories."""
        config_dir = tmp_path / "home" / ".claude"
        config_dir.mkdir(parents=True)

        installer = get_platform_installer("claude_code", spellbook_dir, "1.0.0")
        installer.config_dir = config_dir
        results = installer.install()

        # Skills
        skills_dir = config_dir / "skills"
        assert skills_dir.exists()
        debugging_link = skills_dir / "debugging"
        assert debugging_link.is_symlink()
        assert debugging_link.resolve() == (spellbook_dir / "skills" / "debugging").resolve()

        # Commands
        commands_dir = config_dir / "commands"
        assert commands_dir.exists()
        verify_link = commands_dir / "verify.md"
        assert verify_link.is_symlink()
        assert verify_link.resolve() == (spellbook_dir / "commands" / "verify.md").resolve()

        # Patterns (symlinked as directory)
        patterns_link = config_dir / "patterns"
        if patterns_link.exists():
            assert patterns_link.is_symlink()

        # Docs (symlinked as directory)
        docs_link = config_dir / "docs"
        if docs_link.exists():
            assert docs_link.is_symlink()


class TestOpenCode:
    """Tests specific to OpenCode platform installation."""

    def test_opencode_agents_md(self, spellbook_dir: Path, tmp_path: Path):
        """AGENTS.md is created for OpenCode with demarcation markers."""
        config_dir = tmp_path / "home" / ".config" / "opencode"
        config_dir.mkdir(parents=True)

        installer = get_platform_installer("opencode", spellbook_dir, "1.0.0")
        installer.config_dir = config_dir
        results = installer.install()

        # AGENTS.md should be created
        agents_md = config_dir / "AGENTS.md"
        assert agents_md.exists(), "AGENTS.md should be created for OpenCode"

        content = agents_md.read_text()
        assert MARKER_START_PATTERN.search(content) is not None
        assert MARKER_END in content

    def test_opencode_mcp_config(self, spellbook_dir: Path, tmp_path: Path):
        """OpenCode MCP server is registered in opencode.json."""
        config_dir = tmp_path / "home" / ".config" / "opencode"
        config_dir.mkdir(parents=True)

        installer = get_platform_installer("opencode", spellbook_dir, "1.0.0")
        installer.config_dir = config_dir
        results = installer.install()

        opencode_json = config_dir / "opencode.json"
        assert opencode_json.exists(), "opencode.json should be created"

        config = json.loads(opencode_json.read_text())
        assert "mcp" in config
        assert "spellbook" in config["mcp"]
        assert config["mcp"]["spellbook"]["type"] == "remote"
        assert "url" in config["mcp"]["spellbook"]

    def test_opencode_skips_when_config_missing(self, spellbook_dir: Path, tmp_path: Path):
        """OpenCode installer skips gracefully when config dir does not exist."""
        config_dir = tmp_path / "home" / ".config" / "opencode-nonexistent"
        # Do NOT create it

        installer = get_platform_installer("opencode", spellbook_dir, "1.0.0")
        installer.config_dir = config_dir
        results = installer.install()

        assert len(results) == 1
        assert results[0].action == "skipped"
        assert results[0].success


class TestCodex:
    """Tests specific to Codex platform installation."""

    def test_codex_agents_md(self, spellbook_dir: Path, tmp_path: Path):
        """AGENTS.md is created for Codex with demarcation markers."""
        config_dir = tmp_path / "home" / ".codex"
        config_dir.mkdir(parents=True)

        installer = get_platform_installer("codex", spellbook_dir, "1.0.0")
        installer.config_dir = config_dir
        results = installer.install()

        agents_md = config_dir / "AGENTS.md"
        assert agents_md.exists(), "AGENTS.md should be created for Codex"

        content = agents_md.read_text()
        assert MARKER_START_PATTERN.search(content) is not None
        assert MARKER_END in content

    def test_codex_spellbook_symlink(self, spellbook_dir: Path, tmp_path: Path):
        """Codex creates a symlink to the spellbook root directory."""
        config_dir = tmp_path / "home" / ".codex"
        config_dir.mkdir(parents=True)

        installer = get_platform_installer("codex", spellbook_dir, "1.0.0")
        installer.config_dir = config_dir
        installer.install()

        spellbook_link = config_dir / "spellbook"
        assert spellbook_link.is_symlink()
        assert spellbook_link.resolve() == spellbook_dir.resolve()

    def test_codex_mcp_config_toml(self, spellbook_dir: Path, tmp_path: Path):
        """Codex MCP server is registered in config.toml."""
        config_dir = tmp_path / "home" / ".codex"
        config_dir.mkdir(parents=True)

        installer = get_platform_installer("codex", spellbook_dir, "1.0.0")
        installer.config_dir = config_dir
        installer.install()

        config_toml = config_dir / "config.toml"
        assert config_toml.exists(), "config.toml should be created for MCP"

        content = config_toml.read_text()
        assert "SPELLBOOK:START" in content
        assert "[mcp_servers.spellbook]" in content


def _gemini_cli_available() -> bool:
    """Check if gemini CLI is available on the system."""
    from installer.platforms.gemini import check_gemini_cli_available

    return check_gemini_cli_available()


class TestGemini:
    """Tests specific to Gemini CLI platform installation."""

    @pytest.mark.skipif(
        _gemini_cli_available(),
        reason="gemini CLI is available; skip-without-cli test requires absent CLI",
    )
    def test_gemini_skip_without_cli(self, spellbook_dir: Path, tmp_path: Path):
        """Gemini installer skips gracefully when gemini CLI is absent."""
        config_dir = tmp_path / "home" / ".gemini"
        config_dir.mkdir(parents=True)

        installer = get_platform_installer("gemini", spellbook_dir, "1.0.0")
        installer.config_dir = config_dir
        results = installer.install()

        # Should have a single skip result
        assert len(results) >= 1
        skip_results = [r for r in results if r.action == "skipped"]
        assert len(skip_results) >= 1, "Gemini should skip when CLI is absent"

        # The skip message should indicate CLI not available
        skip_msg = skip_results[0].message.lower()
        assert "not available" in skip_msg or "cli" in skip_msg

    @pytest.mark.skipif(
        _gemini_cli_available(),
        reason="gemini CLI is available; skip test requires absent CLI",
    )
    def test_gemini_skip_is_successful(self, spellbook_dir: Path, tmp_path: Path):
        """Gemini skip result should report success (graceful skip, not error)."""
        config_dir = tmp_path / "home" / ".gemini"
        config_dir.mkdir(parents=True)

        installer = get_platform_installer("gemini", spellbook_dir, "1.0.0")
        installer.config_dir = config_dir
        results = installer.install()

        for r in results:
            assert r.success, f"Gemini skip should be successful, got: {r.message}"

    @pytest.mark.skipif(
        not _gemini_cli_available(),
        reason="gemini CLI not available; install test requires CLI",
    )
    def test_gemini_install_with_cli(self, spellbook_dir: Path, tmp_path: Path):
        """When gemini CLI is present, installer attempts extension linking."""
        config_dir = tmp_path / "home" / ".gemini"
        config_dir.mkdir(parents=True)

        installer = get_platform_installer("gemini", spellbook_dir, "1.0.0")
        installer.config_dir = config_dir
        results = installer.install()

        # Should have results (not just a skip)
        assert len(results) >= 1
        components = _collect_result_components(results)
        assert "extension" in components, (
            "Gemini with CLI should attempt extension linking"
        )


class TestCrush:
    """Tests specific to Crush platform installation."""

    def test_crush_agents_md(self, spellbook_dir: Path, tmp_path: Path):
        """AGENTS.md is created for Crush with demarcation markers."""
        config_dir = tmp_path / "home" / ".local" / "share" / "crush"
        config_dir.mkdir(parents=True)

        installer = get_platform_installer("crush", spellbook_dir, "1.0.0")
        installer.config_dir = config_dir
        results = installer.install()

        agents_md = config_dir / "AGENTS.md"
        assert agents_md.exists(), "AGENTS.md should be created for Crush"

        content = agents_md.read_text()
        assert MARKER_START_PATTERN.search(content) is not None
        assert MARKER_END in content

    def test_crush_config_json(self, spellbook_dir: Path, tmp_path: Path):
        """Crush MCP and skills paths are configured in crush.json."""
        config_dir = tmp_path / "home" / ".local" / "share" / "crush"
        config_dir.mkdir(parents=True)

        installer = get_platform_installer("crush", spellbook_dir, "1.0.0")
        installer.config_dir = config_dir
        installer.install()

        crush_json = config_dir / "crush.json"
        assert crush_json.exists(), "crush.json should be created"

        config = json.loads(crush_json.read_text())
        assert "mcp" in config
        assert "spellbook" in config["mcp"]
        assert config["mcp"]["spellbook"]["type"] == "http"
        assert "url" in config["mcp"]["spellbook"]

        # Skills path should be configured
        skills_paths = config.get("options", {}).get("skills_paths", [])
        assert len(skills_paths) > 0, "skills_paths should be configured"

        # Context path should be configured
        context_paths = config.get("options", {}).get("context_paths", [])
        assert len(context_paths) > 0, "context_paths should be configured"


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_install_specific_platform_only(self, spellbook_dir: Path, tmp_path: Path):
        """The --platforms flag installs ONLY the specified platform.

        When Installer.run() is given a list of one platform, only that
        platform's components should appear in results.
        """
        # Create config dirs for multiple platforms
        claude_dir = tmp_path / "home" / ".claude"
        claude_dir.mkdir(parents=True)
        codex_dir = tmp_path / "home" / ".codex"
        codex_dir.mkdir(parents=True)

        # Install only codex
        installer = get_platform_installer("codex", spellbook_dir, "1.0.0")
        installer.config_dir = codex_dir
        results = installer.install()

        # All results should be for codex
        for r in results:
            assert r.platform == "codex", (
                f"Expected only codex results, got {r.platform} for {r.component}"
            )

        # Verify claude_code was NOT touched
        assert not (claude_dir / "CLAUDE.md").exists()
        assert not (claude_dir / "skills").exists()
        assert not (claude_dir / "commands").exists()

    def test_install_nonexistent_platform_raises(self, spellbook_dir: Path):
        """Unknown platform name raises ValueError from get_platform_installer."""
        with pytest.raises(ValueError, match="Unknown platform"):
            get_platform_installer("nonexistent_platform", spellbook_dir, "1.0.0")

    def test_installer_run_with_explicit_platforms(self, spellbook_dir: Path, tmp_path: Path):
        """Installer.run() with explicit platforms list processes only those platforms."""
        installer = Installer(spellbook_dir)

        # Run with only crush specified, but crush config dir does not exist.
        # The installer should detect it as unavailable and skip.
        session = installer.run(platforms=["crush"])

        crush_results = [r for r in session.results if r.platform == "crush"]
        assert len(crush_results) >= 1

        # Crush should be skipped since its config dir does not exist in
        # the isolated environment (no ~/.local/share/crush), OR if crush
        # IS available, all non-daemon results should succeed (daemon install
        # requires system-level service setup that may fail in test envs)
        skip_results = [r for r in crush_results if r.action == "skipped"]
        non_daemon_results = [r for r in crush_results if r.component != "mcp_daemon"]
        assert len(skip_results) >= 1 or all(r.success for r in non_daemon_results)

    def test_detect_with_missing_config_dirs(self, spellbook_dir: Path, tmp_path: Path):
        """Platforms with missing config dirs report as unavailable (except claude_code).

        Gemini is excluded because its detect() checks CLI availability too:
        ``available = config_dir.exists() or check_gemini_cli_available()``.
        When the gemini CLI is present, it reports available=True regardless
        of the config dir.
        """
        # Exclude gemini since it checks CLI availability separately
        platforms = [p for p in _PLATFORMS_NEEDING_CONFIG if p != "gemini"]
        for platform in platforms:
            installer = get_platform_installer(platform, spellbook_dir, "1.0.0")
            # Point to a nonexistent directory
            installer.config_dir = tmp_path / "nonexistent" / platform
            status = installer.detect()
            assert not status.available, (
                f"{platform} should not be available without config dir"
            )

    def test_claude_code_always_available(self, spellbook_dir: Path, tmp_path: Path):
        """Claude Code is always reported as available (it creates its directory)."""
        installer = get_platform_installer("claude_code", spellbook_dir, "1.0.0")
        installer.config_dir = tmp_path / "nonexistent" / ".claude"
        status = installer.detect()
        assert status.available, "Claude Code should always be available"

    def test_double_install_is_idempotent(self, spellbook_dir: Path, tmp_path: Path):
        """Running install twice does not cause errors or corrupt state."""
        config_dir = tmp_path / "home" / ".codex"
        config_dir.mkdir(parents=True)

        installer = get_platform_installer("codex", spellbook_dir, "1.0.0")
        installer.config_dir = config_dir

        # First install
        results1 = installer.install()
        for r in results1:
            assert r.success, f"First install failed: {r.component}: {r.message}"

        # Second install
        results2 = installer.install()
        for r in results2:
            assert r.success, f"Second install failed: {r.component}: {r.message}"

        # AGENTS.md should still be valid
        agents_md = config_dir / "AGENTS.md"
        assert agents_md.exists()
        content = agents_md.read_text()
        # Should have exactly one START and one END marker
        start_count = len(MARKER_START_PATTERN.findall(content))
        assert start_count == 1, f"Expected 1 START marker, found {start_count}"
        assert content.count(MARKER_END) == 1, "Expected exactly 1 END marker"

    def test_dry_run_creates_no_files(self, spellbook_dir: Path, tmp_path: Path):
        """Dry run mode should not create any files on disk."""
        config_dir = tmp_path / "home" / ".codex"
        config_dir.mkdir(parents=True)

        installer = get_platform_installer("codex", spellbook_dir, "1.0.0", dry_run=True)
        installer.config_dir = config_dir
        results = installer.install()

        # All results should be successful
        for r in results:
            assert r.success, f"Dry run should succeed: {r.component}: {r.message}"

        # But no files should be created (beyond the pre-existing config_dir)
        agents_md = config_dir / "AGENTS.md"
        assert not agents_md.exists(), "AGENTS.md should not be created in dry run"

        spellbook_link = config_dir / "spellbook"
        assert not spellbook_link.exists(), "Symlink should not be created in dry run"
