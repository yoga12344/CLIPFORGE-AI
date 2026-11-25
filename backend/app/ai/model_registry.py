from typing import Dict, List, Optional
from pydantic import BaseModel

class WhisperModelDefinition(BaseModel):
    model_id: str
    repo_id: str
    display_name: str
    description: str
    parameter_count: str
    disk_size_mb: int
    recommended_vram_mb: int
    required_files: List[str]
    license: str
    source_url: str

SUPPORTED_WHISPER_MODELS: Dict[str, WhisperModelDefinition] = {
    "tiny": WhisperModelDefinition(
        model_id="tiny",
        repo_id="Systran/faster-whisper-tiny",
        display_name="Whisper Tiny",
        description="Fastest model with lowest resource footprint. Ideal for testing and rapid draft transcription.",
        parameter_count="39M",
        disk_size_mb=75,
        recommended_vram_mb=1000,
        required_files=["model.bin", "config.json", "tokenizer.json"],
        license="MIT / Apache 2.0 (OpenAI Whisper & Systran CTranslate2)",
        source_url="https://huggingface.co/Systran/faster-whisper-tiny"
    ),
    "base": WhisperModelDefinition(
        model_id="base",
        repo_id="Systran/faster-whisper-base",
        display_name="Whisper Base",
        description="Fast transcription with good accuracy for clean English and common languages.",
        parameter_count="74M",
        disk_size_mb=145,
        recommended_vram_mb=1500,
        required_files=["model.bin", "config.json", "tokenizer.json"],
        license="MIT / Apache 2.0 (OpenAI Whisper & Systran CTranslate2)",
        source_url="https://huggingface.co/Systran/faster-whisper-base"
    ),
    "small": WhisperModelDefinition(
        model_id="small",
        repo_id="Systran/faster-whisper-small",
        display_name="Whisper Small (Recommended)",
        description="Optimal balance of speed and high accuracy for dialogue, podcasts, and diverse accents.",
        parameter_count="244M",
        disk_size_mb=485,
        recommended_vram_mb=2500,
        required_files=["model.bin", "config.json", "tokenizer.json"],
        license="MIT / Apache 2.0 (OpenAI Whisper & Systran CTranslate2)",
        source_url="https://huggingface.co/Systran/faster-whisper-small"
    ),
    "medium": WhisperModelDefinition(
        model_id="medium",
        repo_id="Systran/faster-whisper-medium",
        display_name="Whisper Medium",
        description="High precision transcription for multi-lingual content, technical jargon, and complex audio.",
        parameter_count="769M",
        disk_size_mb=1530,
        recommended_vram_mb=5000,
        required_files=["model.bin", "config.json", "tokenizer.json"],
        license="MIT / Apache 2.0 (OpenAI Whisper & Systran CTranslate2)",
        source_url="https://huggingface.co/Systran/faster-whisper-medium"
    ),
}

DEFAULT_MODEL_ID = "small"

class ModelRegistry:
    @classmethod
    def get(cls, model_id: str) -> Optional[WhisperModelDefinition]:
        return SUPPORTED_WHISPER_MODELS.get(model_id.lower())

    @classmethod
    def list_all(cls) -> List[WhisperModelDefinition]:
        return list(SUPPORTED_WHISPER_MODELS.values())

    @classmethod
    def is_valid_model(cls, model_id: str) -> bool:
        return model_id.lower() in SUPPORTED_WHISPER_MODELS
