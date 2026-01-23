"""Tests for Forged project tools and models.

Following TDD: these tests are written BEFORE implementation.
"""

import json
import pytest
from pathlib import Path


# =============================================================================
# Task 4.1: FeatureNode and ProjectGraph Models
# =============================================================================


class TestFeatureNode:
    """Tests for FeatureNode dataclass."""

    def test_feature_node_creation_with_all_fields(self):
        """FeatureNode must be creatable with all fields."""
        from spellbook_mcp.forged.project_graph import FeatureNode

        node = FeatureNode(
            id="feat-001",
            name="User Authentication",
            description="Implement user login and registration",
            depends_on=["feat-000"],
            status="pending",
            estimated_complexity="medium",
            assigned_skill="implementing-features",
            artifacts=["/path/to/artifact.md"],
        )

        assert node.id == "feat-001"
        assert node.name == "User Authentication"
        assert node.description == "Implement user login and registration"
        assert node.depends_on == ["feat-000"]
        assert node.status == "pending"
        assert node.estimated_complexity == "medium"
        assert node.assigned_skill == "implementing-features"
        assert node.artifacts == ["/path/to/artifact.md"]

    def test_feature_node_with_no_dependencies(self):
        """FeatureNode must work with empty dependencies list."""
        from spellbook_mcp.forged.project_graph import FeatureNode

        node = FeatureNode(
            id="feat-root",
            name="Root Feature",
            description="No dependencies",
            depends_on=[],
            status="pending",
            estimated_complexity="trivial",
            assigned_skill=None,
            artifacts=[],
        )

        assert node.depends_on == []
        assert node.assigned_skill is None

    def test_feature_node_valid_statuses(self):
        """FeatureNode status must accept valid values."""
        from spellbook_mcp.forged.project_graph import FeatureNode, VALID_FEATURE_STATUSES

        for status in VALID_FEATURE_STATUSES:
            node = FeatureNode(
                id="test",
                name="Test",
                description="Test",
                depends_on=[],
                status=status,
                estimated_complexity="trivial",
                assigned_skill=None,
                artifacts=[],
            )
            assert node.status == status

    def test_feature_node_valid_complexities(self):
        """FeatureNode complexity must accept valid values."""
        from spellbook_mcp.forged.project_graph import FeatureNode, VALID_COMPLEXITIES

        for complexity in VALID_COMPLEXITIES:
            node = FeatureNode(
                id="test",
                name="Test",
                description="Test",
                depends_on=[],
                status="pending",
                estimated_complexity=complexity,
                assigned_skill=None,
                artifacts=[],
            )
            assert node.estimated_complexity == complexity

    def test_feature_node_to_dict(self):
        """FeatureNode.to_dict() must produce JSON-serializable dict."""
        from spellbook_mcp.forged.project_graph import FeatureNode

        node = FeatureNode(
            id="feat-001",
            name="Test Feature",
            description="Test description",
            depends_on=["feat-000"],
            status="in_progress",
            estimated_complexity="large",
            assigned_skill="test-driven-development",
            artifacts=["/path/a.md", "/path/b.md"],
        )

        d = node.to_dict()

        # Must be JSON-serializable
        json_str = json.dumps(d)
        assert json_str is not None

        # Must have all fields
        assert d["id"] == "feat-001"
        assert d["name"] == "Test Feature"
        assert d["description"] == "Test description"
        assert d["depends_on"] == ["feat-000"]
        assert d["status"] == "in_progress"
        assert d["estimated_complexity"] == "large"
        assert d["assigned_skill"] == "test-driven-development"
        assert d["artifacts"] == ["/path/a.md", "/path/b.md"]

    def test_feature_node_from_dict(self):
        """FeatureNode.from_dict() must reconstruct from dict."""
        from spellbook_mcp.forged.project_graph import FeatureNode

        data = {
            "id": "feat-002",
            "name": "From Dict Feature",
            "description": "Created from dict",
            "depends_on": ["feat-001", "feat-000"],
            "status": "complete",
            "estimated_complexity": "epic",
            "assigned_skill": "debugging",
            "artifacts": ["/artifact.json"],
        }

        node = FeatureNode.from_dict(data)

        assert node.id == "feat-002"
        assert node.name == "From Dict Feature"
        assert node.depends_on == ["feat-001", "feat-000"]
        assert node.status == "complete"
        assert node.estimated_complexity == "epic"
        assert node.assigned_skill == "debugging"

    def test_feature_node_from_dict_with_none_skill(self):
        """FeatureNode.from_dict() must handle None assigned_skill."""
        from spellbook_mcp.forged.project_graph import FeatureNode

        data = {
            "id": "feat-003",
            "name": "No Skill Feature",
            "description": "No skill assigned",
            "depends_on": [],
            "status": "pending",
            "estimated_complexity": "small",
            "assigned_skill": None,
            "artifacts": [],
        }

        node = FeatureNode.from_dict(data)

        assert node.assigned_skill is None

    def test_feature_node_roundtrip(self):
        """FeatureNode must survive to_dict() -> from_dict() roundtrip."""
        from spellbook_mcp.forged.project_graph import FeatureNode

        original = FeatureNode(
            id="roundtrip-feat",
            name="Roundtrip Test",
            description="Testing roundtrip serialization",
            depends_on=["dep-1", "dep-2", "dep-3"],
            status="blocked",
            estimated_complexity="medium",
            assigned_skill="implementing-features",
            artifacts=["/path/one.md", "/path/two.md"],
        )

        reconstructed = FeatureNode.from_dict(original.to_dict())

        assert reconstructed.id == original.id
        assert reconstructed.name == original.name
        assert reconstructed.description == original.description
        assert reconstructed.depends_on == original.depends_on
        assert reconstructed.status == original.status
        assert reconstructed.estimated_complexity == original.estimated_complexity
        assert reconstructed.assigned_skill == original.assigned_skill
        assert reconstructed.artifacts == original.artifacts


