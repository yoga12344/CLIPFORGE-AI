"""
ClipForge AI - Loudness Mastering (EBU R128 / ITU-R BS.1770)
Predefined platform loudness presets and mastering validation.
"""

from typing import Dict
from app.composition.schemas.audio import LoudnessMasteringConfig


PLATFORM_LOUDNESS_PRESETS: Dict[str, LoudnessMasteringConfig] = {
    "youtube_shorts": LoudnessMasteringConfig(
        enabled=True,
        integrated_lufs=-14.0,
        true_peak_dbtp=-1.0,
        loudness_range_lu=7.0,
    ),
    "tiktok": LoudnessMasteringConfig(
        enabled=True,
        integrated_lufs=-14.0,
        true_peak_dbtp=-1.0,
        loudness_range_lu=7.0,
    ),
    "instagram_reels": LoudnessMasteringConfig(
        enabled=True,
        integrated_lufs=-14.0,
        true_peak_dbtp=-1.0,
        loudness_range_lu=7.0,
    ),
    "podcast": LoudnessMasteringConfig(
        enabled=True,
        integrated_lufs=-16.0,
        true_peak_dbtp=-1.0,
        loudness_range_lu=8.0,
    ),
    "broadcast_tv": LoudnessMasteringConfig(
        enabled=True,
        integrated_lufs=-23.0,
        true_peak_dbtp=-1.0,
        loudness_range_lu=10.0,
    ),
}


class LoudnessMaster:
    """Provides platform-specific broadcast loudness mastering standards."""

    @classmethod
    def get_preset(cls, platform: str) -> LoudnessMasteringConfig:
        """Fetch platform mastering preset with default to -14 LUFS."""
        return PLATFORM_LOUDNESS_PRESETS.get(
            platform.lower(),
            PLATFORM_LOUDNESS_PRESETS["youtube_shorts"]
        )
