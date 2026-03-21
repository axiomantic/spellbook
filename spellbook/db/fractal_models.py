"""SQLAlchemy ORM models for fractal.db tables.

Maps to the schema defined in spellbook/fractal/schema.py:init_fractal_schema().
Tables: graphs, nodes, edges.
"""

import json

from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    text as sa_text,
)
from sqlalchemy.orm import relationship

from spellbook.db.base import FractalBase


def _parse_metadata(raw: str | None) -> dict:
    """Parse metadata_json string to dict, defaulting to empty dict."""
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


class FractalGraph(FractalBase):
    """A fractal exploration graph."""

    __tablename__ = "graphs"

    id = Column(Text, primary_key=True)
    seed = Column(Text, nullable=False)
    intensity = Column(Text, nullable=False)
    checkpoint_mode = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="active", server_default="active")
    metadata_json = Column(Text, default="{}", server_default="{}")
    project_dir = Column(Text, nullable=True)
    created_at = Column(Text, nullable=False, server_default=sa_text("(datetime('now'))"))
    updated_at = Column(Text, nullable=False, server_default=sa_text("(datetime('now'))"))

    nodes = relationship("FractalNode", back_populates="graph", foreign_keys="FractalNode.graph_id")
    edges = relationship("FractalEdge", back_populates="graph", foreign_keys="FractalEdge.graph_id")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "seed": self.seed,
            "intensity": self.intensity,
            "checkpoint_mode": self.checkpoint_mode,
            "status": self.status,
            "metadata": _parse_metadata(self.metadata_json),
            "project_dir": self.project_dir,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class FractalNode(FractalBase):
    """A question or answer node in a fractal graph."""

    __tablename__ = "nodes"

    id = Column(Text, primary_key=True)
    graph_id = Column(Text, ForeignKey("graphs.id", ondelete="CASCADE"), nullable=False)
    parent_id = Column(Text, ForeignKey("nodes.id", ondelete="CASCADE"), nullable=True)
    node_type = Column(Text, nullable=False)
    text = Column(Text, nullable=False)
    owner = Column(Text, nullable=True)
    depth = Column(Integer, nullable=False, default=0, server_default="0")
    status = Column(Text, nullable=False, default="open", server_default="open")
    metadata_json = Column(Text, default="{}", server_default="{}")
    created_at = Column(Text, nullable=False, server_default=sa_text("(datetime('now'))"))
    claimed_at = Column(Text, nullable=True)
    answered_at = Column(Text, nullable=True)
    synthesized_at = Column(Text, nullable=True)
    session_id = Column(Text, nullable=True)

    graph = relationship("FractalGraph", back_populates="nodes", foreign_keys=[graph_id])
    parent = relationship("FractalNode", remote_side=[id], back_populates="children", foreign_keys=[parent_id])
    children = relationship("FractalNode", back_populates="parent", foreign_keys=[parent_id])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "graph_id": self.graph_id,
            "parent_id": self.parent_id,
            "node_type": self.node_type,
            "text": self.text,
            "owner": self.owner,
            "depth": self.depth,
            "status": self.status,
            "metadata": _parse_metadata(self.metadata_json),
            "created_at": self.created_at,
            "claimed_at": self.claimed_at,
            "answered_at": self.answered_at,
            "synthesized_at": self.synthesized_at,
            "session_id": self.session_id,
        }


class FractalEdge(FractalBase):
    """An edge (relationship) between nodes in a fractal graph."""

    __tablename__ = "edges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    graph_id = Column(Text, ForeignKey("graphs.id", ondelete="CASCADE"), nullable=False)
    from_node = Column(Text, ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False)
    to_node = Column(Text, ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False)
    edge_type = Column(Text, nullable=False)
    metadata_json = Column(Text, default="{}", server_default="{}")
    created_at = Column(Text, nullable=False, server_default=sa_text("(datetime('now'))"))

    __table_args__ = (
        UniqueConstraint("graph_id", "from_node", "to_node", "edge_type"),
    )

    graph = relationship("FractalGraph", back_populates="edges", foreign_keys=[graph_id])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "graph_id": self.graph_id,
            "from_node": self.from_node,
            "to_node": self.to_node,
            "edge_type": self.edge_type,
            "metadata": _parse_metadata(self.metadata_json),
            "created_at": self.created_at,
        }
