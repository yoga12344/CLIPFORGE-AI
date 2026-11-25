"""
ClipForge AI - Stream Registry & Port Definitions for Render Graph
Phase 9 Stage 3: Typed stream definitions and compatibility matrix.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class StreamType(str, Enum):
    """Explicit media stream types flowing through render graph edges."""
    VIDEO = "video"
    AUDIO = "audio"
    IMAGE = "image"
    SUBTITLE = "subtitle"
    ENCODED_OUTPUT = "encoded_output"


class PortDirection(str, Enum):
    """Direction of a node port."""
    INPUT = "in"
    OUTPUT = "out"


class Port(BaseModel):
    """A typed communication port on a render graph node."""
    name: str = Field(..., description="Port identifier unique within the node (e.g. 'in', 'video', 'out')")
    stream_type: StreamType = Field(..., description="Media stream type this port sends or receives")
    direction: PortDirection = Field(default=PortDirection.INPUT, description="Whether port is input or output")
    required: bool = Field(default=True, description="Whether this port must be connected for the node to be valid")
    description: str = Field(default="", description="Human-readable description of port semantics")


def are_stream_types_compatible(source_type: StreamType, target_type: StreamType) -> bool:
    """
    Check if a source output stream can be legally piped into a target input stream.
    Strictly forbids routing video to audio or audio to video.
    """
    if source_type == target_type:
        return True
    
    # Images can feed into video filter inputs (e.g. watermark/overlay)
    if source_type == StreamType.IMAGE and target_type == StreamType.VIDEO:
        return True
    
    # Video or audio can feed into encoded output ports on muxers
    if source_type in (StreamType.VIDEO, StreamType.AUDIO) and target_type == StreamType.ENCODED_OUTPUT:
        return True

    return False
