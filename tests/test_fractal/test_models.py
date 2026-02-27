"""Tests for fractal thinking data models."""

import pytest


class TestConstants:
    """Tests for module-level constants."""

    def test_schema_version_defined(self):
        """SCHEMA_VERSION must be defined as integer 1."""
        from spellbook_mcp.fractal.models import SCHEMA_VERSION

        assert isinstance(SCHEMA_VERSION, int)
        assert SCHEMA_VERSION == 1

    def test_valid_intensities_defined(self):
        """VALID_INTENSITIES must contain pulse, explore, deep."""
        from spellbook_mcp.fractal.models import VALID_INTENSITIES

        assert VALID_INTENSITIES == ["pulse", "explore", "deep"]

    def test_valid_checkpoint_modes_defined(self):
        """VALID_CHECKPOINT_MODES must contain expected modes."""
        from spellbook_mcp.fractal.models import VALID_CHECKPOINT_MODES

        assert VALID_CHECKPOINT_MODES == [
            "autonomous",
            "convergence",
            "interactive",
        ]

    def test_valid_graph_statuses_defined(self):
        """VALID_GRAPH_STATUSES must contain expected statuses."""
        from spellbook_mcp.fractal.models import VALID_GRAPH_STATUSES

        assert VALID_GRAPH_STATUSES == [
            "active",
            "paused",
            "completed",
            "error",
            "budget_exhausted",
        ]

    def test_valid_node_statuses_defined(self):
        """VALID_NODE_STATUSES must contain expected statuses."""
        from spellbook_mcp.fractal.models import VALID_NODE_STATUSES

        assert VALID_NODE_STATUSES == [
            "open",
            "answered",
            "saturated",
            "error",
            "budget_exhausted",
        ]

    def test_valid_node_types_defined(self):
        """VALID_NODE_TYPES must contain question and answer."""
        from spellbook_mcp.fractal.models import VALID_NODE_TYPES

        assert VALID_NODE_TYPES == ["question", "answer"]

    def test_valid_edge_types_defined(self):
        """VALID_EDGE_TYPES must contain expected edge types."""
        from spellbook_mcp.fractal.models import VALID_EDGE_TYPES

        assert VALID_EDGE_TYPES == [
            "parent_child",
            "convergence",
            "contradiction",
        ]

    def test_valid_saturation_reasons_defined(self):
        """VALID_SATURATION_REASONS must contain expected reasons."""
        from spellbook_mcp.fractal.models import VALID_SATURATION_REASONS

        assert VALID_SATURATION_REASONS == [
            "semantic_overlap",
            "derivable",
            "actionable",
            "hollow_questions",
            "budget_exhausted",
            "error",
        ]

    def test_intensity_budgets_defined(self):
        """INTENSITY_BUDGETS must map intensities to max_agents and max_depth."""
        from spellbook_mcp.fractal.models import INTENSITY_BUDGETS

        assert INTENSITY_BUDGETS == {
            "pulse": {"max_agents": 3, "max_depth": 2},
            "explore": {"max_agents": 8, "max_depth": 4},
            "deep": {"max_agents": 15, "max_depth": 6},
        }

    def test_intensity_budgets_keys_match_valid_intensities(self):
        """INTENSITY_BUDGETS keys must match VALID_INTENSITIES."""
        from spellbook_mcp.fractal.models import (
            INTENSITY_BUDGETS,
            VALID_INTENSITIES,
        )

        assert set(INTENSITY_BUDGETS.keys()) == set(VALID_INTENSITIES)


class TestGraphMetadata:
    """Tests for GraphMetadata dataclass."""

    def test_graph_metadata_creation_defaults(self):
        """GraphMetadata must be creatable with default fields."""
        from spellbook_mcp.fractal.models import GraphMetadata

        meta = GraphMetadata()

        assert meta.total_nodes == 0
        assert meta.total_edges == 0
        assert meta.max_depth_reached == 0
        assert meta.agents_spawned == 0

    def test_graph_metadata_creation_with_values(self):
        """GraphMetadata must accept custom values."""
        from spellbook_mcp.fractal.models import GraphMetadata

        meta = GraphMetadata(
            total_nodes=10,
            total_edges=15,
            max_depth_reached=3,
            agents_spawned=5,
        )

        assert meta.total_nodes == 10
        assert meta.total_edges == 15
        assert meta.max_depth_reached == 3
        assert meta.agents_spawned == 5