class TestProjectGraph:
    """Tests for ProjectGraph dataclass."""

    def test_project_graph_creation(self):
        """ProjectGraph must be creatable with required fields."""
        from spellbook_mcp.forged.project_graph import ProjectGraph, FeatureNode

        node1 = FeatureNode(
            id="feat-1",
            name="Feature One",
            description="First feature",
            depends_on=[],
            status="pending",
            estimated_complexity="small",
            assigned_skill=None,
            artifacts=[],
        )
        node2 = FeatureNode(
            id="feat-2",
            name="Feature Two",
            description="Second feature",
            depends_on=["feat-1"],
            status="pending",
            estimated_complexity="medium",
            assigned_skill=None,
            artifacts=[],
        )

        graph = ProjectGraph(
            project_name="Test Project",
            features={"feat-1": node1, "feat-2": node2},
            dependency_order=["feat-1", "feat-2"],
            current_feature=None,
            completed_features=[],
        )

        assert graph.project_name == "Test Project"
        assert len(graph.features) == 2
        assert graph.dependency_order == ["feat-1", "feat-2"]
        assert graph.current_feature is None
        assert graph.completed_features == []

    def test_project_graph_empty_features(self):
        """ProjectGraph must work with no features."""
        from spellbook_mcp.forged.project_graph import ProjectGraph

        graph = ProjectGraph(
            project_name="Empty Project",
            features={},
            dependency_order=[],
            current_feature=None,
            completed_features=[],
        )

        assert graph.features == {}
        assert graph.dependency_order == []

    def test_project_graph_with_current_feature(self):
        """ProjectGraph must track current feature."""
        from spellbook_mcp.forged.project_graph import ProjectGraph, FeatureNode

        node = FeatureNode(
            id="current-feat",
            name="Current",
            description="Current feature",
            depends_on=[],
            status="in_progress",
            estimated_complexity="trivial",
            assigned_skill="implementing-features",
            artifacts=[],
        )

        graph = ProjectGraph(
            project_name="Current Test",
            features={"current-feat": node},
            dependency_order=["current-feat"],
            current_feature="current-feat",
            completed_features=[],
        )

        assert graph.current_feature == "current-feat"

    def test_project_graph_with_completed_features(self):
        """ProjectGraph must track completed features."""
        from spellbook_mcp.forged.project_graph import ProjectGraph, FeatureNode

        node1 = FeatureNode(
            id="done-1",
            name="Done One",
            description="Completed",
            depends_on=[],
            status="complete",
            estimated_complexity="trivial",
            assigned_skill=None,
            artifacts=[],
        )
        node2 = FeatureNode(
            id="done-2",
            name="Done Two",
            description="Also completed",
            depends_on=["done-1"],
            status="complete",
            estimated_complexity="small",
            assigned_skill=None,
            artifacts=[],
        )
        node3 = FeatureNode(
            id="pending-1",
            name="Pending",
            description="Not done yet",
            depends_on=["done-2"],
            status="pending",
            estimated_complexity="medium",
            assigned_skill=None,
            artifacts=[],
        )

        graph = ProjectGraph(
            project_name="Completed Test",
            features={"done-1": node1, "done-2": node2, "pending-1": node3},
            dependency_order=["done-1", "done-2", "pending-1"],
            current_feature="pending-1",
            completed_features=["done-1", "done-2"],
        )

        assert len(graph.completed_features) == 2
        assert "done-1" in graph.completed_features
        assert "done-2" in graph.completed_features

    def test_project_graph_to_dict(self):
        """ProjectGraph.to_dict() must produce JSON-serializable dict."""
        from spellbook_mcp.forged.project_graph import ProjectGraph, FeatureNode

        node = FeatureNode(
            id="feat-a",
            name="Feature A",
            description="Test feature",
            depends_on=[],
            status="pending",
            estimated_complexity="small",
            assigned_skill="brainstorming",
            artifacts=["/artifact.md"],
        )

        graph = ProjectGraph(
            project_name="Dict Test Project",
            features={"feat-a": node},
            dependency_order=["feat-a"],
            current_feature="feat-a",
            completed_features=[],
        )

        d = graph.to_dict()

        # Must be JSON-serializable
        json_str = json.dumps(d)
        assert json_str is not None

        # Must have all fields
        assert d["project_name"] == "Dict Test Project"
        assert "feat-a" in d["features"]
        assert d["features"]["feat-a"]["name"] == "Feature A"
        assert d["dependency_order"] == ["feat-a"]
        assert d["current_feature"] == "feat-a"
        assert d["completed_features"] == []

    def test_project_graph_from_dict(self):
        """ProjectGraph.from_dict() must reconstruct from dict."""
        from spellbook_mcp.forged.project_graph import ProjectGraph

        data = {
            "project_name": "From Dict Project",
            "features": {
                "f1": {
                    "id": "f1",
                    "name": "Feature 1",
                    "description": "First",
                    "depends_on": [],
                    "status": "complete",
                    "estimated_complexity": "trivial",
                    "assigned_skill": None,
                    "artifacts": [],
                },
                "f2": {
                    "id": "f2",
                    "name": "Feature 2",
                    "description": "Second",
                    "depends_on": ["f1"],
                    "status": "in_progress",
                    "estimated_complexity": "medium",
                    "assigned_skill": "implementing-features",
                    "artifacts": ["/path.md"],
                },
            },
            "dependency_order": ["f1", "f2"],
            "current_feature": "f2",
            "completed_features": ["f1"],
        }

        graph = ProjectGraph.from_dict(data)

        assert graph.project_name == "From Dict Project"
        assert len(graph.features) == 2
        assert graph.features["f1"].status == "complete"
        assert graph.features["f2"].assigned_skill == "implementing-features"
        assert graph.dependency_order == ["f1", "f2"]
        assert graph.current_feature == "f2"
        assert graph.completed_features == ["f1"]

    def test_project_graph_roundtrip(self):
        """ProjectGraph must survive to_dict() -> from_dict() roundtrip."""
        from spellbook_mcp.forged.project_graph import ProjectGraph, FeatureNode

        node1 = FeatureNode(
            id="rt-1",
            name="Roundtrip 1",
            description="First roundtrip feature",
            depends_on=[],
            status="complete",
            estimated_complexity="small",
            assigned_skill=None,
            artifacts=["/done.md"],
        )
        node2 = FeatureNode(
            id="rt-2",
            name="Roundtrip 2",
            description="Second roundtrip feature",
            depends_on=["rt-1"],
            status="in_progress",
            estimated_complexity="large",
            assigned_skill="test-driven-development",
            artifacts=["/wip.md"],
        )

        original = ProjectGraph(
            project_name="Roundtrip Project",
            features={"rt-1": node1, "rt-2": node2},
            dependency_order=["rt-1", "rt-2"],
            current_feature="rt-2",
            completed_features=["rt-1"],
        )

        reconstructed = ProjectGraph.from_dict(original.to_dict())

        assert reconstructed.project_name == original.project_name
        assert len(reconstructed.features) == len(original.features)
        assert reconstructed.features["rt-1"].name == original.features["rt-1"].name
        assert reconstructed.features["rt-2"].assigned_skill == original.features["rt-2"].assigned_skill
        assert reconstructed.dependency_order == original.dependency_order
        assert reconstructed.current_feature == original.current_feature
        assert reconstructed.completed_features == original.completed_features


