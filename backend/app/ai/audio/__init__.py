"""
ClipForge AI - Audio Intelligence Package
Provides audio extraction, preprocessing, and Voice Activity Detection (VAD).
"""

from .audio_preprocessor import AudioPreprocessor, AudioChunk
from .voice_activity_detector import VoiceActivityDetector, SpeechInterval
from .speaker_embeddings import FBankConfig, FBankExtractor, SpeakerEmbeddingExtractor
from .speaker_clustering import ClusteringConfig, ClusteringResult, SpeakerClusterer
from .speaker_diarizer import (
    DiarizationConfig,
    DiarizationResult,
    DiarizedSpeaker,
    SpeakerDiarizer,
    SpeakerEmbeddingData,
    SpeakerTurnData,
)

__all__ = [
    "AudioPreprocessor",
    "AudioChunk",
    "VoiceActivityDetector",
    "SpeechInterval",
    "FBankConfig",
    "FBankExtractor",
    "SpeakerEmbeddingExtractor",
    "ClusteringConfig",
    "ClusteringResult",
    "SpeakerClusterer",
    "DiarizationConfig",
    "DiarizationResult",
    "DiarizedSpeaker",
    "SpeakerDiarizer",
    "SpeakerEmbeddingData",
    "SpeakerTurnData",
]