class TestNodeData:
    """Tests for NodeData dataclass."""

    def test_node_data_creation(self):
        """NodeData must be creatable with required fields."""
        from spellbook_mcp.fractal.models import NodeData

        node = NodeData(
            id="node-1",
            graph_id="graph-1",
            node_type="question",
            text="What is the meaning of life?",
        )

        assert node.id == "node-1"
        assert node.graph_id == "graph-1"
        assert node.node_type == "question"
        assert node.text == "What is the meaning of life?"
        assert node.parent_id is None
        assert node.owner is None
        assert node.depth == 0
        assert node.status == "open"
        assert node.metadata_json == "{}"

    def test_node_data_with_all_fields(self):
        """NodeData must accept all optional fields."""
        from spellbook_mcp.fractal.models import NodeData

        node = NodeData(
            id="node-2",
            graph_id="graph-1",
            node_type="answer",
            text="42",
            parent_id="node-1",
            owner="agent-1",
            depth=2,
            status="answered",
            metadata_json='{"confidence": 0.95}',
        )

        assert node.parent_id == "node-1"
        assert node.owner == "agent-1"
        assert node.depth == 2
        assert node.status == "answered"
        assert node.metadata_json == '{"confidence": 0.95}'


class TestEdgeData:
    """Tests for EdgeData dataclass."""

    def test_edge_data_creation(self):
        """EdgeData must be creatable with required fields."""
        from spellbook_mcp.fractal.models import EdgeData

        edge = EdgeData(
            graph_id="graph-1",
            from_node="node-1",
            to_node="node-2",
            edge_type="parent_child",
        )

        assert edge.graph_id == "graph-1"
        assert edge.from_node == "node-1"
        assert edge.to_node == "node-2"
        assert edge.edge_type == "parent_child"
        assert edge.metadata_json == "{}"

    def test_edge_data_with_metadata(self):
        """EdgeData must accept metadata_json."""
        from spellbook_mcp.fractal.models import EdgeData

        edge = EdgeData(
            graph_id="graph-1",
            from_node="node-1",
            to_node="node-3",
            edge_type="convergence",
            metadata_json='{"strength": 0.8}',
        )

        assert edge.metadata_json == '{"strength": 0.8}'


class TestBudget:
    """Tests for Budget dataclass."""

    def test_budget_creation(self):
        """Budget must be creatable with explicit values."""
        from spellbook_mcp.fractal.models import Budget

        budget = Budget(max_agents=5, max_depth=3)

        assert budget.max_agents == 5
        assert budget.max_depth == 3

    def test_budget_from_intensity_pulse(self):
        """Budget.from_intensity('pulse') must return pulse budget."""
        from spellbook_mcp.fractal.models import Budget

        budget = Budget.from_intensity("pulse")

        assert budget.max_agents == 3
        assert budget.max_depth == 2

    def test_budget_from_intensity_explore(self):
        """Budget.from_intensity('explore') must return explore budget."""
        from spellbook_mcp.fractal.models import Budget

        budget = Budget.from_intensity("explore")

        assert budget.max_agents == 8
        assert budget.max_depth == 4

    def test_budget_from_intensity_deep(self):
        """Budget.from_intensity('deep') must return deep budget."""
        from spellbook_mcp.fractal.models import Budget

        budget = Budget.from_intensity("deep")

        assert budget.max_agents == 15
        assert budget.max_depth == 6

    def test_budget_from_intensity_invalid(self):
        """Budget.from_intensity with invalid intensity must raise ValueError."""
        from spellbook_mcp.fractal.models import Budget

        with pytest.raises(ValueError, match="Invalid intensity"):
            Budget.from_intensity("invalid")

    def test_budget_from_intensity_returns_budget_instance(self):
        """Budget.from_intensity must return a Budget instance."""
        from spellbook_mcp.fractal.models import Budget

        budget = Budget.from_intensity("pulse")

        assert isinstance(budget, Budget)


class TestFractalResult:
    """Tests for FractalResult dataclass."""

    def test_fractal_result_creation(self):
        """FractalResult must be creatable with required fields."""
        from spellbook_mcp.fractal.models import FractalResult

        result = FractalResult(
            graph_id="graph-1",
            seed="Why is the sky blue?",
            status="completed",
        )

        assert result.graph_id == "graph-1"
        assert result.seed == "Why is the sky blue?"
        assert result.status == "completed"
        assert result.summary is None
        assert result.node_count == 0
        assert result.edge_count == 0
        assert result.max_depth == 0

    def test_fractal_result_with_all_fields(self):
        """FractalResult must accept all optional fields."""
        from spellbook_mcp.fractal.models import FractalResult

        result = FractalResult(
            graph_id="graph-2",
            seed="What causes gravity?",
            status="completed",
            summary="Gravity is caused by spacetime curvature.",
            node_count=25,
            edge_count=30,
            max_depth=4,
        )

        assert result.summary == "Gravity is caused by spacetime curvature."
        assert result.node_count == 25
        assert result.edge_count == 30
        assert result.max_depth == 4