class TestTopologicalSort:
    """Tests for topological sort of project features."""

    def test_topological_sort_single_feature(self):
        """Single feature should return that feature."""
        from spellbook_mcp.forged.project_graph import compute_dependency_order, FeatureNode

        features = {
            "solo": FeatureNode(
                id="solo",
                name="Solo",
                description="Alone",
                depends_on=[],
                status="pending",
                estimated_complexity="trivial",
                assigned_skill=None,
                artifacts=[],
            )
        }

        order = compute_dependency_order(features)
        assert order == ["solo"]

    def test_topological_sort_linear_chain(self):
        """Linear dependency chain should be sorted correctly."""
        from spellbook_mcp.forged.project_graph import compute_dependency_order, FeatureNode

        features = {
            "a": FeatureNode(
                id="a", name="A", description="First", depends_on=[],
                status="pending", estimated_complexity="trivial", assigned_skill=None, artifacts=[],
            ),
            "b": FeatureNode(
                id="b", name="B", description="Second", depends_on=["a"],
                status="pending", estimated_complexity="trivial", assigned_skill=None, artifacts=[],
            ),
            "c": FeatureNode(
                id="c", name="C", description="Third", depends_on=["b"],
                status="pending", estimated_complexity="trivial", assigned_skill=None, artifacts=[],
            ),
        }

        order = compute_dependency_order(features)

        # a must come before b, b must come before c
        assert order.index("a") < order.index("b")
        assert order.index("b") < order.index("c")

    def test_topological_sort_diamond_dependency(self):
        """Diamond dependency pattern should be sorted correctly."""
        from spellbook_mcp.forged.project_graph import compute_dependency_order, FeatureNode

        #     a
        #    / \
        #   b   c
        #    \ /
        #     d
        features = {
            "a": FeatureNode(
                id="a", name="A", description="Root", depends_on=[],
                status="pending", estimated_complexity="trivial", assigned_skill=None, artifacts=[],
            ),
            "b": FeatureNode(
                id="b", name="B", description="Left", depends_on=["a"],
                status="pending", estimated_complexity="trivial", assigned_skill=None, artifacts=[],
            ),
            "c": FeatureNode(
                id="c", name="C", description="Right", depends_on=["a"],
                status="pending", estimated_complexity="trivial", assigned_skill=None, artifacts=[],
            ),
            "d": FeatureNode(
                id="d", name="D", description="Bottom", depends_on=["b", "c"],
                status="pending", estimated_complexity="trivial", assigned_skill=None, artifacts=[],
            ),
        }

        order = compute_dependency_order(features)

        # a must come first
        assert order.index("a") < order.index("b")
        assert order.index("a") < order.index("c")
        # d must come last
        assert order.index("b") < order.index("d")
        assert order.index("c") < order.index("d")

    def test_topological_sort_multiple_roots(self):
        """Multiple independent roots should all be included."""
        from spellbook_mcp.forged.project_graph import compute_dependency_order, FeatureNode

        features = {
            "root1": FeatureNode(
                id="root1", name="Root 1", description="First root", depends_on=[],
                status="pending", estimated_complexity="trivial", assigned_skill=None, artifacts=[],
            ),
            "root2": FeatureNode(
                id="root2", name="Root 2", description="Second root", depends_on=[],
                status="pending", estimated_complexity="trivial", assigned_skill=None, artifacts=[],
            ),
            "child": FeatureNode(
                id="child", name="Child", description="Depends on both", depends_on=["root1", "root2"],
                status="pending", estimated_complexity="trivial", assigned_skill=None, artifacts=[],
            ),
        }

        order = compute_dependency_order(features)

        assert len(order) == 3
        assert order.index("root1") < order.index("child")
        assert order.index("root2") < order.index("child")

    def test_topological_sort_detects_cycle(self):
        """Cycle in dependencies should raise error."""
        from spellbook_mcp.forged.project_graph import compute_dependency_order, FeatureNode, CyclicDependencyError

        features = {
            "a": FeatureNode(
                id="a", name="A", description="Cycle start", depends_on=["c"],
                status="pending", estimated_complexity="trivial", assigned_skill=None, artifacts=[],
            ),
            "b": FeatureNode(
                id="b", name="B", description="Cycle middle", depends_on=["a"],
                status="pending", estimated_complexity="trivial", assigned_skill=None, artifacts=[],
            ),
            "c": FeatureNode(
                id="c", name="C", description="Cycle end", depends_on=["b"],
                status="pending", estimated_complexity="trivial", assigned_skill=None, artifacts=[],
            ),
        }

        with pytest.raises(CyclicDependencyError):
            compute_dependency_order(features)

    def test_topological_sort_empty_features(self):
        """Empty features dict should return empty list."""
        from spellbook_mcp.forged.project_graph import compute_dependency_order

        order = compute_dependency_order({})
        assert order == []

    def test_topological_sort_missing_dependency(self):
        """Missing dependency should raise error."""
        from spellbook_mcp.forged.project_graph import compute_dependency_order, FeatureNode, MissingDependencyError

        features = {
            "a": FeatureNode(
                id="a", name="A", description="Has missing dep", depends_on=["nonexistent"],
                status="pending", estimated_complexity="trivial", assigned_skill=None, artifacts=[],
            ),
        }

        with pytest.raises(MissingDependencyError):
            compute_dependency_order(features)


