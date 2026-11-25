"""
ClipForge AI - Deterministic Topological Sort
Phase 9 Stage 3: Kahn's algorithm with cycle detection and deterministic tie-breaking.
"""

from typing import Dict, List, Set
from .graph import RenderGraph
from .nodes import BaseNode


class GraphCycleError(Exception):
    """Raised when a directed cycle is detected in the render graph."""
    def __init__(self, cycle_nodes: List[str]):
        self.cycle_nodes = cycle_nodes
        msg = f"Graph contains a directed cycle involving nodes: {', '.join(cycle_nodes)}"
        super().__init__(msg)


def topological_sort(graph: RenderGraph) -> List[BaseNode]:
    """
    Compute a deterministic topological ordering of all nodes in the RenderGraph.
    Uses Kahn's algorithm. Resolves ties deterministically by sorting node IDs.
    Raises GraphCycleError if a cycle is detected.
    """
    in_degree: Dict[str, int] = {node_id: 0 for node_id in graph.nodes}
    adj_list: Dict[str, List[str]] = {node_id: [] for node_id in graph.nodes}

    for edge in graph.edges:
        if edge.to_node in in_degree and edge.from_node in adj_list:
            in_degree[edge.to_node] += 1
            adj_list[edge.from_node].append(edge.to_node)

    # Deterministic queue: sort zero in-degree nodes alphabetically
    queue: List[str] = sorted([node_id for node_id, deg in in_degree.items() if deg == 0])
    ordered_ids: List[str] = []

    while queue:
        # Pop smallest ID for deterministic ordering
        current = queue.pop(0)
        ordered_ids.append(current)

        for neighbor in sorted(adj_list[current]):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                # Insert into queue maintaining sorted order
                queue.append(neighbor)
                queue.sort()

    if len(ordered_ids) != len(graph.nodes):
        # A cycle was detected; find remaining nodes with in_degree > 0
        cycle_nodes = [node_id for node_id, deg in in_degree.items() if deg > 0]
        raise GraphCycleError(cycle_nodes=cycle_nodes)

    return [graph.nodes[node_id] for node_id in ordered_ids]
