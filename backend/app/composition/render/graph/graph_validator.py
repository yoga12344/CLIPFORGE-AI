"""
ClipForge AI - Render Graph Comprehensive Validator
Phase 9 Stage 3: Pre-flight validation of typed DAG structure, port types, and parameters.
"""

from typing import Dict, List, Optional, Set
from pydantic import BaseModel, Field

from .graph import RenderGraph
from .nodes import BaseNode, OutputContainerNode
from .edges import Edge
from .stream_registry import are_stream_types_compatible
from .topological_sort import topological_sort, GraphCycleError


class GraphValidationError(BaseModel):
    """Structured error explaining why a render graph is invalid."""
    node_id: Optional[str] = Field(default=None)
    node_type: Optional[str] = Field(default=None)
    field_name: Optional[str] = Field(default=None)
    error_category: str = Field(..., description="E.g. 'cycle', 'type_mismatch', 'missing_input', 'parameter'")
    message: str = Field(...)
    suggested_correction: Optional[str] = Field(default=None)


class GraphValidationWarning(BaseModel):
    """Structured warning for non-fatal graph characteristics."""
    node_id: Optional[str] = Field(default=None)
    message: str = Field(...)


class GraphValidationResult(BaseModel):
    """Overall outcome of graph validation."""
    is_valid: bool = Field(...)
    errors: List[GraphValidationError] = Field(default_factory=list)
    warnings: List[GraphValidationWarning] = Field(default_factory=list)
    topological_order: Optional[List[str]] = Field(default=None)


class GraphValidator:
    """Validates structural invariants of a RenderGraph before compilation."""

    @classmethod
    def validate(cls, graph: RenderGraph) -> GraphValidationResult:
        errors: List[GraphValidationError] = []
        warnings: List[GraphValidationWarning] = []
        ordered_ids: Optional[List[str]] = None

        if not graph.nodes:
            errors.append(GraphValidationError(
                error_category="empty_graph",
                message="Graph does not contain any nodes."
            ))
            return GraphValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # 1. Edge endpoint existence & self-references
        for edge in graph.edges:
            if edge.from_node not in graph.nodes:
                errors.append(GraphValidationError(
                    node_id=edge.from_node,
                    error_category="missing_endpoint",
                    message=f"Edge references non-existent source node '{edge.from_node}'."
                ))
            if edge.to_node not in graph.nodes:
                errors.append(GraphValidationError(
                    node_id=edge.to_node,
                    error_category="missing_endpoint",
                    message=f"Edge references non-existent target node '{edge.to_node}'."
                ))
            if edge.from_node == edge.to_node:
                errors.append(GraphValidationError(
                    node_id=edge.from_node,
                    error_category="self_reference",
                    message=f"Node '{edge.from_node}' has a self-referencing edge to itself."
                ))

        # 2. Port existence & Stream Type Compatibility
        seen_targets: Set[tuple] = set()
        seen_stream_labels: Set[str] = set()

        for edge in graph.edges:
            src_node = graph.nodes.get(edge.from_node)
            dst_node = graph.nodes.get(edge.to_node)
            if not src_node or not dst_node:
                continue

            src_port = src_node.get_output_port(edge.from_port)
            dst_port = dst_node.get_input_port(edge.to_port)

            if not src_port:
                errors.append(GraphValidationError(
                    node_id=src_node.id,
                    node_type=src_node.node_type,
                    field_name=edge.from_port,
                    error_category="missing_port",
                    message=f"Source node '{src_node.id}' has no output port named '{edge.from_port}'."
                ))
            if not dst_port:
                errors.append(GraphValidationError(
                    node_id=dst_node.id,
                    node_type=dst_node.node_type,
                    field_name=edge.to_port,
                    error_category="missing_port",
                    message=f"Target node '{dst_node.id}' has no input port named '{edge.to_port}'."
                ))

            if src_port and dst_port:
                if not are_stream_types_compatible(src_port.stream_type, dst_port.stream_type):
                    errors.append(GraphValidationError(
                        node_id=dst_node.id,
                        node_type=dst_node.node_type,
                        field_name=dst_port.name,
                        error_category="type_mismatch",
                        message=(
                            f"Stream type mismatch: cannot connect output '{src_port.name}' of type '{src_port.stream_type.value}' "
                            f"on '{src_node.id}' to input '{dst_port.name}' of type '{dst_port.stream_type.value}' on '{dst_node.id}'."
                        )
                    ))

            # Duplicate connection to same input port
            target_key = (edge.to_node, edge.to_port)
            if target_key in seen_targets:
                errors.append(GraphValidationError(
                    node_id=edge.to_node,
                    field_name=edge.to_port,
                    error_category="duplicate_input_connection",
                    message=f"Input port '{edge.to_port}' on node '{edge.to_node}' is connected to multiple source edges."
                ))
            seen_targets.add(target_key)

            # Check uniqueness of explicit stream labels
            if edge.stream_label:
                if edge.stream_label in seen_stream_labels:
                    errors.append(GraphValidationError(
                        error_category="duplicate_stream_label",
                        message=f"Duplicate stream label '{edge.stream_label}' used on multiple edges."
                    ))
                seen_stream_labels.add(edge.stream_label)

        # 3. Cycle Detection via Topological Sort
        try:
            sorted_nodes = topological_sort(graph)
            ordered_ids = [n.id for n in sorted_nodes]
        except GraphCycleError as cycle_err:
            errors.append(GraphValidationError(
                error_category="cycle",
                message=str(cycle_err),
                suggested_correction="Break the feedback loop between the cycle nodes."
            ))

        # 4. Required Input Ports Connection Check
        for node in graph.nodes.values():
            incoming = graph.get_incoming_edges(node.id)
            connected_inputs = {e.to_port for e in incoming}
            for port in node.inputs:
                if port.required and port.name not in connected_inputs:
                    errors.append(GraphValidationError(
                        node_id=node.id,
                        node_type=node.node_type,
                        field_name=port.name,
                        error_category="missing_required_input",
                        message=f"Required input port '{port.name}' on node '{node.id}' ({node.node_type}) is not connected."
                    ))

        # 5. Node Parameter Validation
        for node in graph.nodes.values():
            param_errors = node.validate_parameters()
            for err in param_errors:
                errors.append(GraphValidationError(
                    node_id=node.id,
                    node_type=node.node_type,
                    error_category="parameter_error",
                    message=err
                ))

        # 6. Container Output Node Verification
        output_containers = [n for n in graph.nodes.values() if isinstance(n, OutputContainerNode)]
        if len(output_containers) == 0:
            errors.append(GraphValidationError(
                error_category="missing_output_container",
                message="Graph does not contain any OutputContainerNode."
            ))
        elif len(output_containers) > 1:
            errors.append(GraphValidationError(
                error_category="multiple_output_containers",
                message=f"Graph contains {len(output_containers)} OutputContainerNodes; single-file render requires exactly 1."
            ))

        return GraphValidationResult(
            is_valid=(len(errors) == 0),
            errors=errors,
            warnings=warnings,
            topological_order=ordered_ids
        )
