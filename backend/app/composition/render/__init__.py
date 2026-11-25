"""
ClipForge AI - Composition Render Engine
Phase 9 Stage 3: Modular DAG, FFmpeg Compiler, Execution Harness & Output Validation.
"""

from .graph import (
    StreamType,
    BaseNode,
    RenderGraph,
    CompositionToGraphBuilder,
    GraphValidator,
    topological_sort,
)
from .compiler import (
    RenderGraphCompiler,
    FFmpegExecutionPlan,
    ArgumentBuilder,
    FilterCompiler,
    FilterScriptWriter,
)
from .execution import (
    RenderExecutor,
    RenderExecutionResult,
    RenderProcessRunner,
    RenderProgressTracker,
    RenderCancellationHandler,
    RenderRecoveryService,
)
from .validation import (
    OutputValidator,
    OutputValidationResult,
    RenderValidator,
    SynchronizationValidator,
)
from .services import (
    RenderService,
    RenderPlanService,
)

__all__ = [
    "StreamType",
    "BaseNode",
    "RenderGraph",
    "CompositionToGraphBuilder",
    "GraphValidator",
    "topological_sort",
    "RenderGraphCompiler",
    "FFmpegExecutionPlan",
    "ArgumentBuilder",
    "FilterCompiler",
    "FilterScriptWriter",
    "RenderExecutor",
    "RenderExecutionResult",
    "RenderProcessRunner",
    "RenderProgressTracker",
    "RenderCancellationHandler",
    "RenderRecoveryService",
    "OutputValidator",
    "OutputValidationResult",
    "RenderValidator",
    "SynchronizationValidator",
    "RenderService",
    "RenderPlanService",
]
