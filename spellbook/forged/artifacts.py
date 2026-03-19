"""Artifact path generation and storage operations for Forged.

This module provides standardized paths for storing development artifacts
(requirements, designs, plans, reflections, checkpoints, progress) in
the spellbook docs directory structure.

Artifact Structure:
    ~/.local/spellbook/docs/{project-encoded}/forged/{feature}/
        requirements.md
        design.md
        implementation-plan.md
        progress.json
        reflections/
            reflection-{iteration}.md
        checkpoints/
            checkpoint-{iteration}.json
"""

import os
from pathlib import Path
from typing import Optional

# Valid artifact types
VALID_ARTIFACT_TYPES = [
    "requirement",
    "design",
    "plan",
    "reflection",
    "checkpoint",
    "progress",
]

# Artifact types that require iteration numbers
_ITERATION_REQUIRED_TYPES = {"reflection", "checkpoint"}

# Mapping from artifact type to filename/pattern
_ARTIFACT_FILENAMES = {
    "requirement": "requirements.md",
    "design": "design.md",
    "plan": "implementation-plan.md",
    "progress": "progress.json",
}

# Mapping for iteration-based artifacts (subdirectory, pattern)
_ARTIFACT_PATTERNS = {
    "reflection": ("reflections", "reflection-{iteration}.md"),
    "checkpoint": ("checkpoints", "checkpoint-{iteration}.json"),
}


def get_project_encoded(project_path: str) -> str:
    """Encode project path for use in artifact paths.

    Removes leading slash and replaces all remaining slashes with dashes.

    Args:
        project_path: Absolute path to project directory

    Returns:
        Encoded string suitable for use in directory names

    Examples:
        >>> get_project_encoded("/Users/alice/project")
        'Users-alice-project'
        >>> get_project_encoded("/home/user/dev/myproject")
        'home-user-dev-myproject'
    """
    return project_path.lstrip("/").replace("/", "-")


def artifact_base_path(project_path: str, feature_name: str) -> str:
    """Get base path for feature artifacts.

    Args:
        project_path: Absolute path to project directory
        feature_name: Name of the feature being developed

    Returns:
        Absolute path to the feature's artifact directory

    Example:
        >>> artifact_base_path("/Users/alice/project", "my-feature")
        '/Users/alice/.local/spellbook/docs/Users-alice-project/forged/my-feature'
    """
    project_encoded = get_project_encoded(project_path)
    return os.path.expanduser(
        f"~/.local/spellbook/docs/{project_encoded}/forged/{feature_name}"
    )


def artifact_path(
    project_path: str,
    feature_name: str,
    artifact_type: str,
    iteration: Optional[int] = None,
) -> str:
    """Generate standard path for artifacts.

    Args:
        project_path: Absolute path to project directory
        feature_name: Name of the feature being developed
        artifact_type: Type of artifact ("requirement", "design", "plan",
                      "reflection", "checkpoint", "progress")
        iteration: Iteration number (required for reflection and checkpoint)

    Returns:
        Absolute path to the artifact file

    Raises:
        ValueError: If artifact_type is invalid or iteration is required but missing

    Examples:
        >>> artifact_path("/path", "feature", "requirement")
        '...forged/feature/requirements.md'
        >>> artifact_path("/path", "feature", "reflection", iteration=3)
        '...forged/feature/reflections/reflection-3.md'
    """
    if artifact_type not in VALID_ARTIFACT_TYPES:
        raise ValueError(
            f"Invalid artifact type: {artifact_type}. "
            f"Must be one of: {VALID_ARTIFACT_TYPES}"
        )

    if artifact_type in _ITERATION_REQUIRED_TYPES and iteration is None:
        raise ValueError(
            f"Artifact type '{artifact_type}' requires an iteration number"
        )

    base = artifact_base_path(project_path, feature_name)

    # Simple artifacts (no iteration)
    if artifact_type in _ARTIFACT_FILENAMES:
        return os.path.join(base, _ARTIFACT_FILENAMES[artifact_type])

    # Iteration-based artifacts
    subdir, pattern = _ARTIFACT_PATTERNS[artifact_type]
    filename = pattern.format(iteration=iteration)
    return os.path.join(base, subdir, filename)


def write_artifact(path: str, content: str) -> bool:
    """Write content to artifact path.

    Creates parent directories if needed.

    Args:
        path: Absolute path to the artifact file
        content: Content to write

    Returns:
        True on success
    """
    artifact_path_obj = Path(path)
    artifact_path_obj.parent.mkdir(parents=True, exist_ok=True)
    artifact_path_obj.write_text(content, encoding="utf-8")
    return True


def read_artifact(path: str) -> Optional[str]:
    """Read content from artifact path.

    Args:
        path: Absolute path to the artifact file

    Returns:
        File content as string, or None if file doesn't exist
    """
    artifact_path_obj = Path(path)
    if not artifact_path_obj.exists():
        return None
    return artifact_path_obj.read_text(encoding="utf-8")


def list_artifacts(
    feature_path: str, artifact_type: Optional[str] = None
) -> list[str]:
    """List artifact paths in feature directory.

    Args:
        feature_path: Path to the feature's artifact directory
        artifact_type: Optionally filter by artifact type

    Returns:
        List of absolute paths to artifact files
    """
    feature_dir = Path(feature_path)
    if not feature_dir.exists():
        return []

    results: list[str] = []

    if artifact_type is None:
        # List all files recursively
        for item in feature_dir.rglob("*"):
            if item.is_file():
                results.append(str(item))
    else:
        # Filter by artifact type
        if artifact_type in _ARTIFACT_FILENAMES:
            # Single file artifact
            target = feature_dir / _ARTIFACT_FILENAMES[artifact_type]
            if target.exists():
                results.append(str(target))
        elif artifact_type in _ARTIFACT_PATTERNS:
            # Iteration-based artifacts in subdirectory
            subdir, pattern = _ARTIFACT_PATTERNS[artifact_type]
            subdir_path = feature_dir / subdir
            if subdir_path.exists():
                # Extract the prefix from pattern (e.g., "reflection-" from "reflection-{iteration}.md")
                prefix = pattern.split("{")[0]
                for item in subdir_path.iterdir():
                    if item.is_file() and item.name.startswith(prefix):
                        results.append(str(item))

    return sorted(results)


def ensure_artifact_dir(project_path: str, feature_name: str) -> str:
    """Ensure artifact directory exists, create if needed.

    Args:
        project_path: Absolute path to project directory
        feature_name: Name of the feature being developed

    Returns:
        Absolute path to the created/existing directory
    """
    base = artifact_base_path(project_path, feature_name)
    dir_path = Path(base)
    dir_path.mkdir(parents=True, exist_ok=True)
    return str(dir_path)
