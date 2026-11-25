"""
ClipForge AI - Subtitle Composition Module
"""

from .subtitle_presets import SubtitlePresetRegistry, SPEAKER_PALETTE
from .collision_avoidance import (
    CollisionAvoidancePlanner,
    FaceBoxSample,
    SubtitlePlacementDirective
)
from .karaoke_generator import SubtitleKaraokeGenerator, us_to_ass_timestamp
from .subtitle_service import SubtitleCompositionService

__all__ = [
    "SubtitlePresetRegistry",
    "SPEAKER_PALETTE",
    "CollisionAvoidancePlanner",
    "FaceBoxSample",
    "SubtitlePlacementDirective",
    "SubtitleKaraokeGenerator",
    "us_to_ass_timestamp",
    "SubtitleCompositionService",
]
