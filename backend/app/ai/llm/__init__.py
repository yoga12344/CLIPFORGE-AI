"""
ClipForge AI - Local LLM Subsystem
"""

from .llm_provider import LLMProvider, LlamaCppBinaryProvider
from .model_registry import ModelRegistry, LLMModelDefinition, SUPPORTED_LLM_MODELS
from .model_manager import LLMModelManager, LLMModelStatus
from .inference_manager import LLMInferenceManager, LLMInferenceStatus
from .prompt_templates import build_highlight_prompt, SYSTEM_PROMPT_BASE, CONTENT_TYPE_INSTRUCTIONS
from .structured_output import (
    RawCandidateItem,
    RawCandidatesResponse,
    parse_and_validate_candidates
)

__all__ = [
    "LLMProvider",
    "LlamaCppBinaryProvider",
    "ModelRegistry",
    "LLMModelDefinition",
    "SUPPORTED_LLM_MODELS",
    "LLMModelManager",
    "LLMModelStatus",
    "LLMInferenceManager",
    "LLMInferenceStatus",
    "build_highlight_prompt",
    "SYSTEM_PROMPT_BASE",
    "CONTENT_TYPE_INSTRUCTIONS",
    "RawCandidateItem",
    "RawCandidatesResponse",
    "parse_and_validate_candidates"
]
