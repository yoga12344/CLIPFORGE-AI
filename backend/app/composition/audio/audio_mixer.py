"""
ClipForge AI - Audio Mixer and Ducking Logic
Decibel conversions, sidechain compression parameter mapping, and mix topology planning.
"""

import math
from typing import Dict, Any, Optional
from app.composition.schemas.audio import (
    AudioCompositionConfig,
    VoiceDialogueConfig,
    BackgroundMusicConfig,
    AudioDuckingConfig,
    LoudnessMasteringConfig
)


def db_to_linear(gain_db: float) -> float:
    """Convert decibels (dB) to linear amplitude multiplier."""
    return round(math.pow(10.0, gain_db / 20.0), 4)


def linear_to_db(linear: float) -> float:
    """Convert linear amplitude multiplier to decibels (dB)."""
    if linear <= 0.0:
        return -96.0
    return round(20.0 * math.log10(linear), 2)


class AudioMixPlanner:
    """Calculates parameters for multi-track audio mixing and dynamic voice ducking."""

    @classmethod
    def calculate_ducking_parameters(cls, ducking_cfg: AudioDuckingConfig) -> Dict[str, float]:
        """
        Translates human-readable ducking settings into FFmpeg sidechaincompress parameters.
        Threshold is converted from dB to linear ratio (0.0 to 1.0).
        """
        # Linear threshold for sidechaincompress (e.g. -30dB -> ~0.0316)
        linear_threshold = db_to_linear(ducking_cfg.threshold_db)
        return {
            "threshold": linear_threshold,
            "ratio": float(ducking_cfg.ratio),
            "attack": float(ducking_cfg.attack_ms),
            "release": float(ducking_cfg.release_ms),
        }