class TestFeatureNodeConstants:
    """Tests for FeatureNode-related constants."""

    def test_valid_feature_statuses_defined(self):
        """VALID_FEATURE_STATUSES must contain all valid statuses."""
        from spellbook_mcp.forged.project_graph import VALID_FEATURE_STATUSES

        expected = ["pending", "in_progress", "complete", "blocked"]
        assert VALID_FEATURE_STATUSES == expected

    def test_valid_complexities_defined(self):
        """VALID_COMPLEXITIES must contain all complexity levels."""
        from spellbook_mcp.forged.project_graph import VALID_COMPLEXITIES

        expected = ["trivial", "small", "medium", "large", "epic"]
        assert VALID_COMPLEXITIES == expected


# =============================================================================
# Task 4.2: Skill Selection Algorithm
# =============================================================================


class TestSkillSelection:
    """Tests for skill selection algorithm."""

    def test_select_skill_for_discover_stage(self):
        """DISCOVER stage should default to gathering-requirements skill."""
        from spellbook_mcp.forged.skill_selection import select_skill
        from spellbook_mcp.forged.models import IterationState

        context = IterationState(
            iteration_number=1,
            current_stage="DISCOVER",
            feedback_history=[],
        )

        skill = select_skill(context)
        assert skill == "gathering-requirements"

    def test_select_skill_for_design_stage(self):
        """DESIGN stage should default to brainstorming skill."""
        from spellbook_mcp.forged.skill_selection import select_skill
        from spellbook_mcp.forged.models import IterationState

        context = IterationState(
            iteration_number=1,
            current_stage="DESIGN",
            feedback_history=[],
        )

        skill = select_skill(context)
        assert skill == "brainstorming"

    def test_select_skill_for_plan_stage(self):
        """PLAN stage should default to writing-plans skill."""
        from spellbook_mcp.forged.skill_selection import select_skill
        from spellbook_mcp.forged.models import IterationState

        context = IterationState(
            iteration_number=1,
            current_stage="PLAN",
            feedback_history=[],
        )

        skill = select_skill(context)
        assert skill == "writing-plans"

    def test_select_skill_for_implement_stage(self):
        """IMPLEMENT stage should default to implementing-features skill."""
        from spellbook_mcp.forged.skill_selection import select_skill
        from spellbook_mcp.forged.models import IterationState

        context = IterationState(
            iteration_number=1,
            current_stage="IMPLEMENT",
            feedback_history=[],
        )

        skill = select_skill(context)
        assert skill == "implementing-features"

    def test_select_skill_with_test_error_feedback(self):
        """Test errors should trigger fixing-tests skill."""
        from spellbook_mcp.forged.skill_selection import select_skill
        from spellbook_mcp.forged.models import IterationState, Feedback

        feedback = Feedback(
            source="test-validator",
            stage="IMPLEMENT",
            return_to="IMPLEMENT",
            critique="Tests failing",
            evidence="3 tests failed in test_auth.py",
            suggestion="Fix the failing tests",
            severity="blocking",
            iteration=1,
        )

        context = IterationState(
            iteration_number=2,
            current_stage="IMPLEMENT",
            feedback_history=[feedback],
        )

        skill = select_skill(context)
        assert skill == "fixing-tests"

    def test_select_skill_with_merge_error_feedback(self):
        """Merge conflicts should trigger resolving-merge-conflicts skill."""
        from spellbook_mcp.forged.skill_selection import select_skill
        from spellbook_mcp.forged.models import IterationState, Feedback

        feedback = Feedback(
            source="git-validator",
            stage="IMPLEMENT",
            return_to="IMPLEMENT",
            critique="Merge conflict detected",
            evidence="Conflict in src/auth.py",
            suggestion="Resolve merge conflicts",
            severity="blocking",
            iteration=1,
        )

        context = IterationState(
            iteration_number=2,
            current_stage="IMPLEMENT",
            feedback_history=[feedback],
        )

        skill = select_skill(context)
        assert skill == "resolving-merge-conflicts"

    def test_select_skill_with_code_quality_feedback(self):
        """Code quality feedback should trigger receiving-code-review skill."""
        from spellbook_mcp.forged.skill_selection import select_skill
        from spellbook_mcp.forged.models import IterationState, Feedback

        feedback = Feedback(
            source="lint-validator",
            stage="IMPLEMENT",
            return_to="IMPLEMENT",
            critique="Code style issues",
            evidence="Line too long, missing docstring",
            suggestion="Fix linting issues",
            severity="significant",
            iteration=1,
        )

        context = IterationState(
            iteration_number=2,
            current_stage="IMPLEMENT",
            feedback_history=[feedback],
        )

        skill = select_skill(context)
        assert skill == "receiving-code-review"

    def test_select_skill_with_factual_accuracy_feedback(self):
        """Factual accuracy feedback should trigger fact-checking skill."""
        from spellbook_mcp.forged.skill_selection import select_skill
        from spellbook_mcp.forged.models import IterationState, Feedback

        feedback = Feedback(
            source="accuracy-validator",
            stage="DESIGN",
            return_to="DISCOVER",
            critique="Incorrect assumption about API",
            evidence="The API does not support batch operations",
            suggestion="Verify API capabilities",
            severity="blocking",
            iteration=1,
        )

        context = IterationState(
            iteration_number=2,
            current_stage="DESIGN",
            feedback_history=[feedback],
        )

        skill = select_skill(context)
        assert skill == "fact-checking"

    def test_select_skill_prioritizes_errors_over_stage_default(self):
        """Error feedback should take priority over stage default."""
        from spellbook_mcp.forged.skill_selection import select_skill
        from spellbook_mcp.forged.models import IterationState, Feedback

        # Even in DESIGN stage, test errors should trigger fixing-tests
        feedback = Feedback(
            source="test-validator",
            stage="IMPLEMENT",
            return_to="IMPLEMENT",
            critique="Tests failing",
            evidence="test_module.py::test_func FAILED",
            suggestion="Fix tests",
            severity="blocking",
            iteration=1,
        )

        context = IterationState(
            iteration_number=2,
            current_stage="DESIGN",
            feedback_history=[feedback],
        )

        skill = select_skill(context)
        assert skill == "fixing-tests"


