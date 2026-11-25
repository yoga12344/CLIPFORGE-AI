"""
ClipForge AI - Audio Composition and Mixing Module
"""

from .audio_mixer import db_to_linear, linear_to_db, AudioMixPlanner
from .loudness_master import LoudnessMaster, PLATFORM_LOUDNESS_PRESETS

__all__ = [
    "db_to_linear",
    "linear_to_db",
    "AudioMixPlanner",
    "LoudnessMaster",
    "PLATFORM_LOUDNESS_PRESETS",
]
