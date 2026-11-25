"""
ClipForge AI - Render Graph Edge Definitions
Phase 9 Stage 3: Typed edge connecting source node output port to target node input port.
"""

from typing import Optional
from pydantic import BaseModel, Field


class Edge(BaseModel):
    """Directed connection from a source node's output port to a target node's input port."""
    from_node: str = Field(..., description="Source node ID")
    from_port: str = Field(..., description="Source node output port name (e.g. 'out', 'v_out')")
    to_node: str = Field(..., description="Target node ID")
    to_port: str = Field(..., description="Target node input port name (e.g. 'in', 'video')")
    stream_label: Optional[str] = Field(default=None, description="Explicit FFmpeg stream label assigned to this edge (e.g. '[v_crop_0]')")

    def __repr__(self) -> str:
        label_part = f" ({self.stream_label})" if self.stream_label else ""
        return f"Edge({self.from_node}:{self.from_port} -> {self.to_node}:{self.to_port}{label_part})"
