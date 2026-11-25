"""
ClipForge AI - Render Graph Data Structure
Phase 9 Stage 3: Typed Directed Acyclic Graph (DAG) for FFmpeg filter orchestration.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from .nodes import BaseNode
from .edges import Edge


class RenderGraph(BaseModel):
    """Container representing a complete rendering DAG."""
    id: str = Field(..., description="Unique graph execution ID")
    name: str = Field(default="CompositionRenderGraph", description="Human-readable graph name")
    nodes: Dict[str, BaseNode] = Field(default_factory=dict, description="Nodes indexed by their unique node ID")
    edges: List[Edge] = Field(default_factory=list, description="List of directed edges between nodes")

    def add_node(self, node: BaseNode) -> None:
        """Add a node to the graph. Raises ValueError if ID already exists."""
        if node.id in self.nodes:
            raise ValueError(f"Node with id '{node.id}' already exists in graph.")
        self.nodes[node.id] = node

    def add_edge(
        self,
        from_node: str,
        from_port: str,
        to_node: str,
        to_port: str,
        stream_label: Optional[str] = None
    ) -> Edge:
        """Add a directed edge between two nodes."""
        edge = Edge(
            from_node=from_node,
            from_port=from_port,
            to_node=to_node,
            to_port=to_port,
            stream_label=stream_label
        )
        self.edges.append(edge)
        return edge

    def get_node(self, node_id: str) -> Optional[BaseNode]:
        return self.nodes.get(node_id)

    def get_incoming_edges(self, node_id: str) -> List[Edge]:
        """Get all edges entering the specified node."""
        return [e for e in self.edges if e.to_node == node_id]

    def get_outgoing_edges(self, node_id: str) -> List[Edge]:
        """Get all edges leaving the specified node."""
        return [e for e in self.edges if e.from_node == node_id]

    def get_dependencies(self, node_id: str) -> List[str]:
        """Return IDs of all direct parent nodes that feed into node_id."""
        return list({e.from_node for e in self.get_incoming_edges(node_id)})
