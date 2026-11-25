"""
ClipForge AI - Delivery Profile Models
Separates output delivery parameters (resolution, codecs, bitrates, containers) from creative composition.
"""

from typing import Literal, Dict
from pydantic import BaseModel, Field, model_validator
from .timeline import RationalTimebase


class DeliveryProfile(BaseModel):
    """
    Final encoding and container delivery profile.
    Changing this profile re-encodes the composition without destroying creative decisions.
    """
    profile_name: str = Field("Shorts / Reels / TikTok (9:16)", description="Human-readable preset name")
    aspect_ratio: Literal["9:16", "1:1", "4:5", "16:9"] = "9:16"
    width: int = Field(1080, gt=0, description="Pixel width (must be even for H.264)")
    height: int = Field(1920, gt=0, description="Pixel height (must be even for H.264)")
    fps: float = Field(30.0, gt=0.0, le=120.0, description="Target framerate")
    timebase: RationalTimebase = Field(default_factory=lambda: RationalTimebase(numerator=30, denominator=1))
    video_codec: Literal["libx264", "h264_nvenc"] = "libx264"
    rate_control: Literal["crf", "cbr", "vbr"] = "crf"
    bitrate_kbps: int = Field(6500, ge=500, le=50000, description="Target video bitrate in kbps")
    crf: int = Field(20, ge=0, le=51, description="Constant rate factor for libx264 (lower = higher quality)")
    pixel_format: Literal["yuv420p"] = "yuv420p"
    audio_codec: Literal["aac"] = "aac"
    audio_sample_rate: int = Field(48000, description="Output audio sample rate (Hz)")
    audio_bitrate_kbps: int = Field(192, ge=64, le=384, description="Output audio bitrate in kbps")
    container: Literal["mp4"] = "mp4"
    color_space: Literal["bt709"] = "bt709"
    fast_start: bool = Field(True, description="Enables MP4 +faststart moov atom at beginning of file")
    target_loudness_lufs: float = Field(-14.0, ge=-30.0, le=-8.0, description="EBU R128 loudness target")

    @model_validator(mode="after")
    def validate_even_dimensions(self) -> "DeliveryProfile":
        if self.width % 2 != 0:
            raise ValueError(f"Output width must be an even integer for codec compatibility: {self.width}")
        if self.height % 2 != 0:
            raise ValueError(f"Output height must be an even integer for codec compatibility: {self.height}")
        return self


STANDARD_DELIVERY_PROFILES: Dict[str, DeliveryProfile] = {
    "9:16": DeliveryProfile(
        profile_name="Vertical Shorts / Reels / TikTok (9:16)",
        aspect_ratio="9:16",
        width=1080,
        height=1920,
        fps=30.0,
        timebase=RationalTimebase(numerator=30, denominator=1),
        video_codec="libx264",
        rate_control="crf",
        bitrate_kbps=6500,
        crf=20,
        target_loudness_lufs=-14.0,
    ),
    "1:1": DeliveryProfile(
        profile_name="Square Instagram Feed (1:1)",
        aspect_ratio="1:1",
        width=1080,
        height=1080,
        fps=30.0,
        timebase=RationalTimebase(numerator=30, denominator=1),
        video_codec="libx264",
        rate_control="crf",
        bitrate_kbps=5000,
        crf=20,
        target_loudness_lufs=-14.0,
    ),
    "4:5": DeliveryProfile(
        profile_name="Portrait Feed (4:5)",
        aspect_ratio="4:5",
        width=1080,
        height=1350,
        fps=30.0,
        timebase=RationalTimebase(numerator=30, denominator=1),
        video_codec="libx264",
        rate_control="crf",
        bitrate_kbps=5500,
        crf=20,
        target_loudness_lufs=-14.0,
    ),
    "16:9": DeliveryProfile(
        profile_name="Standard Landscape (16:9)",
        aspect_ratio="16:9",
        width=1920,
        height=1080,
        fps=30.0,
        timebase=RationalTimebase(numerator=30, denominator=1),
        video_codec="libx264",
        rate_control="crf",
        bitrate_kbps=8000,
        crf=18,
        target_loudness_lufs=-14.0,
    ),
}


def get_default_delivery_profile(aspect_ratio: str = "9:16") -> DeliveryProfile:
    """Retrieve standard delivery profile by aspect ratio key."""
    profile = STANDARD_DELIVERY_PROFILES.get(aspect_ratio)
    if profile:
        return profile.model_copy(deep=True)
    return STANDARD_DELIVERY_PROFILES["9:16"].model_copy(deep=True)
