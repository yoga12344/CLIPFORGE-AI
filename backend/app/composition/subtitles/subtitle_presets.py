"""
ClipForge AI - Subtitle Presets and Style Resolver
Predefined broadcast caption styles, speaker palettes, and override resolution.
"""

from typing import Dict, Optional, Any
from copy import deepcopy
from app.schemas.subtitle_schemas import CaptionPresetSchema
from app.services.subtitle_renderer import DEFAULT_PRESETS
from app.composition.schemas.subtitles import SubtitleStyleOverrides, SubtitleCompositionConfig


# Speaker Accent Color Palette (for multi-speaker visual differentiation)
SPEAKER_PALETTE = [
    {"highlight": "#FACC15", "primary": "#FFFFFF"},  # Vibrant Yellow / White (Speaker 0)
    {"highlight": "#38BDF8", "primary": "#F8FAFC"},  # Sky Cyan / Crisp White (Speaker 1)
    {"highlight": "#4ADE80", "primary": "#FFFFFF"},  # Emerald Green / White (Speaker 2)
    {"highlight": "#FB923C", "primary": "#FFFFFF"},  # Coral Orange / White (Speaker 3)
    {"highlight": "#E879F9", "primary": "#FFFFFF"},  # Neon Violet / White (Speaker 4)
    {"highlight": "#F87171", "primary": "#FFFFFF"},  # Soft Crimson / White (Speaker 5)
]


class SubtitlePresetRegistry:
    """Manages preset registry and resolves customized style specifications."""

    _presets: Dict[str, CaptionPresetSchema] = {p.id: p for p in DEFAULT_PRESETS}

    @classmethod
    def get_preset(cls, preset_id: str) -> CaptionPresetSchema:
        """Fetch a base preset by ID with fallback to bold creator."""
        if preset_id in cls._presets:
            return deepcopy(cls._presets[preset_id])
        return deepcopy(cls._presets.get("preset_bold_creator", DEFAULT_PRESETS[1]))

    @classmethod
    def list_presets(cls) -> Dict[str, CaptionPresetSchema]:
        """Return all available presets."""
        return {k: deepcopy(v) for k, v in cls._presets.items()}

    @classmethod
    def apply_overrides(
        cls,
        base_preset: CaptionPresetSchema,
        overrides: Optional[SubtitleStyleOverrides]
    ) -> CaptionPresetSchema:
        """Apply explicit style overrides over a base preset."""
        preset = deepcopy(base_preset)
        if not overrides:
            return preset

        if overrides.font_family is not None:
            preset.font_family = overrides.font_family
        if overrides.font_size is not None:
            preset.font_size = overrides.font_size
        if overrides.primary_color is not None:
            preset.primary_color = overrides.primary_color
        if overrides.highlight_color is not None:
            preset.highlight_color = overrides.highlight_color
        if overrides.outline_color is not None:
            preset.outline_color = overrides.outline_color
        if overrides.outline_width is not None:
            preset.outline_width = overrides.outline_width
        if overrides.shadow_width is not None:
            preset.shadow_width = overrides.shadow_width
        if overrides.bold is not None:
            preset.bold = overrides.bold
        if overrides.italic is not None:
            preset.italic = overrides.italic
        if overrides.max_words_per_line is not None:
            preset.max_words_per_line = overrides.max_words_per_line
        if overrides.animation_style is not None:
            preset.animation_style = overrides.animation_style

        return preset

    @classmethod
    def resolve_speaker_preset(
        cls,
        base_preset: CaptionPresetSchema,
        speaker_id: Optional[str],
        speaker_styles: Dict[str, SubtitleStyleOverrides],
        speaker_index: int = 0
    ) -> CaptionPresetSchema:
        """
        Resolve style for a specific speaker.
        If an explicit override exists in speaker_styles, apply it.
        Otherwise, if speaker_id is present, apply automatic speaker palette colors.
        """
        preset = deepcopy(base_preset)
        if speaker_id and speaker_id in speaker_styles:
            return cls.apply_overrides(preset, speaker_styles[speaker_id])

        # Automatic speaker color accenting if multi-speaker
        if speaker_id:
            palette_entry = SPEAKER_PALETTE[speaker_index % len(SPEAKER_PALETTE)]
            preset.highlight_color = palette_entry["highlight"]
            preset.primary_color = palette_entry["primary"]

        return preset
