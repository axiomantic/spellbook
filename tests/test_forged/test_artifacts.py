"""Tests for forged artifact storage operations."""

import os
import tempfile
from pathlib import Path

import pytest


class TestGetProjectEncoded:
    """Tests for project path encoding."""

    def test_removes_leading_slash(self):
        from spellbook_mcp.forged.artifacts import get_project_encoded

        assert get_project_encoded("/Users/alice/project") == "Users-alice-project"

    def test_replaces_all_slashes_with_dashes(self):
        from spellbook_mcp.forged.artifacts import get_project_encoded

        result = get_project_encoded("/home/user/dev/myproject")
        assert result == "home-user-dev-myproject"
        assert "/" not in result

    def test_handles_path_without_leading_slash(self):
        from spellbook_mcp.forged.artifacts import get_project_encoded

        result = get_project_encoded("relative/path")
        assert result == "relative-path"

    def test_handles_single_component_path(self):
        from spellbook_mcp.forged.artifacts import get_project_encoded

        assert get_project_encoded("/project") == "project"

    def test_handles_trailing_slash(self):
        from spellbook_mcp.forged.artifacts import get_project_encoded

        result = get_project_encoded("/Users/alice/project/")
        # Trailing slash becomes trailing dash, which is acceptable
        assert result.startswith("Users-alice-project")


class TestArtifactBasePath:
    """Tests for artifact base path generation."""

    def test_includes_project_encoded(self):
        from spellbook_mcp.forged.artifacts import artifact_base_path

        path = artifact_base_path("/Users/alice/project", "my-feature")
        assert "Users-alice-project" in path

    def test_includes_feature_name(self):
        from spellbook_mcp.forged.artifacts import artifact_base_path

        path = artifact_base_path("/Users/alice/project", "my-feature")
        assert "my-feature" in path

    def test_under_spellbook_docs(self):
        from spellbook_mcp.forged.artifacts import artifact_base_path

        path = artifact_base_path("/Users/alice/project", "feature")
        assert "/.local/spellbook/docs/" in path

    def test_includes_forged_directory(self):
        from spellbook_mcp.forged.artifacts import artifact_base_path

        path = artifact_base_path("/Users/alice/project", "feature")
        assert "/forged/" in path

    def test_expands_home_directory(self):
        from spellbook_mcp.forged.artifacts import artifact_base_path

        path = artifact_base_path("/project", "feature")
        # Should not start with ~ after expansion
        assert not path.startswith("~")
        assert path.startswith("/")


class TestArtifactPath:
    """Tests for specific artifact path generation."""

    def test_requirement_artifact(self):
        from spellbook_mcp.forged.artifacts import artifact_path

        path = artifact_path("/Users/alice/project", "my-feature", "requirement")
        assert path.endswith("forged/my-feature/requirements.md")

    def test_design_artifact(self):
        from spellbook_mcp.forged.artifacts import artifact_path

        path = artifact_path("/Users/alice/project", "my-feature", "design")
        assert path.endswith("forged/my-feature/design.md")

    def test_plan_artifact(self):
        from spellbook_mcp.forged.artifacts import artifact_path

        path = artifact_path("/Users/alice/project", "my-feature", "plan")
        assert path.endswith("forged/my-feature/implementation-plan.md")

    def test_progress_artifact(self):
        from spellbook_mcp.forged.artifacts import artifact_path

        path = artifact_path("/Users/alice/project", "my-feature", "progress")
        assert path.endswith("forged/my-feature/progress.json")

    def test_reflection_requires_iteration(self):
        from spellbook_mcp.forged.artifacts import artifact_path

        with pytest.raises(ValueError, match="iteration"):
            artifact_path("/path", "feature", "reflection")

    def test_reflection_with_iteration(self):
        from spellbook_mcp.forged.artifacts import artifact_path

        path = artifact_path("/path", "feature", "reflection", iteration=3)
        assert "reflections/reflection-3.md" in path

    def test_checkpoint_requires_iteration(self):
        from spellbook_mcp.forged.artifacts import artifact_path

        with pytest.raises(ValueError, match="iteration"):
            artifact_path("/path", "feature", "checkpoint")

    def test_checkpoint_with_iteration(self):
        from spellbook_mcp.forged.artifacts import artifact_path

        path = artifact_path("/path", "feature", "checkpoint", iteration=5)
        assert "checkpoints/checkpoint-5.json" in path

    def test_invalid_artifact_type_raises(self):
        from spellbook_mcp.forged.artifacts import artifact_path

        with pytest.raises(ValueError, match="Invalid artifact type"):
            artifact_path("/path", "feature", "invalid_type")

    def test_iteration_zero_is_valid(self):
        from spellbook_mcp.forged.artifacts import artifact_path

        path = artifact_path("/path", "feature", "reflection", iteration=0)
        assert "reflection-0.md" in path