class TestClassifyFeedback:
    """Tests for feedback classification."""

    def test_classify_test_failure_feedback(self):
        """Test failure feedback should be classified as test_failure."""
        from spellbook_mcp.forged.skill_selection import classify_feedback
        from spellbook_mcp.forged.models import Feedback

        feedback = Feedback(
            source="test-validator",
            stage="IMPLEMENT",
            return_to="IMPLEMENT",
            critique="Tests failing",
            evidence="3 tests failed",
            suggestion="Fix tests",
            severity="blocking",
            iteration=1,
        )

        classification = classify_feedback([feedback])
        assert classification == "test_failure"

    def test_classify_merge_conflict_feedback(self):
        """Merge conflict feedback should be classified as merge_conflict."""
        from spellbook_mcp.forged.skill_selection import classify_feedback
        from spellbook_mcp.forged.models import Feedback

        feedback = Feedback(
            source="git-validator",
            stage="IMPLEMENT",
            return_to="IMPLEMENT",
            critique="Merge conflict",
            evidence="Conflict markers in file",
            suggestion="Resolve conflicts",
            severity="blocking",
            iteration=1,
        )

        classification = classify_feedback([feedback])
        assert classification == "merge_conflict"

    def test_classify_code_quality_feedback(self):
        """Lint/style feedback should be classified as code_quality."""
        from spellbook_mcp.forged.skill_selection import classify_feedback
        from spellbook_mcp.forged.models import Feedback

        feedback = Feedback(
            source="lint-validator",
            stage="IMPLEMENT",
            return_to="IMPLEMENT",
            critique="Style issues",
            evidence="Missing type hints",
            suggestion="Add types",
            severity="minor",
            iteration=1,
        )

        classification = classify_feedback([feedback])
        assert classification == "code_quality"

    def test_classify_factual_accuracy_feedback(self):
        """Factual accuracy feedback should be classified as factual_accuracy."""
        from spellbook_mcp.forged.skill_selection import classify_feedback
        from spellbook_mcp.forged.models import Feedback

        feedback = Feedback(
            source="accuracy-validator",
            stage="DESIGN",
            return_to="DISCOVER",
            critique="Incorrect assumption",
            evidence="API works differently",
            suggestion="Verify facts",
            severity="blocking",
            iteration=1,
        )

        classification = classify_feedback([feedback])
        assert classification == "factual_accuracy"

    def test_classify_empty_feedback_list(self):
        """Empty feedback list should return None."""
        from spellbook_mcp.forged.skill_selection import classify_feedback

        classification = classify_feedback([])
        assert classification is None

    def test_classify_prioritizes_blocking_feedback(self):
        """Blocking feedback should take priority over minor."""
        from spellbook_mcp.forged.skill_selection import classify_feedback
        from spellbook_mcp.forged.models import Feedback

        minor_feedback = Feedback(
            source="lint-validator",
            stage="IMPLEMENT",
            return_to="IMPLEMENT",
            critique="Style issue",
            evidence="Line too long",
            suggestion="Shorten line",
            severity="minor",
            iteration=1,
        )
        blocking_feedback = Feedback(
            source="test-validator",
            stage="IMPLEMENT",
            return_to="IMPLEMENT",
            critique="Tests failing",
            evidence="Critical test failed",
            suggestion="Fix test",
            severity="blocking",
            iteration=1,
        )

        # Blocking should win even if minor comes first
        classification = classify_feedback([minor_feedback, blocking_feedback])
        assert classification == "test_failure"


