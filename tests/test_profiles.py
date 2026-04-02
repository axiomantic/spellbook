"""Tests for spellbook.core.profiles module."""


class TestParseProfileFrontmatter:
    """Tests for parse_profile_frontmatter()."""

    def test_valid_frontmatter(self):
        from spellbook.core.profiles import parse_profile_frontmatter

        content = "---\nname: Test Profile\ndescription: A test\n---\n\nBody content here."
        meta, body = parse_profile_frontmatter(content)
        assert meta == {"name": "Test Profile", "description": "A test"}
        assert body == "Body content here."

    def test_no_frontmatter(self):
        from spellbook.core.profiles import parse_profile_frontmatter

        content = "Just plain content with no frontmatter."
        meta, body = parse_profile_frontmatter(content)
        assert meta == {}
        assert body == "Just plain content with no frontmatter."

    def test_malformed_frontmatter_single_delimiter(self):
        from spellbook.core.profiles import parse_profile_frontmatter

        content = "---\nname: Test\nNo closing delimiter"
        meta, body = parse_profile_frontmatter(content)
        assert meta == {}
        assert body == content

    def test_empty_file(self):
        from spellbook.core.profiles import parse_profile_frontmatter

        meta, body = parse_profile_frontmatter("")
        assert meta == {}
        assert body == ""

    def test_frontmatter_no_colon(self):
        from spellbook.core.profiles import parse_profile_frontmatter

        content = "---\njust a line without colon\n---\n\nBody"
        meta, body = parse_profile_frontmatter(content)
        assert meta == {}
        assert body == "Body"

    def test_frontmatter_extra_colons_in_value(self):
        from spellbook.core.profiles import parse_profile_frontmatter

        content = "---\nname: Profile: The Sequel\ndescription: Test\n---\n\nBody"
        meta, body = parse_profile_frontmatter(content)
        assert meta == {"name": "Profile: The Sequel", "description": "Test"}
        assert body == "Body"


