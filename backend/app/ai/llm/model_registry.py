"""
ClipForge AI - Local LLM Model Registry
Defines supported quantized GGUF models for local highlight detection and intelligence.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel


class LLMModelDefinition(BaseModel):
    id: str
    name: str
    parameter_count: str
    quantization: str
    file_name: str
    file_size_bytes: int
    source_url: str
    context_window: int = 4096
    recommended_threads: int = 6
    description: str
    is_default: bool = False


# Standardized GGUF models optimized for CPU / low VRAM execution
SUPPORTED_LLM_MODELS: Dict[str, LLMModelDefinition] = {
    "qwen-2.5-3b": LLMModelDefinition(
        id="qwen-2.5-3b",
        name="Qwen 2.5 3B Instruct (Q4_K_M)",
        parameter_count="3 Billion",
        quantization="Q4_K_M",
        file_name="qwen2.5-3b-instruct-q4_k_m.gguf",
        file_size_bytes=1933080000,  # ~1.93 GB
        source_url="https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf",
        context_window=8192,
        recommended_threads=6,
        description="High-reasoning 3B model with exceptional instruction following and JSON structuring.",
        is_default=True
    ),
    "llama-3.2-3b": LLMModelDefinition(
        id="llama-3.2-3b",
        name="Llama 3.2 3B Instruct (Q4_K_M)",
        parameter_count="3.2 Billion",
        quantization="Q4_K_M",
        file_name="Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        file_size_bytes=2019448000,  # ~2.02 GB
        source_url="https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        context_window=8192,
        recommended_threads=6,
        description="Meta's compact instruct model with strong dialogue comprehension and narrative parsing.",
        is_default=False
    ),
    "qwen-2.5-1.5b": LLMModelDefinition(
        id="qwen-2.5-1.5b",
        name="Qwen 2.5 1.5B Instruct (Q4_K_M)",
        parameter_count="1.5 Billion",
        quantization="Q4_K_M",
        file_name="qwen2.5-1.5b-instruct-q4_k_m.gguf",
        file_size_bytes=1117320736,  # ~1.04 GB
        source_url="https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf",
        context_window=4096,
        recommended_threads=4,
        description="Fast, low-memory model optimized for responsive local execution.",
        is_default=False
    ),
    "qwen-2.5-0.5b": LLMModelDefinition(
        id="qwen-2.5-0.5b",
        name="Qwen 2.5 0.5B Instruct (Q4_K_M)",
        parameter_count="490 Million",
        quantization="Q4_K_M",
        file_name="qwen2.5-0.5b-instruct-q4_k_m.gguf",
        file_size_bytes=397734000,  # ~397 MB
        source_url="https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf",
        context_window=4096,
        recommended_threads=4,
        description="Ultra-lightweight model with fast CPU inference for testing and resource-constrained environments.",
        is_default=False
    )
}


class ModelRegistry:
    @classmethod
    def list_models(cls) -> List[LLMModelDefinition]:
        return list(SUPPORTED_LLM_MODELS.values())

    @classmethod
    def get_model(cls, model_id: str) -> Optional[LLMModelDefinition]:
        return SUPPORTED_LLM_MODELS.get(model_id.lower())

    @classmethod
    def get_default_model(cls) -> LLMModelDefinition:
        for m in SUPPORTED_LLM_MODELS.values():
            if m.is_default:
                return m
        return list(SUPPORTED_LLM_MODELS.values())[0]
