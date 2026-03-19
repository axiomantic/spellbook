"""Project graph models for Forged autonomous development.

This module provides data structures for managing project features and their
dependencies, including topological sorting for dependency ordering and
skill invocation tracking for cross-skill context persistence.
"""

from dataclasses import dataclass, field
from typing import Optional


# Constants
VALID_FEATURE_STATUSES = ["pending", "in_progress", "complete", "blocked"]
VALID_COMPLEXITIES = ["trivial", "small", "medium", "large", "epic"]


class CyclicDependencyError(Exception):
    """Raised when a cyclic dependency is detected in the feature graph."""

    pass


class MissingDependencyError(Exception):
    """Raised when a feature depends on a non-existent feature."""

    pass


@dataclass
class FeatureNode:
    """A single feature in the project dependency graph.

    Represents a unit of work with dependencies on other features,
    status tracking, and artifact associations.

    Attributes:
        id: Unique identifier for the feature
        name: Human-readable feature name
        description: Detailed description of the feature
        depends_on: List of feature IDs this feature depends on
        status: Current status (pending, in_progress, complete, blocked)
        estimated_complexity: Complexity estimate (trivial, small, medium, large, epic)
        assigned_skill: Currently assigned skill for this feature
        artifacts: List of artifact paths produced for this feature
    """

    id: str
    name: str
    description: str
    depends_on: list[str]
    status: str
    estimated_complexity: str
    assigned_skill: Optional[str]
    artifacts: list[str]

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dictionary.

        Returns:
            Dictionary with all feature node fields
        """
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "depends_on": self.depends_on,
            "status": self.status,
            "estimated_complexity": self.estimated_complexity,
            "assigned_skill": self.assigned_skill,
            "artifacts": self.artifacts,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FeatureNode":
        """Reconstruct FeatureNode from dictionary.

        Args:
            data: Dictionary containing feature node fields

        Returns:
            Reconstructed FeatureNode instance
        """
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            depends_on=data["depends_on"],
            status=data["status"],
            estimated_complexity=data["estimated_complexity"],
            assigned_skill=data.get("assigned_skill"),
            artifacts=data.get("artifacts", []),
        )


@dataclass
class ProjectGraph:
    """Dependency graph for all features in a project.

    Manages the complete set of features, their dependency relationships,
    and tracking of project progress.

    Attributes:
        project_name: Human-readable project name
        features: Dictionary mapping feature ID to FeatureNode
        dependency_order: Topologically sorted list of feature IDs
        current_feature: ID of the currently active feature (if any)
        completed_features: List of completed feature IDs
    """

    project_name: str
    features: dict[str, FeatureNode]
    dependency_order: list[str]
    current_feature: Optional[str]
    completed_features: list[str]

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dictionary.

        Returns:
            Dictionary with all project graph fields, features nested as dicts
        """
        return {
            "project_name": self.project_name,
            "features": {
                fid: node.to_dict() for fid, node in self.features.items()
            },
            "dependency_order": self.dependency_order,
            "current_feature": self.current_feature,
            "completed_features": self.completed_features,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProjectGraph":
        """Reconstruct ProjectGraph from dictionary.

        Args:
            data: Dictionary containing project graph fields

        Returns:
            Reconstructed ProjectGraph instance
        """
        features = {
            fid: FeatureNode.from_dict(fdata)
            for fid, fdata in data.get("features", {}).items()
        }

        return cls(
            project_name=data["project_name"],
            features=features,
            dependency_order=data.get("dependency_order", []),
            current_feature=data.get("current_feature"),
            completed_features=data.get("completed_features", []),
        )


@dataclass
class SkillInvocation:
    """Record of a skill invocation for cross-skill context persistence.

    Tracks when skills are invoked, their results, and context passed
    between skills to enable coherent multi-skill workflows.

    Attributes:
        id: Unique identifier for this invocation
        feature_id: ID of the feature being worked on
        skill_name: Name of the invoked skill
        stage: Workflow stage when skill was invoked
        iteration: Iteration number within the feature development
        started_at: ISO timestamp when skill invocation started
        completed_at: ISO timestamp when skill invocation completed (if done)
        result: Result status (success, failure, etc.)
        context_passed: Context data passed to the skill
        context_returned: Context data returned by the skill
    """

    id: str
    feature_id: str
    skill_name: str
    stage: str
    iteration: int
    started_at: str
    completed_at: Optional[str]
    result: Optional[str]
    context_passed: dict = field(default_factory=dict)
    context_returned: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dictionary.

        Returns:
            Dictionary with all skill invocation fields
        """
        return {
            "id": self.id,
            "feature_id": self.feature_id,
            "skill_name": self.skill_name,
            "stage": self.stage,
            "iteration": self.iteration,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "context_passed": self.context_passed,
            "context_returned": self.context_returned,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SkillInvocation":
        """Reconstruct SkillInvocation from dictionary.

        Args:
            data: Dictionary containing skill invocation fields

        Returns:
            Reconstructed SkillInvocation instance
        """
        return cls(
            id=data["id"],
            feature_id=data["feature_id"],
            skill_name=data["skill_name"],
            stage=data["stage"],
            iteration=data["iteration"],
            started_at=data["started_at"],
            completed_at=data.get("completed_at"),
            result=data.get("result"),
            context_passed=data.get("context_passed", {}),
            context_returned=data.get("context_returned", {}),
        )


def compute_dependency_order(features: dict[str, FeatureNode]) -> list[str]:
    """Compute topological sort of features based on dependencies.

    Uses Kahn's algorithm to produce a valid execution order where
    all dependencies are satisfied before dependent features.

    Args:
        features: Dictionary mapping feature ID to FeatureNode

    Returns:
        List of feature IDs in dependency order (dependencies first)

    Raises:
        CyclicDependencyError: If features contain circular dependencies
        MissingDependencyError: If a feature depends on non-existent feature
    """
    if not features:
        return []

    # Validate all dependencies exist
    all_ids = set(features.keys())
    for fid, node in features.items():
        for dep in node.depends_on:
            if dep not in all_ids:
                raise MissingDependencyError(
                    f"Feature '{fid}' depends on non-existent feature '{dep}'"
                )

    # Build in-degree map and adjacency list
    in_degree: dict[str, int] = {fid: 0 for fid in features}
    dependents: dict[str, list[str]] = {fid: [] for fid in features}

    for fid, node in features.items():
        in_degree[fid] = len(node.depends_on)
        for dep in node.depends_on:
            dependents[dep].append(fid)

    # Start with nodes that have no dependencies (in_degree = 0)
    queue = [fid for fid, degree in in_degree.items() if degree == 0]
    result: list[str] = []

    while queue:
        # Sort queue to ensure deterministic output
        queue.sort()
        current = queue.pop(0)
        result.append(current)

        # Reduce in-degree for all dependents
        for dependent in dependents[current]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    # If we didn't process all nodes, there's a cycle
    if len(result) != len(features):
        # Find nodes still with dependencies (part of cycle)
        remaining = [fid for fid in features if fid not in result]
        raise CyclicDependencyError(
            f"Cyclic dependency detected involving features: {remaining}"
        )

    return result
