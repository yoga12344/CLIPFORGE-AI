"""
ClipForge AI - Audio-Visual Active Speaker Intelligence Subsystem
"""

from .active_speaker_detector import LightASDDetector
from .active_speaker_service import ActiveSpeakerService
from .av_fusion_engine import AudioVisualFusionEngine
from .av_synchronizer import AudioVisualSynchronizer, StreamSyncInfo, SynchronizedAVWindow
from .schemas import (
    ActiveSpeakerAnalysisResult,
    ActiveSpeakerObservation,
    ActiveSpeakerSegment,
    SpeakerFaceMatch,
)

__all__ = [
    "LightASDDetector",
    "ActiveSpeakerService",
    "AudioVisualFusionEngine",
    "AudioVisualSynchronizer",
    "StreamSyncInfo",
    "SynchronizedAVWindow",
    "ActiveSpeakerAnalysisResult",
    "ActiveSpeakerObservation",
    "ActiveSpeakerSegment",
    "SpeakerFaceMatch",
]