class TestDiscoverProfiles:
    """Tests for discover_profiles()."""

    def test_bundled_only(self, tmp_path):
        """Discovers profiles from bundled directory only."""
        import bigfoot

        from spellbook.core.profiles import discover_profiles

        bundled_dir = tmp_path / "bundled" / "profiles"
        bundled_dir.mkdir(parents=True)
        (bundled_dir / "alpha.md").write_text(
            "---\nname: Alpha\ndescription: First\n---\n\nAlpha body",
            encoding="utf-8",
        )

        get_spellbook_dir = bigfoot.mock("spellbook.core.profiles:get_spellbook_dir")
        get_spellbook_dir.returns(tmp_path / "bundled")
        get_config_dir = bigfoot.mock("spellbook.core.profiles:get_config_dir")
        get_config_dir.returns(tmp_path / "custom")  # does not exist

        with bigfoot:
            profiles = discover_profiles()

        get_spellbook_dir.assert_call()
        get_config_dir.assert_call()

        assert len(profiles) == 1
        assert profiles[0].slug == "alpha"
        assert profiles[0].name == "Alpha"
        assert profiles[0].description == "First"
        assert profiles[0].is_custom is False

    def test_custom_overrides_bundled(self, tmp_path):
        """Custom profile with same slug takes precedence over bundled."""
        import bigfoot

        from spellbook.core.profiles import discover_profiles

        bundled_dir = tmp_path / "bundled" / "profiles"
        bundled_dir.mkdir(parents=True)
        (bundled_dir / "alpha.md").write_text(
            "---\nname: Alpha Bundled\ndescription: Bundled\n---\n\nBundled body",
            encoding="utf-8",
        )

        custom_dir = tmp_path / "custom" / "profiles"
        custom_dir.mkdir(parents=True)
        (custom_dir / "alpha.md").write_text(
            "---\nname: Alpha Custom\ndescription: Custom\n---\n\nCustom body",
            encoding="utf-8",
        )

        get_spellbook_dir = bigfoot.mock("spellbook.core.profiles:get_spellbook_dir")
        get_spellbook_dir.returns(tmp_path / "bundled")
        get_config_dir = bigfoot.mock("spellbook.core.profiles:get_config_dir")
        get_config_dir.returns(tmp_path / "custom")

        with bigfoot:
            profiles = discover_profiles()

        get_spellbook_dir.assert_call()
        get_config_dir.assert_call()

        assert len(profiles) == 1
        assert profiles[0].name == "Alpha Custom"
        assert profiles[0].is_custom is True

    def test_empty_dirs(self, tmp_path):
        """Returns empty list when no profile files exist."""
        import bigfoot

        from spellbook.core.profiles import discover_profiles

        bundled_dir = tmp_path / "bundled" / "profiles"
        bundled_dir.mkdir(parents=True)
        custom_dir = tmp_path / "custom" / "profiles"
        custom_dir.mkdir(parents=True)

        get_spellbook_dir = bigfoot.mock("spellbook.core.profiles:get_spellbook_dir")
        get_spellbook_dir.returns(tmp_path / "bundled")
        get_config_dir = bigfoot.mock("spellbook.core.profiles:get_config_dir")
        get_config_dir.returns(tmp_path / "custom")

        with bigfoot:
            profiles = discover_profiles()

        get_spellbook_dir.assert_call()
        get_config_dir.assert_call()

        assert profiles == []

    def test_no_dirs_exist(self, tmp_path):
        """Returns empty list when profile directories do not exist."""
        import bigfoot

        from spellbook.core.profiles import discover_profiles

        get_spellbook_dir = bigfoot.mock("spellbook.core.profiles:get_spellbook_dir")
        get_spellbook_dir.returns(tmp_path / "nonexistent-bundled")
        get_config_dir = bigfoot.mock("spellbook.core.profiles:get_config_dir")
        get_config_dir.returns(tmp_path / "nonexistent-custom")

        with bigfoot:
            profiles = discover_profiles()

        get_spellbook_dir.assert_call()
        get_config_dir.assert_call()

        assert profiles == []

    def test_sorted_by_name(self, tmp_path):
        """Profiles are returned sorted by name."""
        import bigfoot

        from spellbook.core.profiles import discover_profiles

        bundled_dir = tmp_path / "bundled" / "profiles"
        bundled_dir.mkdir(parents=True)
        (bundled_dir / "zebra.md").write_text(
            "---\nname: Zebra\ndescription: Last\n---\n\nZ body",
            encoding="utf-8",
        )
        (bundled_dir / "alpha.md").write_text(
            "---\nname: Alpha\ndescription: First\n---\n\nA body",
            encoding="utf-8",
        )

        get_spellbook_dir = bigfoot.mock("spellbook.core.profiles:get_spellbook_dir")
        get_spellbook_dir.returns(tmp_path / "bundled")
        get_config_dir = bigfoot.mock("spellbook.core.profiles:get_config_dir")
        get_config_dir.returns(tmp_path / "custom")

        with bigfoot:
            profiles = discover_profiles()

        get_spellbook_dir.assert_call()
        get_config_dir.assert_call()

        assert [p.name for p in profiles] == ["Alpha", "Zebra"]


