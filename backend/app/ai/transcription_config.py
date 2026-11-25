from typing import Optional
from pydantic import BaseModel, Field

class TranscriptionConfig(BaseModel):
    model_name: str = Field("small", description="Whisper model size: tiny, base, small, medium")
    language: Optional[str] = Field(None, description="ISO-639-1 language code or None for auto-detect")
    device: str = Field("auto", description="Target inference device: auto, cuda, or cpu")
    compute_type: Optional[str] = Field(None, description="Compute type: int8, float16, int8_float16, float32")
    vad_filter: bool = Field(True, description="Enable Voice Activity Detection to filter out background noise/silence")
    vad_threshold: float = Field(0.5, ge=0.0, le=1.0, description="Speech threshold for VAD")
    beam_size: int = Field(5, ge=1, le=10, description="Beam search width")
    word_timestamps: bool = Field(True, description="Extract word-level timestamps")
    temperature: float = Field(0.0, ge=0.0, le=1.0, description="Sampling temperature")
    initial_prompt: Optional[str] = Field(None, description="Optional prompt to condition Whisper vocabulary/context")