class TestValidateCheckpointMode:
    """Tests for validate_checkpoint_mode helper."""

    def test_valid_autonomous(self):
        """validate_checkpoint_mode('autonomous') must return True."""
        from spellbook_mcp.fractal.models import validate_checkpoint_mode

        assert validate_checkpoint_mode("autonomous") is True

    def test_valid_convergence(self):
        """validate_checkpoint_mode('convergence') must return True."""
        from spellbook_mcp.fractal.models import validate_checkpoint_mode

        assert validate_checkpoint_mode("convergence") is True

    def test_valid_interactive(self):
        """validate_checkpoint_mode('interactive') must return True."""
        from spellbook_mcp.fractal.models import validate_checkpoint_mode

        assert validate_checkpoint_mode("interactive") is True

    def test_valid_depth_mode(self):
        """validate_checkpoint_mode('depth:3') must return True."""
        from spellbook_mcp.fractal.models import validate_checkpoint_mode

        assert validate_checkpoint_mode("depth:3") is True

    def test_valid_depth_mode_other_number(self):
        """validate_checkpoint_mode('depth:10') must return True."""
        from spellbook_mcp.fractal.models import validate_checkpoint_mode

        assert validate_checkpoint_mode("depth:10") is True

    def test_invalid_mode(self):
        """validate_checkpoint_mode with invalid mode must return False."""
        from spellbook_mcp.fractal.models import validate_checkpoint_mode

        assert validate_checkpoint_mode("invalid") is False

    def test_invalid_empty(self):
        """validate_checkpoint_mode('') must return False."""
        from spellbook_mcp.fractal.models import validate_checkpoint_mode

        assert validate_checkpoint_mode("") is False

    def test_invalid_depth_no_number(self):
        """validate_checkpoint_mode('depth:') must return False."""
        from spellbook_mcp.fractal.models import validate_checkpoint_mode

        assert validate_checkpoint_mode("depth:") is False

    def test_invalid_depth_non_numeric(self):
        """validate_checkpoint_mode('depth:abc') must return False."""
        from spellbook_mcp.fractal.models import validate_checkpoint_mode

        assert validate_checkpoint_mode("depth:abc") is False


class TestParseCheckpointDepth:
    """Tests for parse_checkpoint_depth helper."""

    def test_depth_mode_returns_number(self):
        """parse_checkpoint_depth('depth:3') must return 3."""
        from spellbook_mcp.fractal.models import parse_checkpoint_depth

        assert parse_checkpoint_depth("depth:3") == 3

    def test_depth_mode_other_number(self):
        """parse_checkpoint_depth('depth:10') must return 10."""
        from spellbook_mcp.fractal.models import parse_checkpoint_depth

        assert parse_checkpoint_depth("depth:10") == 10

    def test_non_depth_mode_returns_none(self):
        """parse_checkpoint_depth('autonomous') must return None."""
        from spellbook_mcp.fractal.models import parse_checkpoint_depth

        assert parse_checkpoint_depth("autonomous") is None

    def test_convergence_mode_returns_none(self):
        """parse_checkpoint_depth('convergence') must return None."""
        from spellbook_mcp.fractal.models import parse_checkpoint_depth

        assert parse_checkpoint_depth("convergence") is None

    def test_interactive_mode_returns_none(self):
        """parse_checkpoint_depth('interactive') must return None."""
        from spellbook_mcp.fractal.models import parse_checkpoint_depth

        assert parse_checkpoint_depth("interactive") is None

    def test_invalid_depth_returns_none(self):
        """parse_checkpoint_depth('depth:abc') must return None."""
        from spellbook_mcp.fractal.models import parse_checkpoint_depth

        assert parse_checkpoint_depth("depth:abc") is None

    def test_empty_depth_returns_none(self):
        """parse_checkpoint_depth('depth:') must return None."""
        from spellbook_mcp.fractal.models import parse_checkpoint_depth

        assert parse_checkpoint_depth("depth:") is None