class TestLoadProfile:
    """Tests for load_profile()."""

    def test_found_in_custom(self, tmp_path):
        """Loads profile from custom directory when it exists there."""
        import bigfoot

        from spellbook.core.profiles import load_profile

        custom_dir = tmp_path / "custom" / "profiles"
        custom_dir.mkdir(parents=True)
        (custom_dir / "test.md").write_text(
            "---\nname: Test\ndescription: Desc\n---\n\nCustom body content",
            encoding="utf-8",
        )

        get_spellbook_dir = bigfoot.mock("spellbook.core.profiles:get_spellbook_dir")
        get_spellbook_dir.returns(tmp_path / "bundled")
        get_config_dir = bigfoot.mock("spellbook.core.profiles:get_config_dir")
        get_config_dir.returns(tmp_path / "custom")

        with bigfoot:
            content = load_profile("test")

        get_config_dir.assert_call()
        get_spellbook_dir.assert_call()

        assert content == "Custom body content"

    def test_found_in_bundled(self, tmp_path):
        """Falls back to bundled directory when custom does not have it."""
        import bigfoot

        from spellbook.core.profiles import load_profile

        bundled_dir = tmp_path / "bundled" / "profiles"
        bundled_dir.mkdir(parents=True)
        (bundled_dir / "test.md").write_text(
            "---\nname: Test\ndescription: Desc\n---\n\nBundled body content",
            encoding="utf-8",
        )

        get_spellbook_dir = bigfoot.mock("spellbook.core.profiles:get_spellbook_dir")
        get_spellbook_dir.returns(tmp_path / "bundled")
        get_config_dir = bigfoot.mock("spellbook.core.profiles:get_config_dir")
        get_config_dir.returns(tmp_path / "custom")  # no profiles dir here

        with bigfoot:
            content = load_profile("test")

        get_config_dir.assert_call()
        get_spellbook_dir.assert_call()

        assert content == "Bundled body content"

    def test_not_found(self, tmp_path):
        """Returns None when profile slug does not match any file."""
        import bigfoot

        from spellbook.core.profiles import load_profile

        get_spellbook_dir = bigfoot.mock("spellbook.core.profiles:get_spellbook_dir")
        get_spellbook_dir.returns(tmp_path / "bundled")
        get_config_dir = bigfoot.mock("spellbook.core.profiles:get_config_dir")
        get_config_dir.returns(tmp_path / "custom")

        with bigfoot:
            content = load_profile("nonexistent")

        get_config_dir.assert_call()
        get_spellbook_dir.assert_call()

        assert content is None

    def test_empty_file_returns_none(self, tmp_path):
        """Returns None for an empty profile file (falsy body)."""
        import bigfoot

        from spellbook.core.profiles import load_profile

        custom_dir = tmp_path / "custom" / "profiles"
        custom_dir.mkdir(parents=True)
        (custom_dir / "empty.md").write_text("", encoding="utf-8")

        get_spellbook_dir = bigfoot.mock("spellbook.core.profiles:get_spellbook_dir")
        get_spellbook_dir.returns(tmp_path / "bundled")
        get_config_dir = bigfoot.mock("spellbook.core.profiles:get_config_dir")
        get_config_dir.returns(tmp_path / "custom")

        with bigfoot:
            content = load_profile("empty")

        get_config_dir.assert_call()
        get_spellbook_dir.assert_call()

        assert content is None


class TestRendererProfileWizardContract:
    """Verify render_profile_wizard is defined on InstallerRenderer."""

    def test_abstract_method_exists(self):
        from installer.renderer import InstallerRenderer

        assert hasattr(InstallerRenderer, "render_profile_wizard")
        import inspect
        assert "render_profile_wizard" in [
            name for name, _ in inspect.getmembers(InstallerRenderer)
            if not name.startswith("_")
        ]


