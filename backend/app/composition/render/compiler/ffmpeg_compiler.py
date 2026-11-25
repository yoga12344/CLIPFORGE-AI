"""
ClipForge AI - FFmpeg Render Graph Compiler
Phase 9 Stage 3: Top-level compiler translating typed RenderGraph into an FFmpegExecutionPlan.
"""

from typing import Any, Dict, List, Optional, Set, Tuple
from pathlib import Path

from ..graph.graph import RenderGraph
from ..graph.nodes import (
    BaseNode,
    VideoInputNode,
    AudioInputNode,
    ImageInputNode,
    OutputContainerNode,
    VideoOutputNode,
    AudioOutputNode,
    VideoAudioMuxNode,
)
from ..graph.graph_validator import GraphValidator
from ..graph.topological_sort import topological_sort
from ...schemas.delivery import DeliveryProfile
from .filter_compiler import FilterCompiler
from .argument_builder import ArgumentBuilder, FFmpegExecutionPlan
from ....video.capabilities import CapabilityDetector


class RenderCompilationError(Exception):
    """Raised when compilation of a RenderGraph into FFmpeg arguments fails."""
    def __init__(self, message: str, errors: Optional[List[Any]] = None):
        self.message = message
        self.errors = errors or []
        super().__init__(self.message)


class RenderGraphCompiler:
    """Translates a validated RenderGraph into an FFmpeg execution plan."""

    @classmethod
    def compile(
        cls,
        graph: RenderGraph,
        delivery: DeliveryProfile,
        render_id: str,
        preferred_encoder: Optional[str] = None,
        estimated_duration_seconds: float = 0.0,
        script_threshold_chars: int = 2048,
        force_script_file: bool = False,
        custom_script_dir: Optional[Path] = None,
    ) -> FFmpegExecutionPlan:
        """
        Validate graph, perform topological sort, generate filtergraph, and assemble execution plan.
        """
        # 1. Pre-flight Validation
        val_res = GraphValidator.validate(graph)
        if not val_res.is_valid:
            err_msgs = [e.message for e in val_res.errors]
            raise RenderCompilationError(
                message=f"RenderGraph validation failed with {len(val_res.errors)} error(s): {'; '.join(err_msgs)}",
                errors=val_res.errors
            )

        # 2. Topological Ordering
        ordered_nodes = topological_sort(graph)

        # 3. Assign Input Files & Input Stream Labels
        input_files: List[str] = []
        input_file_to_idx: Dict[str, int] = {}

        # Collect unique input files in order of appearance
        for node in ordered_nodes:
            if isinstance(node, (VideoInputNode, AudioInputNode, ImageInputNode)):
                fpath = str(Path(node.params["file_path"]).resolve())
                if fpath not in input_file_to_idx:
                    input_file_to_idx[fpath] = len(input_files)
                    input_files.append(fpath)

        # Map input nodes to their FFmpeg input stream specifiers (e.g. "[0:v]", "[0:a]")
        node_output_labels: Dict[Tuple[str, str], str] = {}
        for node in ordered_nodes:
            if isinstance(node, VideoInputNode):
                fpath = str(Path(node.params["file_path"]).resolve())
                idx = input_file_to_idx[fpath]
                node_output_labels[(node.id, "out")] = f"[{idx}:v]"
            elif isinstance(node, AudioInputNode):
                fpath = str(Path(node.params["file_path"]).resolve())
                idx = input_file_to_idx[fpath]
                node_output_labels[(node.id, "out")] = f"[{idx}:a]"
            elif isinstance(node, ImageInputNode):
                fpath = str(Path(node.params["file_path"]).resolve())
                idx = input_file_to_idx[fpath]
                node_output_labels[(node.id, "out")] = f"[{idx}:v]"

        # 4. Generate Filtergraph Lines
        filter_lines: List[str] = []
        assigned_edge_labels: Dict[Tuple[str, str, str, str], str] = {}
        edge_label_counter = 0

        # Assign deterministic stream labels to all inter-filter edges
        for edge in graph.edges:
            src_key = (edge.from_node, edge.from_port)
            if src_key in node_output_labels:
                # Coming from an input node: use the input specifier like [0:v]
                assigned_edge_labels[(edge.from_node, edge.from_port, edge.to_node, edge.to_port)] = node_output_labels[src_key]
            else:
                # Inter-filter edge: assign explicit stream label if defined, else synthesize unique deterministic label
                if edge.stream_label:
                    label = edge.stream_label
                else:
                    edge_label_counter += 1
                    label = f"[s_{edge.from_node}_{edge.from_port}_{edge_label_counter}]"
                assigned_edge_labels[(edge.from_node, edge.from_port, edge.to_node, edge.to_port)] = label

        # Process filter nodes in topological order
        for node in ordered_nodes:
            # Skip input, output, muxing, container nodes for filtergraph body
            if isinstance(node, (VideoInputNode, AudioInputNode, ImageInputNode, VideoOutputNode, AudioOutputNode, VideoAudioMuxNode, OutputContainerNode)):
                continue

            filter_expr = FilterCompiler.compile_node_filter(node)
            if not filter_expr:
                continue

            # Incoming stream labels for this node
            incoming_edges = graph.get_incoming_edges(node.id)
            in_labels = ""
            for port in node.inputs:
                matching_edges = [e for e in incoming_edges if e.to_port == port.name]
                if matching_edges:
                    edge = matching_edges[0]
                    in_labels += assigned_edge_labels[(edge.from_node, edge.from_port, edge.to_node, edge.to_port)]

            # Outgoing stream labels for this node
            outgoing_edges = graph.get_outgoing_edges(node.id)
            out_labels = ""
            for port in node.outputs:
                matching_edges = [e for e in outgoing_edges if e.from_port == port.name]
                if matching_edges:
                    # Look at outgoing target: if target is VideoOutputNode or AudioOutputNode, check its label
                    target_node = graph.get_node(matching_edges[0].to_node)
                    if isinstance(target_node, VideoOutputNode):
                        out_labels += f"[{target_node.params.get('label', 'v_out')}]"
                    elif isinstance(target_node, AudioOutputNode):
                        out_labels += f"[{target_node.params.get('label', 'a_out')}]"
                    else:
                        out_labels += assigned_edge_labels[(node.id, port.name, matching_edges[0].to_node, matching_edges[0].to_port)]

            filter_lines.append(f"{in_labels}{filter_expr}{out_labels}")

        filter_complex_str = ";\n".join(filter_lines)

        # 5. Determine Video Encoder & Hardware Capabilities
        caps = CapabilityDetector.detect()
        requested_enc = preferred_encoder or delivery.video_codec

        if requested_enc == "h264_nvenc" and caps.nvenc_functional:
            video_encoder = "h264_nvenc"
        else:
            video_encoder = "libx264"

        # Determine output file path from OutputContainerNode
        output_containers = [n for n in ordered_nodes if isinstance(n, OutputContainerNode)]
        out_path = output_containers[0].params.get("output_path", f"output_{render_id}.mp4")

        # 6. Assemble Final Execution Plan
        plan = ArgumentBuilder.build_plan(
            input_files=input_files,
            filter_complex_str=filter_complex_str,
            output_path=out_path,
            delivery=delivery,
            video_encoder=video_encoder,
            render_id=render_id,
            estimated_duration_seconds=estimated_duration_seconds,
            script_threshold_chars=script_threshold_chars,
            force_script_file=force_script_file,
            custom_script_dir=custom_script_dir,
        )

        return plan