# =============================================================================
# Task 4.8: SkillInvocation Model
# =============================================================================


class TestSkillInvocation:
    """Tests for SkillInvocation model for cross-skill context persistence."""

    def test_skill_invocation_creation(self):
        """SkillInvocation must be creatable with required fields."""
        from spellbook_mcp.forged.project_graph import SkillInvocation

        invocation = SkillInvocation(
            id="inv-001",
            feature_id="feat-001",
            skill_name="implementing-features",
            stage="IMPLEMENT",
            iteration=1,
            started_at="2025-01-22T10:00:00",
            completed_at=None,
            result=None,
            context_passed={},
            context_returned={},
        )

        assert invocation.id == "inv-001"
        assert invocation.feature_id == "feat-001"
        assert invocation.skill_name == "implementing-features"
        assert invocation.stage == "IMPLEMENT"
        assert invocation.iteration == 1
        assert invocation.completed_at is None
        assert invocation.result is None

    def test_skill_invocation_with_completed_state(self):
        """SkillInvocation must handle completed state."""
        from spellbook_mcp.forged.project_graph import SkillInvocation

        invocation = SkillInvocation(
            id="inv-002",
            feature_id="feat-001",
            skill_name="brainstorming",
            stage="DESIGN",
            iteration=1,
            started_at="2025-01-22T10:00:00",
            completed_at="2025-01-22T10:30:00",
            result="success",
            context_passed={"requirement": "Build auth system"},
            context_returned={"design_options": ["OAuth", "JWT", "Session"]},
        )

        assert invocation.completed_at == "2025-01-22T10:30:00"
        assert invocation.result == "success"
        assert invocation.context_returned["design_options"] == ["OAuth", "JWT", "Session"]

    def test_skill_invocation_to_dict(self):
        """SkillInvocation.to_dict() must produce JSON-serializable dict."""
        from spellbook_mcp.forged.project_graph import SkillInvocation

        invocation = SkillInvocation(
            id="inv-003",
            feature_id="feat-002",
            skill_name="test-driven-development",
            stage="IMPLEMENT",
            iteration=2,
            started_at="2025-01-22T11:00:00",
            completed_at="2025-01-22T11:45:00",
            result="success",
            context_passed={"plan": "Write tests first"},
            context_returned={"tests_written": 5, "coverage": 0.85},
        )

        d = invocation.to_dict()

        # Must be JSON-serializable
        json_str = json.dumps(d)
        assert json_str is not None

        assert d["id"] == "inv-003"
        assert d["skill_name"] == "test-driven-development"
        assert d["context_returned"]["tests_written"] == 5

    def test_skill_invocation_from_dict(self):
        """SkillInvocation.from_dict() must reconstruct from dict."""
        from spellbook_mcp.forged.project_graph import SkillInvocation

        data = {
            "id": "inv-004",
            "feature_id": "feat-003",
            "skill_name": "debugging",
            "stage": "IMPLEMENT",
            "iteration": 3,
            "started_at": "2025-01-22T12:00:00",
            "completed_at": "2025-01-22T13:00:00",
            "result": "success",
            "context_passed": {"error": "NullPointerException"},
            "context_returned": {"root_cause": "Uninitialized variable"},
        }

        invocation = SkillInvocation.from_dict(data)

        assert invocation.id == "inv-004"
        assert invocation.skill_name == "debugging"
        assert invocation.context_returned["root_cause"] == "Uninitialized variable"

    def test_skill_invocation_roundtrip(self):
        """SkillInvocation must survive to_dict() -> from_dict() roundtrip."""
        from spellbook_mcp.forged.project_graph import SkillInvocation

        original = SkillInvocation(
            id="inv-rt",
            feature_id="feat-rt",
            skill_name="writing-plans",
            stage="PLAN",
            iteration=1,
            started_at="2025-01-22T14:00:00",
            completed_at="2025-01-22T14:30:00",
            result="success",
            context_passed={"design": "Architecture document"},
            context_returned={"plan_path": "/path/to/plan.md"},
        )

        reconstructed = SkillInvocation.from_dict(original.to_dict())

        assert reconstructed.id == original.id
        assert reconstructed.feature_id == original.feature_id
        assert reconstructed.skill_name == original.skill_name
        assert reconstructed.stage == original.stage
        assert reconstructed.iteration == original.iteration
        assert reconstructed.started_at == original.started_at
        assert reconstructed.completed_at == original.completed_at
        assert reconstructed.result == original.result
        assert reconstructed.context_passed == original.context_passed
        assert reconstructed.context_returned == original.context_returned


# =============================================================================
# Task 4.3-4.7: MCP Tools (Project Tools)
# =============================================================================