class TestRichRendererProfileWizard:
    """Tests for RichRenderer.render_profile_wizard."""

    def test_auto_yes_returns_empty(self):
        from installer.renderer import RichRenderer

        renderer = RichRenderer(auto_yes=True)
        result = renderer.render_profile_wizard()
        assert result == {}

    def test_no_profiles_returns_empty(self):
        import bigfoot

        from installer.renderer import RichRenderer

        discover = bigfoot.mock("spellbook.core.profiles:discover_profiles")
        discover.returns([])

        renderer = RichRenderer(auto_yes=False)

        with bigfoot:
            result = renderer.render_profile_wizard()

        discover.assert_call()
        assert result == {}

    def test_already_configured_not_reconfigure_returns_empty(self):
        import bigfoot

        from spellbook.core.profiles import ProfileInfo
        from installer.renderer import RichRenderer
        from pathlib import Path

        discover = bigfoot.mock("spellbook.core.profiles:discover_profiles")
        discover.returns([
            ProfileInfo(slug="test", name="Test", description="Desc", path=Path("/fake"), is_custom=False),
        ])
        is_set = bigfoot.mock("spellbook.core.config:config_is_explicitly_set")
        is_set.returns(True)

        renderer = RichRenderer(auto_yes=False)

        with bigfoot:
            result = renderer.render_profile_wizard(reconfigure=False)

        discover.assert_call()
        is_set.assert_call(args=("profile.default",))
        assert result == {}

    def test_selects_profile_returns_slug(self):
        import bigfoot

        from spellbook.core.profiles import ProfileInfo
        from installer.renderer import RichRenderer
        from pathlib import Path

        discover = bigfoot.mock("spellbook.core.profiles:discover_profiles")
        discover.returns([
            ProfileInfo(slug="radical-collaborator", name="Radical Collaborator", description="Partnership", path=Path("/fake"), is_custom=False),
        ])
        is_set = bigfoot.mock("spellbook.core.config:config_is_explicitly_set")
        is_set.returns(False)

        renderer = RichRenderer(auto_yes=False)
        prompt = bigfoot.mock.object(renderer, "prompt_choice")
        prompt.returns(1)

        with bigfoot:
            result = renderer.render_profile_wizard()

        discover.assert_call()
        is_set.assert_call(args=("profile.default",))
        prompt.assert_call(args=(
            "Select a session profile:",
            ["None (no session profile)", "Radical Collaborator - Partnership"],
        ), kwargs={"default": 0})
        assert result == {"profile.default": "radical-collaborator"}

    def test_selects_none_returns_empty_string(self):
        import bigfoot

        from spellbook.core.profiles import ProfileInfo
        from installer.renderer import RichRenderer
        from pathlib import Path

        discover = bigfoot.mock("spellbook.core.profiles:discover_profiles")
        discover.returns([
            ProfileInfo(slug="radical-collaborator", name="Radical Collaborator", description="Partnership", path=Path("/fake"), is_custom=False),
        ])
        is_set = bigfoot.mock("spellbook.core.config:config_is_explicitly_set")
        is_set.returns(False)

        renderer = RichRenderer(auto_yes=False)
        prompt = bigfoot.mock.object(renderer, "prompt_choice")
        prompt.returns(0)

        with bigfoot:
            result = renderer.render_profile_wizard()

        discover.assert_call()
        is_set.assert_call(args=("profile.default",))
        prompt.assert_call(args=(
            "Select a session profile:",
            ["None (no session profile)", "Radical Collaborator - Partnership"],
        ), kwargs={"default": 0})
        assert result == {"profile.default": ""}


class TestPlainTextRendererProfileWizard:
    """Tests for PlainTextRenderer.render_profile_wizard."""

    def test_auto_yes_returns_empty(self):
        from installer.renderer import PlainTextRenderer

        renderer = PlainTextRenderer(auto_yes=True)
        result = renderer.render_profile_wizard()
        assert result == {}

    def test_no_profiles_returns_empty(self):
        import bigfoot

        from installer.renderer import PlainTextRenderer

        discover = bigfoot.mock("spellbook.core.profiles:discover_profiles")
        discover.returns([])

        renderer = PlainTextRenderer(auto_yes=False)

        with bigfoot:
            result = renderer.render_profile_wizard()

        discover.assert_call()
        assert result == {}

    def test_selects_profile_returns_slug(self):
        import bigfoot

        from spellbook.core.profiles import ProfileInfo
        from installer.renderer import PlainTextRenderer
        from pathlib import Path

        discover = bigfoot.mock("spellbook.core.profiles:discover_profiles")
        discover.returns([
            ProfileInfo(slug="radical-collaborator", name="Radical Collaborator", description="Partnership", path=Path("/fake"), is_custom=False),
        ])
        is_set = bigfoot.mock("spellbook.core.config:config_is_explicitly_set")
        is_set.returns(False)

        renderer = PlainTextRenderer(auto_yes=False)
        prompt = bigfoot.mock.object(renderer, "prompt_choice")
        prompt.returns(1)

        with bigfoot:
            result = renderer.render_profile_wizard()

        discover.assert_call()
        is_set.assert_call(args=("profile.default",))
        prompt.assert_call(args=(
            "Select a session profile:",
            ["None (no session profile)", "Radical Collaborator - Partnership"],
        ), kwargs={"default": 0})
        assert result == {"profile.default": "radical-collaborator"}
