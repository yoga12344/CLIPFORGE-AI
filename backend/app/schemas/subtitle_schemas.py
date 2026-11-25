"""
ClipForge AI - Subtitle & Final Render Pydantic Schemas
Defines data structures for word-level karaoke timing, subtitle tracks,
custom presets, segment editing, and export configurations.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SubtitleWord(BaseModel):
    """A single word with precise clip-relative start and end timestamps."""
    word: str
    start: float = Field(..., ge=0.0, description="Start time in seconds relative to clip start")
    end: float = Field(..., ge=0.0, description="End time in seconds relative to clip start")
    prob: Optional[float] = Field(default=1.0, ge=0.0, le=1.0, description="Whisper confidence score")
    edited: bool = Field(default=False, description="Whether this word timing/text was manually modified")


class SubtitleSegment(BaseModel):
    """A subtitle phrase or sentence grouping containing timed words."""
    id: str
    start: float = Field(..., ge=0.0)
    end: float = Field(..., ge=0.0)
    text: str
    words: List[SubtitleWord] = Field(default_factory=list)
    speaker_id: Optional[str] = None


class CaptionPresetSchema(BaseModel):
    """Typography, coloring, layout, and animation properties for subtitles."""
    id: Optional[str] = None
    name: str
    font_family: str = "Arial"
    font_size: int = 64
    primary_color: str = "#FFFFFF"       # Main unhighlighted text color
    highlight_color: str = "#FACC15"     # Active karaoke highlighted word color
    outline_color: str = "#000000"       # Border stroke color
    outline_width: int = 6               # Stroke width in pixels
    shadow_width: int = 2                # Drop shadow offset
    bold: bool = True
    italic: bool = False
    alignment: int = 2                   # ASS numpad alignment: 2=bottom-center, 5=mid-center, 8=top-center
    margin_v: int = 220                  # Vertical bottom margin (safe zone for mobile UI)
    margin_l: int = 40                   # Left margin
    margin_r: int = 40                   # Right margin
    max_words_per_line: int = 4          # Line break threshold for vertical readability
    max_lines: int = 2                   # Maximum simultaneous caption lines
    bg_color: str = "&H00000000"         # Background box color (ASS format)
    bg_padding: int = 0                  # Box padding
    animation_style: str = "karaoke_pop" # karaoke_pop, word_by_word, phrase_fade, static
    is_default: bool = False


class SubtitleTrackResponse(BaseModel):
    """Full subtitle track associated with a clip."""
    id: str
    clip_id: str
    preset_id: Optional[str] = None
    language: str = "en"
    is_enabled: bool = True
    style_overrides: Optional[Dict[str, Any]] = None
    segments: List[SubtitleSegment] = Field(default_factory=list)
    preset: Optional[CaptionPresetSchema] = None


class UpdateSegmentRequest(BaseModel):
    """Request to update a subtitle segment text or boundary timings."""
    text: Optional[str] = None
    start: Optional[float] = None
    end: Optional[float] = None
    words: Optional[List[SubtitleWord]] = None


class SplitSegmentRequest(BaseModel):
    """Request to split a segment into two at a specific word index."""
    word_index: int = Field(..., ge=1, description="Index of word where second segment begins")


class MergeSegmentsRequest(BaseModel):
    """Request to merge two adjacent segments into one."""
    segment_ids: List[str] = Field(..., min_length=2, max_length=2)


class RenderExportRequest(BaseModel):
    """Configuration for final video rendering and export."""
    preset_id: Optional[str] = None
    resolution: str = "1080x1920"        # 1080x1920, 1080x1080, 1080x1350, 1920x1080
    fps: float = 30.0
    bitrate_kbps: int = 6000
    burn_subtitles: bool = True
    reframe_mode: str = "smart_face_track" # smart_face_track, center_crop, fit_pad, blur_background
    use_vision_tracking: bool = True
    custom_style: Optional[Dict[str, Any]] = None
    codec: Optional[str] = None          # None for auto-detect (NVENC -> libx264)


class ExportResponse(BaseModel):
    """Export history record for a rendered clip."""
    id: str
    clip_id: str
    preset_id: Optional[str] = None
    output_path: str
    resolution: str
    fps: float
    bitrate_kbps: int
    codec: str
    file_size_bytes: Optional[int] = None
    duration_seconds: float = 0.0
    burn_subtitles: bool = True
    subtitle_settings: Optional[Dict[str, Any]] = None
    status: str
    error_message: Optional[str] = None
    created_at: Any
