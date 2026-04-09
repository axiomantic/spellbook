"""Tests for installer.components.aliases."""

from pathlib import Path

import pytest

from installer.components.aliases import (
    _ALIAS_RE,
    _END_MARKER,
    _START_MARKER,
    detect_existing_aliases,
    generate_alias_block,
    get_shell_rc_path,
    install_aliases,
    uninstall_aliases,
)


# ---------------------------------------------------------------------------
# get_shell_rc_path
# ---------------------------------------------------------------------------


class TestGetShellRcPath:
    def test_zsh(self, monkeypatch):
        monkeypatch.setenv("SHELL", "/bin/zsh")
        result = get_shell_rc_path()
        assert result is not None
        assert result.name == ".zshrc"

    def test_bash(self, monkeypatch):
        monkeypatch.setenv("SHELL", "/bin/bash")
        result = get_shell_rc_path()
        assert result is not None
        assert result.name == ".bashrc"

    def test_fish(self, monkeypatch):
        monkeypatch.setenv("SHELL", "/usr/bin/fish")
        result = get_shell_rc_path()
        assert result is not None
        assert result == Path.home() / ".config" / "fish" / "config.fish"

    def test_unknown_shell(self, monkeypatch):
        monkeypatch.setenv("SHELL", "/usr/bin/tcsh")
        assert get_shell_rc_path() is None

    def test_no_shell_env(self, monkeypatch):
        monkeypatch.delenv("SHELL", raising=False)
        assert get_shell_rc_path() is None


# ---------------------------------------------------------------------------
# generate_alias_block
# ---------------------------------------------------------------------------


class TestGenerateAliasBlock:
    def test_bash_zsh_syntax(self, tmp_path):
        block = generate_alias_block(tmp_path, fish=False)
        assert "alias claude=" in block
        assert "alias opencode=" in block
        # bash/zsh uses = with single quotes
        assert f"alias claude='{tmp_path / 'scripts' / 'spellbook-sandbox'}'" in block

    def test_fish_syntax(self, tmp_path):
        block = generate_alias_block(tmp_path, fish=True)
        # fish uses space, not =
        assert "alias claude '" in block
        assert "alias opencode '" in block
        assert "=" not in block

    def test_path_with_spaces(self, tmp_path):
        spellbook_dir = tmp_path / "my spellbook dir"
        spellbook_dir.mkdir()
        block = generate_alias_block(spellbook_dir, fish=False)
        # Path is enclosed in single quotes, so spaces are safe
        assert "my spellbook dir" in block
        assert "alias claude='" in block


# ---------------------------------------------------------------------------
# install_aliases
# ---------------------------------------------------------------------------


class TestInstallAliases:
    def _patch_rc(self, monkeypatch, rc_path):
        """Monkey-patch get_shell_rc_path to return rc_path."""
        monkeypatch.setattr(
            "installer.components.aliases.get_shell_rc_path", lambda: rc_path
        )

    def test_creates_rc_if_missing(self, monkeypatch, tmp_path):
        rc = tmp_path / ".zshrc"
        self._patch_rc(monkeypatch, rc)

        result = install_aliases(tmp_path)
        assert result["installed"] is True
        assert rc.exists()
        content = rc.read_text()
        assert _START_MARKER in content
        assert _END_MARKER in content

    def test_appends_to_existing_rc(self, monkeypatch, tmp_path):
        rc = tmp_path / ".zshrc"
        rc.write_text("# existing stuff\nexport FOO=bar\n", encoding="utf-8")
        self._patch_rc(monkeypatch, rc)

        install_aliases(tmp_path)
        content = rc.read_text()
        assert content.startswith("# existing stuff\n")
        assert _START_MARKER in content

    def test_idempotent(self, monkeypatch, tmp_path):
        rc = tmp_path / ".zshrc"
        self._patch_rc(monkeypatch, rc)

        install_aliases(tmp_path)
        install_aliases(tmp_path)
        content = rc.read_text()
        assert content.count(_START_MARKER) == 1
        assert content.count(_END_MARKER) == 1

    def test_updates_existing_block(self, monkeypatch, tmp_path):
        rc = tmp_path / ".zshrc"
        self._patch_rc(monkeypatch, rc)

        first_dir = tmp_path / "alpha-spellbook"
        second_dir = tmp_path / "beta-spellbook"

        # Install with one path
        install_aliases(first_dir)
        # Install with a different path -- should replace, not duplicate
        install_aliases(second_dir)
        content = rc.read_text()
        assert content.count(_START_MARKER) == 1
        assert "beta-spellbook" in content
        assert "alpha-spellbook" not in content

    def test_no_trailing_newline_in_rc(self, monkeypatch, tmp_path):
        rc = tmp_path / ".zshrc"
        rc.write_text("export A=1", encoding="utf-8")  # no trailing newline
        self._patch_rc(monkeypatch, rc)

        install_aliases(tmp_path)
        content = rc.read_text()
        # Should not smash existing content into the marker line
        assert "export A=1\n" in content
        assert _START_MARKER in content

    def test_dry_run_does_not_write(self, monkeypatch, tmp_path):
        rc = tmp_path / ".zshrc"
        self._patch_rc(monkeypatch, rc)

        result = install_aliases(tmp_path, dry_run=True)
        assert result["installed"] is True
        assert not rc.exists()

    def test_unknown_shell_returns_skipped(self, monkeypatch):
        monkeypatch.setattr(
            "installer.components.aliases.get_shell_rc_path", lambda: None
        )
        result = install_aliases(Path("/tmp/sb"))
        assert result["installed"] is False
        assert result["skipped_reason"] is not None

    def test_creates_parent_dirs_for_fish(self, monkeypatch, tmp_path):
        """Fish config lives in ~/.config/fish/ which may not exist."""
        rc = tmp_path / ".config" / "fish" / "config.fish"
        self._patch_rc(monkeypatch, rc)

        result = install_aliases(tmp_path)
        assert result["installed"] is True
        assert rc.exists()

    def test_path_with_spaces_roundtrip(self, monkeypatch, tmp_path):
        spellbook_dir = tmp_path / "my spellbook"
        spellbook_dir.mkdir()
        rc = tmp_path / ".zshrc"
        self._patch_rc(monkeypatch, rc)

        install_aliases(spellbook_dir)
        content = rc.read_text()
        assert "my spellbook" in content
        # The path is wrapped in single quotes
        assert f"'{spellbook_dir / 'scripts' / 'spellbook-sandbox'}'" in content