class TestWriteArtifact:
    """Tests for writing artifacts."""

    def test_creates_parent_directories(self, tmp_path, monkeypatch):
        from spellbook_mcp.forged.artifacts import write_artifact

        # Create a nested path that doesn't exist
        artifact_file = tmp_path / "deeply" / "nested" / "path" / "artifact.md"
        assert not artifact_file.parent.exists()

        result = write_artifact(str(artifact_file), "test content")

        assert result is True
        assert artifact_file.exists()
        assert artifact_file.parent.exists()

    def test_writes_content_correctly(self, tmp_path):
        from spellbook_mcp.forged.artifacts import write_artifact

        artifact_file = tmp_path / "test.md"
        content = "# Test\n\nThis is test content."

        write_artifact(str(artifact_file), content)

        assert artifact_file.read_text() == content

    def test_overwrites_existing_file(self, tmp_path):
        from spellbook_mcp.forged.artifacts import write_artifact

        artifact_file = tmp_path / "test.md"
        artifact_file.write_text("old content")

        write_artifact(str(artifact_file), "new content")

        assert artifact_file.read_text() == "new content"

    def test_returns_true_on_success(self, tmp_path):
        from spellbook_mcp.forged.artifacts import write_artifact

        artifact_file = tmp_path / "test.md"
        result = write_artifact(str(artifact_file), "content")
        assert result is True

    def test_handles_unicode_content(self, tmp_path):
        from spellbook_mcp.forged.artifacts import write_artifact

        artifact_file = tmp_path / "unicode.md"
        content = "Unicode: \u2713 \u2717 \u2192 \u03b1\u03b2\u03b3"

        write_artifact(str(artifact_file), content)

        assert artifact_file.read_text() == content


class TestReadArtifact:
    """Tests for reading artifacts."""

    def test_nonexistent_returns_none(self):
        from spellbook_mcp.forged.artifacts import read_artifact

        result = read_artifact("/nonexistent/path/that/does/not/exist.md")
        assert result is None

    def test_reads_existing_file(self, tmp_path):
        from spellbook_mcp.forged.artifacts import read_artifact

        artifact_file = tmp_path / "test.md"
        artifact_file.write_text("test content")

        result = read_artifact(str(artifact_file))

        assert result == "test content"

    def test_reads_unicode_content(self, tmp_path):
        from spellbook_mcp.forged.artifacts import read_artifact

        artifact_file = tmp_path / "unicode.md"
        content = "Unicode: \u2713 \u2717"
        artifact_file.write_text(content)

        result = read_artifact(str(artifact_file))

        assert result == content

    def test_roundtrip_write_read(self, tmp_path):
        from spellbook_mcp.forged.artifacts import read_artifact, write_artifact

        artifact_file = tmp_path / "roundtrip.md"
        original_content = "# Header\n\nMultiple\nlines\nof content."

        write_artifact(str(artifact_file), original_content)
        result = read_artifact(str(artifact_file))

        assert result == original_content


