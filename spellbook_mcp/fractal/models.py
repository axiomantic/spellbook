"""Data models for the fractal thinking system.

These dataclasses represent the core domain objects used for tracking
recursive question decomposition graphs, including nodes, edges,
budgets, and results.
"""

from dataclasses import dataclass
from typing import Optional


# Constants
SCHEMA_VERSION = 1

VALID_INTENSITIES = ["pulse", "explore", "deep"]

VALID_CHECKPOINT_MODES = ["autonomous", "convergence", "interactive"]

VALID_GRAPH_STATUSES = [
    "active",
    "paused",
    "completed",
    "error",
    "budget_exhausted",
]

VALID_NODE_STATUSES = [
    "open",
    "answered",
    "saturated",
    "error",
    "budget_exhausted",
]

VALID_NODE_TYPES = ["question", "answer"]

VALID_EDGE_TYPES = ["parent_child", "convergence", "contradiction"]

VALID_SATURATION_REASONS = [
    "semantic_overlap",
    "derivable",
    "actionable",
    "hollow_questions",
    "budget_exhausted",
    "error",
]

INTENSITY_BUDGETS = {
    "pulse": {"max_agents": 3, "max_depth": 2},
    "explore": {"max_agents": 8, "max_depth": 4},
    "deep": {"max_agents": 15, "max_depth": 6},
}


@dataclass
class GraphMetadata:
    """Metadata tracking for a fractal graph.

    Attributes:
        total_nodes: Number of nodes in the graph
        total_edges: Number of edges in the graph
        max_depth_reached: Maximum depth reached during exploration
        agents_spawned: Number of agents spawned during exploration
    """

    total_nodes: int = 0
    total_edges: int = 0
    max_depth_reached: int = 0
    agents_spawned: int = 0


@dataclass
class NodeData:
    """Data for a single node in a fractal graph.

    Attributes:
        id: Unique identifier for the node
        graph_id: ID of the graph this node belongs to
        node_type: Type of node - "question" or "answer"
        text: The question or answer text
        parent_id: ID of the parent node, if any
        owner: Agent that owns this node
        depth: Depth in the graph tree
        status: Current status of the node
        metadata_json: JSON string of additional metadata
    """

    id: str
    graph_id: str
    node_type: str
    text: str
    parent_id: Optional[str] = None
    owner: Optional[str] = None
    depth: int = 0
    status: str = "open"
    metadata_json: str = "{}"


@dataclass
class EdgeData:
    """Data for a single edge in a fractal graph.

    Attributes:
        graph_id: ID of the graph this edge belongs to
        from_node: ID of the source node
        to_node: ID of the target node
        edge_type: Type of edge - "parent_child", "convergence", or "contradiction"
        metadata_json: JSON string of additional metadata
    """

    graph_id: str
    from_node: str
    to_node: str
    edge_type: str
    metadata_json: str = "{}"


@dataclass
class Budget:
    """Resource budget for a fractal thinking session.

    Attributes:
        max_agents: Maximum number of agents that can be spawned
        max_depth: Maximum depth of recursive exploration
    """

    max_agents: int
    max_depth: int

    @classmethod
    def from_intensity(cls, intensity: str) -> "Budget":
        """Create a Budget from an intensity level.

        Args:
            intensity: One of "pulse", "explore", "deep"

        Returns:
            Budget configured for the given intensity

        Raises:
            ValueError: If intensity is not valid
        """
        if intensity not in INTENSITY_BUDGETS:
            raise ValueError(
                f"Invalid intensity '{intensity}'. "
                f"Must be one of: {VALID_INTENSITIES}"
            )
        config = INTENSITY_BUDGETS[intensity]
        return cls(max_agents=config["max_agents"], max_depth=config["max_depth"])


@dataclass
class FractalResult:
    """Result summary from a completed fractal thinking session.

    Attributes:
        graph_id: ID of the fractal graph
        seed: The original seed question
        status: Final status of the graph
        summary: Optional text summary of findings
        node_count: Total nodes created
        edge_count: Total edges created
        max_depth: Maximum depth reached
    """

    graph_id: str
    seed: str
    status: str
    summary: Optional[str] = None
    node_count: int = 0
    edge_count: int = 0
    max_depth: int = 0


def validate_checkpoint_mode(mode: str) -> bool:
    """Validate a checkpoint mode string.

    Valid modes are "autonomous", "convergence", "interactive",
    or "depth:N" where N is a positive integer.

    Args:
        mode: The checkpoint mode string to validate

    Returns:
        True if the mode is valid, False otherwise
    """
    if mode in VALID_CHECKPOINT_MODES:
        return True
    if mode.startswith("depth:"):
        depth_str = mode[6:]
        if not depth_str:
            return False
        try:
            if int(depth_str) <= 0:
                return False
            return True
        except ValueError:
            return False
    return False


def parse_checkpoint_depth(mode: str) -> Optional[int]:
    """Parse the depth value from a checkpoint mode string.

    Args:
        mode: The checkpoint mode string (e.g. "depth:3")

    Returns:
        The depth as a positive integer if mode is "depth:N" where N > 0,
        None otherwise
    """
    if mode.startswith("depth:"):
        depth_str = mode[6:]
        if not depth_str:
            return None
        try:
            val = int(depth_str)
            if val <= 0:
                return None
            return val
        except ValueError:
            return None
    return None