class TestForgeProjectInit:
    """Tests for forge_project_init MCP tool."""

    def test_forge_project_init_creates_graph(self, tmp_path, monkeypatch):
        """forge_project_init must create a project graph."""
        from spellbook_mcp.forged.project_tools import forge_project_init

        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        project_path = str(tmp_path / "test-project")
        (tmp_path / "test-project").mkdir()

        features = [
            {
                "id": "feat-1",
                "name": "Feature 1",
                "description": "First feature",
                "depends_on": [],
                "estimated_complexity": "small",
            },
            {
                "id": "feat-2",
                "name": "Feature 2",
                "description": "Second feature",
                "depends_on": ["feat-1"],
                "estimated_complexity": "medium",
            },
        ]

        result = forge_project_init(
            project_path=project_path,
            project_name="Test Project",
            features=features,
        )

        assert result["success"] is True
        assert "graph" in result
        assert result["graph"]["project_name"] == "Test Project"
        assert len(result["graph"]["features"]) == 2
        assert result["graph"]["dependency_order"] == ["feat-1", "feat-2"]

    def test_forge_project_init_validates_dependencies(self, tmp_path, monkeypatch):
        """forge_project_init must validate feature dependencies exist."""
        from spellbook_mcp.forged.project_tools import forge_project_init

        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        project_path = str(tmp_path / "test-project")
        (tmp_path / "test-project").mkdir()

        features = [
            {
                "id": "feat-1",
                "name": "Feature 1",
                "description": "Has invalid dependency",
                "depends_on": ["nonexistent"],
                "estimated_complexity": "small",
            },
        ]

        result = forge_project_init(
            project_path=project_path,
            project_name="Test Project",
            features=features,
        )

        assert result["success"] is False
        assert "error" in result
        assert "nonexistent" in result["error"].lower() or "missing" in result["error"].lower()

    def test_forge_project_init_detects_cycles(self, tmp_path, monkeypatch):
        """forge_project_init must detect cyclic dependencies."""
        from spellbook_mcp.forged.project_tools import forge_project_init

        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        project_path = str(tmp_path / "test-project")
        (tmp_path / "test-project").mkdir()

        features = [
            {
                "id": "a",
                "name": "A",
                "description": "Depends on C",
                "depends_on": ["c"],
                "estimated_complexity": "small",
            },
            {
                "id": "b",
                "name": "B",
                "description": "Depends on A",
                "depends_on": ["a"],
                "estimated_complexity": "small",
            },
            {
                "id": "c",
                "name": "C",
                "description": "Depends on B",
                "depends_on": ["b"],
                "estimated_complexity": "small",
            },
        ]

        result = forge_project_init(
            project_path=project_path,
            project_name="Cyclic Project",
            features=features,
        )

        assert result["success"] is False
        assert "error" in result
        assert "cycl" in result["error"].lower()


class TestForgeProjectStatus:
    """Tests for forge_project_status MCP tool."""

    def test_forge_project_status_returns_graph(self, tmp_path, monkeypatch):
        """forge_project_status must return current project graph."""
        from spellbook_mcp.forged.project_tools import forge_project_init, forge_project_status

        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        project_path = str(tmp_path / "test-project")
        (tmp_path / "test-project").mkdir()

        # Initialize first
        forge_project_init(
            project_path=project_path,
            project_name="Status Test",
            features=[
                {"id": "f1", "name": "F1", "description": "First", "depends_on": [], "estimated_complexity": "trivial"},
            ],
        )

        result = forge_project_status(project_path=project_path)

        assert result["success"] is True
        assert "graph" in result
        assert result["graph"]["project_name"] == "Status Test"

    def test_forge_project_status_shows_progress(self, tmp_path, monkeypatch):
        """forge_project_status must show completion progress."""
        from spellbook_mcp.forged.project_tools import forge_project_init, forge_project_status, forge_feature_update

        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        project_path = str(tmp_path / "test-project")
        (tmp_path / "test-project").mkdir()

        forge_project_init(
            project_path=project_path,
            project_name="Progress Test",
            features=[
                {"id": "f1", "name": "F1", "description": "First", "depends_on": [], "estimated_complexity": "trivial"},
                {"id": "f2", "name": "F2", "description": "Second", "depends_on": ["f1"], "estimated_complexity": "trivial"},
            ],
        )

        # Mark one feature complete
        forge_feature_update(
            project_path=project_path,
            feature_id="f1",
            status="complete",
        )

        result = forge_project_status(project_path=project_path)

        assert result["success"] is True
        assert result["progress"]["total_features"] == 2
        assert result["progress"]["completed_features"] == 1
        assert result["progress"]["completion_percentage"] == 50.0

    def test_forge_project_status_nonexistent_project(self, tmp_path, monkeypatch):
        """forge_project_status must handle nonexistent project."""
        from spellbook_mcp.forged.project_tools import forge_project_status

        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        result = forge_project_status(project_path="/nonexistent/project")

        assert result["success"] is False
        assert "error" in result


