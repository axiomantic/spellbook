"""Tests for installer.migrations one-shot cleanup helpers.

Covers the SPELLBOOK_ALIASES legacy block stripper used during install
and uninstall. All tests operate on tmp_path; the real ~/.zshrc must
never be touched.
"""

from __future__ import annotations

from pathlib import Path

from installer.migrations import (
    cleanup_legacy_alias_block,
    run_all_migrations,
)


def test_missing_rc_file_returns_false(tmp_path: Path) -> None:
    rc = tmp_path / "nonexistent-zshrc"
    assert cleanup_legacy_alias_block(rc) is False
    assert not rc.exists()


def test_empty_rc_file_is_noop(tmp_path: Path) -> None:
    rc = tmp_path / ".zshrc"
    rc.write_text("")
    assert cleanup_legacy_alias_block(rc) is False
    assert rc.read_text() == ""


def test_rc_without_markers_is_noop(tmp_path: Path) -> None:
    rc = tmp_path / ".zshrc"
    body = "export PATH=/usr/local/bin:$PATH\nalias gs='git status'\n"
    rc.write_text(body)
    assert cleanup_legacy_alias_block(rc) is False
    assert rc.read_text() == body


def test_alias_block_is_removed_and_surrounding_content_preserved(
    tmp_path: Path,
) -> None:
    rc = tmp_path / ".zshrc"
    rc.write_text(
        "export PATH=/usr/local/bin:$PATH\n"
        "\n"
        "# SPELLBOOK_ALIASES:START\n"
        "alias claude='spellbook-sandbox claude'\n"
        "alias opencode='spellbook-sandbox opencode'\n"
        "# SPELLBOOK_ALIASES:END\n"
        "\n"
        "alias gs='git status'\n"
    )

    assert cleanup_legacy_alias_block(rc) is True

    text = rc.read_text()
    assert "SPELLBOOK_ALIASES" not in text
    assert "spellbook-sandbox" not in text
    assert "export PATH=/usr/local/bin:$PATH" in text
    assert "alias gs='git status'" in text


def test_cleanup_is_idempotent(tmp_path: Path) -> None:
    rc = tmp_path / ".zshrc"
    rc.write_text(
        "header\n"
        "# SPELLBOOK_ALIASES:START\n"
        "alias claude='spellbook-sandbox claude'\n"
        "# SPELLBOOK_ALIASES:END\n"
        "footer\n"
    )

    assert cleanup_legacy_alias_block(rc) is True
    first_pass = rc.read_text()

    # Second pass must not change anything.
    assert cleanup_legacy_alias_block(rc) is False
    assert rc.read_text() == first_pass


def test_run_all_migrations_uses_home_and_returns_modified(
    tmp_path: Path, monkeypatch
) -> None:
    """run_all_migrations() must iterate ~/.zshrc, ~/.bashrc, fish config."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

    zshrc = fake_home / ".zshrc"
    bashrc = fake_home / ".bashrc"
    fish_dir = fake_home / ".config" / "fish"
    fish_dir.mkdir(parents=True)
    fish_conf = fish_dir / "config.fish"

    zshrc.write_text(
        "# SPELLBOOK_ALIASES:START\n"
        "alias claude='spellbook-sandbox claude'\n"
        "# SPELLBOOK_ALIASES:END\n"
    )
    bashrc.write_text("alias ll='ls -la'\n")  # no markers
    fish_conf.write_text(
        "# SPELLBOOK_ALIASES:START\n"
        "alias opencode 'spellbook-sandbox opencode'\n"
        "# SPELLBOOK_ALIASES:END\n"
    )

    modified = run_all_migrations()

    assert zshrc in modified
    assert fish_conf in modified
    assert bashrc not in modified
    assert "SPELLBOOK_ALIASES" not in zshrc.read_text()
    assert "SPELLBOOK_ALIASES" not in fish_conf.read_text()
    assert bashrc.read_text() == "alias ll='ls -la'\n"


def test_run_all_migrations_clean_machine_returns_empty(
    tmp_path: Path, monkeypatch
) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

    # No rc files exist at all.
    assert run_all_migrations() == []
