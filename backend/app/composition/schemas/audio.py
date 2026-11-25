"""
ClipForge AI - Audio Composition and Mastering Models
Multi-track audio mixing, sidechain voice ducking, sound effects, and EBU R128 loudness.
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator
from .assets import validate_asset_uri_string
from .timeline import us_to_seconds


class VoiceDialogueConfig(BaseModel):
    """Primary vocal dialogue processing configuration."""
    gain_db: float = Field(0.0, ge=-60.0, le=24.0, description="Dialogue gain adjustment in dB")
    eq_profile: Literal["flat", "voice_clarity", "warm_vocal", "low_cut"] = "voice_clarity"
    high_pass_filter_hz: int = Field(80, ge=20, le=300, description="Low-cut rumble filter frequency")


class BackgroundMusicConfig(BaseModel):
    """Background music bed configuration."""
    asset_uri: Optional[str] = Field(None, description="Logical URI to background music (e.g. asset://audio/music_01)")
    gain_db: float = Field(-18.0, ge=-60.0, le=12.0, description="Music bed volume relative to dialogue")
    fade_in_us: int = Field(1_000_000, ge=0, description="Fade-in duration in microseconds (default 1.0s)")
    fade_out_us: int = Field(2_000_000, ge=0, description="Fade-out duration in microseconds (default 2.0s)")
    loop: bool = Field(True, description="Automatically loop track if shorter than composition")

    @field_validator("asset_uri")
    @classmethod
    def check_asset_uri(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_asset_uri_string(v)
        return None

    @property
    def fade_in_seconds(self) -> float:
        return us_to_seconds(self.fade_in_us)

    @property
    def fade_out_seconds(self) -> float:
        return us_to_seconds(self.fade_out_us)


class AudioDuckingConfig(BaseModel):
    """
    Automated sidechain compression ducking background music during active dialogue.
    """
    enabled: bool = Field(True)
    duck_attenuation_db: float = Field(-14.0, ge=-40.0, le=0.0, description="Volume drop applied during speech (dB)")
    attack_ms: int = Field(50, ge=5, le=500, description="Attack time in milliseconds")
    release_ms: int = Field(350, ge=50, le=2000, description="Release/recovery time in milliseconds")
    threshold_db: float = Field(-30.0, ge=-60.0, le=0.0, description="Speech volume trigger threshold (dB)")
    ratio: float = Field(4.0, ge=1.0, le=20.0, description="Sidechain compression ratio")


class SoundEffectItem(BaseModel):
    """Stinger, whoosh, or pop sound effect placed on timeline."""
    sfx_id: str
    asset_uri: str
    timeline_start_us: int = Field(..., ge=0)
    gain_db: float = Field(0.0, ge=-40.0, le=12.0)

    @field_validator("asset_uri")
    @classmethod
    def check_asset_uri(cls, v: str) -> str:
        return validate_asset_uri_string(v)

    @property
    def timeline_start_seconds(self) -> float:
        return us_to_seconds(self.timeline_start_us)


class LoudnessMasteringConfig(BaseModel):
    """
    Broadcast loudness mastering parameters (ITU-R BS.1770-4 / EBU R128).
    Configurable targets per delivery platform.
    """
    enabled: bool = Field(True)
    integrated_lufs: float = Field(-14.0, ge=-30.0, le=-8.0, description="Target integrated loudness (-14 LUFS standard)")
    true_peak_dbtp: float = Field(-1.0, ge=-6.0, le=0.0, description="Maximum allowable true-peak (-1.0 dBTP standard)")
    loudness_range_lu: float = Field(7.0, ge=1.0, le=20.0, description="Target loudness range (LRA)")


class AudioCompositionConfig(BaseModel):
    """Complete audio mix and mastering specification."""
    sample_rate: int = Field(48000, description="Audio sample rate (44100 or 48000 Hz)")
    channels: int = Field(2, ge=1, le=2, description="Output channel count (1=mono, 2=stereo)")
    voice: VoiceDialogueConfig = Field(default_factory=VoiceDialogueConfig)
    music: BackgroundMusicConfig = Field(default_factory=BackgroundMusicConfig)
    ducking: AudioDuckingConfig = Field(default_factory=AudioDuckingConfig)
    sound_effects: List[SoundEffectItem] = Field(default_factory=list)
    master_loudness: LoudnessMasteringConfig = Field(default_factory=LoudnessMasteringConfig)
