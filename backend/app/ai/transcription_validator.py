import logging
import os
from pathlib import Path
from typing import Optional, Tuple
from ..video.ffprobe_manager import FFprobeManager

logger = logging.getLogger("clipforge.ai.validator")

class AudioValidationResult:
    def __init__(self, valid: bool, error: Optional[str] = None, duration_seconds: float = 0.0):
        self.valid = valid
        self.error = error
        self.duration_seconds = duration_seconds

class TranscriptionValidator:
    @classmethod
    def validate_audio_file(cls, audio_file_path: str) -> AudioValidationResult:
        """
        Validate audio file exists, is readable, and contains valid audio streams.
        """
        p = Path(audio_file_path).resolve()
        if not p.exists() or not p.is_file():
            return AudioValidationResult(valid=False, error=f"Audio file does not exist: {audio_file_path}")

        file_size = p.stat().st_size
        if file_size == 0:
            return AudioValidationResult(valid=False, error="Audio file is empty (0 bytes).")

        # Probe with FFprobe
        meta = FFprobeManager.probe(str(p))
        if not meta.valid or not meta.has_audio:
            return AudioValidationResult(valid=False, error=f"Invalid or corrupt audio file: {meta.error}")

        if meta.duration_seconds <= 0.05:
            return AudioValidationResult(valid=False, error="Audio duration is too short for transcription (<0.05s).")

        return AudioValidationResult(valid=True, duration_seconds=meta.duration_seconds)