class TestListArtifacts:
    """Tests for listing artifacts."""

    def test_empty_directory_returns_empty_list(self, tmp_path):
        from spellbook_mcp.forged.artifacts import list_artifacts

        result = list_artifacts(str(tmp_path))
        assert result == []

    def test_nonexistent_directory_returns_empty_list(self):
        from spellbook_mcp.forged.artifacts import list_artifacts

        result = list_artifacts("/nonexistent/directory/path")
        assert result == []

    def test_lists_all_files(self, tmp_path):
        from spellbook_mcp.forged.artifacts import list_artifacts

        # Create some files
        (tmp_path / "requirements.md").write_text("req")
        (tmp_path / "design.md").write_text("design")
        (tmp_path / "progress.json").write_text("{}")

        result = list_artifacts(str(tmp_path))

        assert len(result) == 3
        assert any("requirements.md" in p for p in result)
        assert any("design.md" in p for p in result)
        assert any("progress.json" in p for p in result)

    def test_filter_by_artifact_type_requirement(self, tmp_path):
        from spellbook_mcp.forged.artifacts import list_artifacts

        (tmp_path / "requirements.md").write_text("req")
        (tmp_path / "design.md").write_text("design")

        result = list_artifacts(str(tmp_path), artifact_type="requirement")

        assert len(result) == 1
        assert "requirements.md" in result[0]

    def test_filter_by_artifact_type_reflection(self, tmp_path):
        from spellbook_mcp.forged.artifacts import list_artifacts

        # Create reflections subdirectory
        reflections_dir = tmp_path / "reflections"
        reflections_dir.mkdir()
        (reflections_dir / "reflection-1.md").write_text("r1")
        (reflections_dir / "reflection-2.md").write_text("r2")
        (tmp_path / "design.md").write_text("design")

        result = list_artifacts(str(tmp_path), artifact_type="reflection")

        assert len(result) == 2
        assert all("reflection-" in p for p in result)

    def test_filter_by_artifact_type_checkpoint(self, tmp_path):
        from spellbook_mcp.forged.artifacts import list_artifacts

        # Create checkpoints subdirectory
        checkpoints_dir = tmp_path / "checkpoints"
        checkpoints_dir.mkdir()
        (checkpoints_dir / "checkpoint-1.json").write_text("{}")
        (checkpoints_dir / "checkpoint-2.json").write_text("{}")

        result = list_artifacts(str(tmp_path), artifact_type="checkpoint")

        assert len(result) == 2
        assert all("checkpoint-" in p for p in result)

    def test_includes_subdirectory_files(self, tmp_path):
        from spellbook_mcp.forged.artifacts import list_artifacts

        # Create nested structure
        (tmp_path / "requirements.md").write_text("req")
        reflections_dir = tmp_path / "reflections"
        reflections_dir.mkdir()
        (reflections_dir / "reflection-1.md").write_text("r1")

        result = list_artifacts(str(tmp_path))

        # Should include both top-level and subdirectory files
        assert len(result) >= 2


class TestEnsureArtifactDir:
    """Tests for ensuring artifact directory exists."""

    def test_creates_directory_if_missing(self, tmp_path, monkeypatch):
        from spellbook_mcp.forged.artifacts import ensure_artifact_dir

        # Redirect home to tmp_path for testing
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        result = ensure_artifact_dir("/my/project", "test-feature")

        assert Path(result).exists()
        assert Path(result).is_dir()

    def test_returns_path_if_exists(self, tmp_path, monkeypatch):
        from spellbook_mcp.forged.artifacts import ensure_artifact_dir

        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        # Call twice - should work both times
        result1 = ensure_artifact_dir("/my/project", "test-feature")
        result2 = ensure_artifact_dir("/my/project", "test-feature")

        assert result1 == result2
        assert Path(result1).exists()

    def test_includes_forged_and_feature_in_path(self, tmp_path, monkeypatch):
        from spellbook_mcp.forged.artifacts import ensure_artifact_dir

        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        result = ensure_artifact_dir("/my/project", "awesome-feature")

        assert "forged" in result
        assert "awesome-feature" in result


class TestValidArtifactTypes:
    """Tests for artifact type validation."""

    def test_valid_types_constant_exists(self):
        from spellbook_mcp.forged.artifacts import VALID_ARTIFACT_TYPES

        assert isinstance(VALID_ARTIFACT_TYPES, list)
        assert len(VALID_ARTIFACT_TYPES) == 6

    def test_all_expected_types_present(self):
        from spellbook_mcp.forged.artifacts import VALID_ARTIFACT_TYPES

        expected = ["requirement", "design", "plan", "reflection", "checkpoint", "progress"]
        for t in expected:
            assert t in VALID_ARTIFACT_TYPES