class TestForgeFeatureUpdate:
    """Tests for forge_feature_update MCP tool."""

    def test_forge_feature_update_status(self, tmp_path, monkeypatch):
        """forge_feature_update must update feature status."""
        from spellbook_mcp.forged.project_tools import forge_project_init, forge_feature_update, forge_project_status

        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        project_path = str(tmp_path / "test-project")
        (tmp_path / "test-project").mkdir()

        forge_project_init(
            project_path=project_path,
            project_name="Update Test",
            features=[
                {"id": "f1", "name": "F1", "description": "First", "depends_on": [], "estimated_complexity": "trivial"},
            ],
        )

        result = forge_feature_update(
            project_path=project_path,
            feature_id="f1",
            status="in_progress",
        )

        assert result["success"] is True

        # Verify the update
        status = forge_project_status(project_path=project_path)
        assert status["graph"]["features"]["f1"]["status"] == "in_progress"
        assert status["graph"]["current_feature"] == "f1"

    def test_forge_feature_update_adds_artifact(self, tmp_path, monkeypatch):
        """forge_feature_update must add artifacts to feature."""
        from spellbook_mcp.forged.project_tools import forge_project_init, forge_feature_update, forge_project_status

        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        project_path = str(tmp_path / "test-project")
        (tmp_path / "test-project").mkdir()

        forge_project_init(
            project_path=project_path,
            project_name="Artifact Test",
            features=[
                {"id": "f1", "name": "F1", "description": "First", "depends_on": [], "estimated_complexity": "trivial"},
            ],
        )

        result = forge_feature_update(
            project_path=project_path,
            feature_id="f1",
            artifacts=["/path/to/design.md", "/path/to/plan.md"],
        )

        assert result["success"] is True

        status = forge_project_status(project_path=project_path)
        assert "/path/to/design.md" in status["graph"]["features"]["f1"]["artifacts"]
        assert "/path/to/plan.md" in status["graph"]["features"]["f1"]["artifacts"]

    def test_forge_feature_update_marks_complete(self, tmp_path, monkeypatch):
        """forge_feature_update must update completed_features when marking complete."""
        from spellbook_mcp.forged.project_tools import forge_project_init, forge_feature_update, forge_project_status

        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        project_path = str(tmp_path / "test-project")
        (tmp_path / "test-project").mkdir()

        forge_project_init(
            project_path=project_path,
            project_name="Complete Test",
            features=[
                {"id": "f1", "name": "F1", "description": "First", "depends_on": [], "estimated_complexity": "trivial"},
            ],
        )

        result = forge_feature_update(
            project_path=project_path,
            feature_id="f1",
            status="complete",
        )

        assert result["success"] is True

        status = forge_project_status(project_path=project_path)
        assert "f1" in status["graph"]["completed_features"]

    def test_forge_feature_update_nonexistent_feature(self, tmp_path, monkeypatch):
        """forge_feature_update must handle nonexistent feature."""
        from spellbook_mcp.forged.project_tools import forge_project_init, forge_feature_update

        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        project_path = str(tmp_path / "test-project")
        (tmp_path / "test-project").mkdir()

        forge_project_init(
            project_path=project_path,
            project_name="Test",
            features=[
                {"id": "f1", "name": "F1", "description": "First", "depends_on": [], "estimated_complexity": "trivial"},
            ],
        )

        result = forge_feature_update(
            project_path=project_path,
            feature_id="nonexistent",
            status="complete",
        )

        assert result["success"] is False
        assert "error" in result


class TestForgeSelectSkill:
    """Tests for forge_select_skill MCP tool."""

    def test_forge_select_skill_returns_appropriate_skill(self, tmp_path, monkeypatch):
        """forge_select_skill must return appropriate skill for context."""
        from spellbook_mcp.forged.project_tools import forge_project_init, forge_select_skill
        from spellbook_mcp.forged.schema import init_forged_schema

        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        db_path = fake_home / ".local" / "spellbook" / "forged.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_forged_schema(str(db_path))

        project_path = str(tmp_path / "test-project")
        (tmp_path / "test-project").mkdir()

        forge_project_init(
            project_path=project_path,
            project_name="Skill Test",
            features=[
                {"id": "f1", "name": "F1", "description": "First", "depends_on": [], "estimated_complexity": "trivial"},
            ],
        )

        result = forge_select_skill(
            project_path=project_path,
            feature_id="f1",
            stage="IMPLEMENT",
        )

        assert result["success"] is True
        assert "skill" in result
        assert result["skill"] == "implementing-features"


class TestForgeSkillComplete:
    """Tests for forge_skill_complete MCP tool."""

    def test_forge_skill_complete_records_invocation(self, tmp_path, monkeypatch):
        """forge_skill_complete must record skill invocation."""
        from spellbook_mcp.forged.project_tools import forge_project_init, forge_skill_complete
        from spellbook_mcp.forged.schema import init_forged_schema

        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        db_path = fake_home / ".local" / "spellbook" / "forged.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_forged_schema(str(db_path))

        project_path = str(tmp_path / "test-project")
        (tmp_path / "test-project").mkdir()

        forge_project_init(
            project_path=project_path,
            project_name="Complete Test",
            features=[
                {"id": "f1", "name": "F1", "description": "First", "depends_on": [], "estimated_complexity": "trivial"},
            ],
        )

        result = forge_skill_complete(
            project_path=project_path,
            feature_id="f1",
            skill_name="implementing-features",
            result="success",
            context_returned={"files_created": ["/path/to/file.py"]},
        )

        assert result["success"] is True
        assert "invocation_id" in result

    def test_forge_skill_complete_updates_feature_state(self, tmp_path, monkeypatch):
        """forge_skill_complete must update feature with skill result."""
        from spellbook_mcp.forged.project_tools import (
            forge_project_init,
            forge_skill_complete,
            forge_project_status,
        )
        from spellbook_mcp.forged.schema import init_forged_schema

        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        db_path = fake_home / ".local" / "spellbook" / "forged.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_forged_schema(str(db_path))

        project_path = str(tmp_path / "test-project")
        (tmp_path / "test-project").mkdir()

        forge_project_init(
            project_path=project_path,
            project_name="State Test",
            features=[
                {"id": "f1", "name": "F1", "description": "First", "depends_on": [], "estimated_complexity": "trivial"},
            ],
        )

        forge_skill_complete(
            project_path=project_path,
            feature_id="f1",
            skill_name="writing-plans",
            result="success",
            artifacts_produced=["/path/to/plan.md"],
            context_returned={"plan_summary": "Detailed implementation plan"},
        )

        status = forge_project_status(project_path=project_path)
        assert "/path/to/plan.md" in status["graph"]["features"]["f1"]["artifacts"]