# ---------------------------------------------------------------------------
# uninstall_aliases
# ---------------------------------------------------------------------------


class TestUninstallAliases:
    def _patch_rc(self, monkeypatch, rc_path):
        monkeypatch.setattr(
            "installer.components.aliases.get_shell_rc_path", lambda: rc_path
        )

    def test_removes_demarcated_block(self, monkeypatch, tmp_path):
        rc = tmp_path / ".zshrc"
        self._patch_rc(monkeypatch, rc)

        install_aliases(tmp_path)
        result = uninstall_aliases()
        assert result["removed"] is True
        content = rc.read_text()
        assert _START_MARKER not in content
        assert _END_MARKER not in content

    def test_preserves_surrounding_content(self, monkeypatch, tmp_path):
        rc = tmp_path / ".zshrc"
        rc.write_text("# before\nexport A=1\n", encoding="utf-8")
        self._patch_rc(monkeypatch, rc)

        install_aliases(tmp_path)
        # Append something after the block
        content = rc.read_text()
        rc.write_text(content + "# after\n", encoding="utf-8")

        uninstall_aliases()
        content = rc.read_text()
        assert "export A=1" in content
        assert "# after" in content
        assert _START_MARKER not in content

    def test_no_block_returns_not_removed(self, monkeypatch, tmp_path):
        rc = tmp_path / ".zshrc"
        rc.write_text("# nothing here\n", encoding="utf-8")
        self._patch_rc(monkeypatch, rc)

        result = uninstall_aliases()
        assert result["removed"] is False

    def test_no_rc_file(self, monkeypatch, tmp_path):
        rc = tmp_path / ".zshrc"
        self._patch_rc(monkeypatch, rc)
        # rc doesn't exist
        result = uninstall_aliases()
        assert result["removed"] is False

    def test_unknown_shell(self, monkeypatch):
        monkeypatch.setattr(
            "installer.components.aliases.get_shell_rc_path", lambda: None
        )
        result = uninstall_aliases()
        assert result["removed"] is False


# ---------------------------------------------------------------------------
# detect_existing_aliases
# ---------------------------------------------------------------------------


class TestDetectExistingAliases:
    def test_finds_aliases_in_block(self, tmp_path):
        rc = tmp_path / ".zshrc"
        content = (
            f"{_START_MARKER}\n"
            "alias claude='/foo/scripts/spellbook-sandbox'\n"
            "alias opencode='/foo/scripts/spellbook-sandbox opencode'\n"
            f"{_END_MARKER}\n"
        )
        rc.write_text(content, encoding="utf-8")
        result = detect_existing_aliases(rc)
        assert result["claude"] is not None
        assert result["opencode"] is not None

    def test_ignores_non_spellbook_aliases(self, tmp_path):
        rc = tmp_path / ".zshrc"
        rc.write_text("alias claude='/usr/bin/something-else'\n", encoding="utf-8")
        result = detect_existing_aliases(rc)
        assert result["claude"] is None

    def test_missing_file(self, tmp_path):
        rc = tmp_path / ".zshrc"
        result = detect_existing_aliases(rc)
        assert result == {"claude": None, "opencode": None}

    def test_fish_syntax(self, tmp_path):
        rc = tmp_path / "config.fish"
        content = "alias claude '/foo/scripts/spellbook-sandbox'\n"
        rc.write_text(content, encoding="utf-8")
        result = detect_existing_aliases(rc)
        assert result["claude"] is not None


# ---------------------------------------------------------------------------
# Regex pattern
# ---------------------------------------------------------------------------


class TestAliasRegex:
    def test_matches_bash_alias(self):
        m = _ALIAS_RE.search("alias claude='/path/to/spellbook-sandbox'")
        assert m is not None
        assert m.group(1) == "claude"

    def test_matches_fish_alias(self):
        m = _ALIAS_RE.search("alias claude '/path/to/spellbook-sandbox'")
        assert m is not None
        assert m.group(1) == "claude"

    def test_no_match_for_other_aliases(self):
        m = _ALIAS_RE.search("alias vim='nvim'")
        assert m is None
