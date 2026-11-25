"""
ClipForge AI - Subtitle Karaoke Generator
Compiles microsecond-precise subtitle references and speaker styles into broadcast-grade ASS files.
"""

import re
from typing import List, Dict, Optional, Any
from pathlib import Path

from app.schemas.subtitle_schemas import CaptionPresetSchema
from app.services.subtitle_renderer import hex_to_ass_color, escape_ass_text, format_ass_timestamp
from app.composition.schemas.subtitles import (
    SubtitleCompositionConfig,
    SubtitleSegmentRef,
    SubtitleWordRef,
    SubtitleStyleOverrides
)
from app.composition.subtitles.subtitle_presets import SubtitlePresetRegistry
from app.composition.subtitles.collision_avoidance import (
    CollisionAvoidancePlanner,
    FaceBoxSample,
    SubtitlePlacementDirective
)


def us_to_ass_timestamp(microseconds: int) -> str:
    """Format microseconds to ASS timestamp: H:MM:SS.cs"""
    seconds = microseconds / 1_000_000.0
    return format_ass_timestamp(seconds)


class SubtitleKaraokeGenerator:
    """
    Transforms SubtitleCompositionConfig and timing data into an ASS v4+ script.
    """

    def __init__(
        self,
        config: SubtitleCompositionConfig,
        canvas_width: int = 1080,
        canvas_height: int = 1920,
    ):
        self.config = config
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.base_preset = SubtitlePresetRegistry.get_preset(config.preset_id)
        if config.style_overrides:
            self.base_preset = SubtitlePresetRegistry.apply_overrides(
                self.base_preset, config.style_overrides
            )
        self.collision_planner = CollisionAvoidancePlanner(
            config=config.collision,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
            base_bottom_margin=self.base_preset.margin_v
        )

    def generate_ass_script(
        self,
        face_boxes: Optional[List[FaceBoxSample]] = None
    ) -> str:
        """
        Generate complete ASS script string with speaker styles, karaoke animations,
        and face collision avoidance.
        """
        # Discover all unique speakers in segments
        speaker_ids = []
        for seg in self.config.segments:
            if seg.speaker_id and seg.speaker_id not in speaker_ids:
                speaker_ids.append(seg.speaker_id)

        # Build style dictionary per speaker
        speaker_presets: Dict[str, CaptionPresetSchema] = {}
        for idx, spk in enumerate(speaker_ids):
            speaker_presets[spk] = SubtitlePresetRegistry.resolve_speaker_preset(
                base_preset=self.base_preset,
                speaker_id=spk,
                speaker_styles=self.config.speaker_styles,
                speaker_index=idx
            )

        # ASS Script Header
        header = f"""[Script Info]
Title: ClipForge AI Professional Subtitle Composition
ScriptType: v4.00+
PlayResX: {self.canvas_width}
PlayResY: {self.canvas_height}
ScaledBorderAndShadow: yes
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
"""

        # Generate Default Base Style
        p = self.base_preset
        primary_ass = hex_to_ass_color(p.primary_color, alpha=0)
        highlight_ass = hex_to_ass_color(p.highlight_color, alpha=0)
        outline_ass = hex_to_ass_color(p.outline_color, alpha=0)
        shadow_ass = "&H80000000"
        bold_flag = 1 if p.bold else 0
        italic_flag = 1 if p.italic else 0

        header += f"Style: Default,{p.font_family},{p.font_size},{primary_ass},{highlight_ass},{outline_ass},{shadow_ass},{bold_flag},{italic_flag},0,0,100,100,1,0,1,{p.outline_width},{p.shadow_width},{p.alignment},{p.margin_l},{p.margin_r},{p.margin_v},1\n"

        # Generate Per-Speaker Styles
        for spk, sp_preset in speaker_presets.items():
            sp_prim = hex_to_ass_color(sp_preset.primary_color, alpha=0)
            sp_high = hex_to_ass_color(sp_preset.highlight_color, alpha=0)
            sp_out = hex_to_ass_color(sp_preset.outline_color, alpha=0)
            sp_bold = 1 if sp_preset.bold else 0
            sp_ital = 1 if sp_preset.italic else 0
            header += f"Style: {spk},{sp_preset.font_family},{sp_preset.font_size},{sp_prim},{sp_high},{sp_out},{shadow_ass},{sp_bold},{sp_ital},0,0,100,100,1,0,1,{sp_preset.outline_width},{sp_preset.shadow_width},{sp_preset.alignment},{sp_preset.margin_l},{sp_preset.margin_r},{sp_preset.margin_v},1\n"

        header += "\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"

        events: List[str] = []

        for seg in self.config.segments:
            seg_start_s = seg.start_seconds
            seg_end_s = seg.end_seconds
            style_name = seg.speaker_id if seg.speaker_id and seg.speaker_id in speaker_presets else "Default"
            active_preset = speaker_presets.get(seg.speaker_id, self.base_preset)

            anim_style = active_preset.animation_style
            preset_prim_ass = hex_to_ass_color(active_preset.primary_color, alpha=0)
            preset_high_ass = hex_to_ass_color(active_preset.highlight_color, alpha=0)

            # Evaluate Collision Avoidance
            placement: SubtitlePlacementDirective = self.collision_planner.calculate_placement(
                start_s=seg_start_s,
                end_s=seg_end_s,
                face_boxes=face_boxes or [],
                default_mode=self.config.position_mode,
                custom_y_fraction=self.config.custom_y_fraction
            )

            # Build positional tag or margin override
            pos_prefix = ""
            if placement.pos_tag:
                pos_prefix = placement.pos_tag
            elif placement.alignment != active_preset.alignment:
                pos_prefix = f"{{\\an{placement.alignment}}}"

            margin_v_override = placement.margin_v

            # If no words are attached, render segment text directly
            if not seg.words:
                escaped_text = escape_ass_text(seg.text)
                start_ts = us_to_ass_timestamp(seg.start_us)
                end_ts = us_to_ass_timestamp(seg.end_us)
                fade_tag = "{\\fad(150,150)}" if anim_style == "phrase_fade" else ""
                events.append(
                    f"Dialogue: 0,{start_ts},{end_ts},{style_name},,0,0,{margin_v_override},,{pos_prefix}{fade_tag}{escaped_text}"
                )
                continue

            # Word chunking
            chunk_size = max(1, active_preset.max_words_per_line)
            word_chunks = [seg.words[i : i + chunk_size] for i in range(0, len(seg.words), chunk_size)]

            for chunk in word_chunks:
                if not chunk:
                    continue

                chunk_start_us = chunk[0].start_us
                chunk_end_us = chunk[-1].end_us
                start_ts = us_to_ass_timestamp(chunk_start_us)
                end_ts = us_to_ass_timestamp(chunk_end_us)

                if anim_style == "static":
                    words_text = " ".join(escape_ass_text(w.word) for w in chunk)
                    events.append(
                        f"Dialogue: 0,{start_ts},{end_ts},{style_name},,0,0,{margin_v_override},,{pos_prefix}{words_text}"
                    )

                elif anim_style == "phrase_fade":
                    words_text = " ".join(escape_ass_text(w.word) for w in chunk)
                    events.append(
                        f"Dialogue: 0,{start_ts},{end_ts},{style_name},,0,0,{margin_v_override},,{pos_prefix}{{\\fad(150,150)}}{words_text}"
                    )

                elif anim_style == "word_by_word":
                    for i, active_w in enumerate(chunk):
                        w_start_us = active_w.start_us
                        w_end_us = chunk[i + 1].start_us if i + 1 < len(chunk) else active_w.end_us
                        w_end_us = max(w_start_us + 100_000, w_end_us)
                        parts = []
                        for j, w in enumerate(chunk):
                            clean = escape_ass_text(w.word)
                            if j == i:
                                parts.append(f"{{\\c{preset_high_ass}}}{clean}{{\\r}}")
                            elif j < i:
                                parts.append(f"{{\\c{preset_prim_ass}}}{clean}")
                            else:
                                parts.append(f"{{\\c&HFFFFFFFF}}{clean}")
                        line = " ".join(parts)
                        events.append(
                            f"Dialogue: 0,{us_to_ass_timestamp(w_start_us)},{us_to_ass_timestamp(w_end_us)},{style_name},,0,0,{margin_v_override},,{pos_prefix}{line}"
                        )

                else:
                    # Default: viral karaoke_pop (highlight active word with pop effect)
                    for i, active_w in enumerate(chunk):
                        w_start_us = active_w.start_us
                        w_end_us = chunk[i + 1].start_us if i + 1 < len(chunk) else active_w.end_us
                        w_end_us = max(w_start_us + 100_000, w_end_us)

                        parts = []
                        for j, w in enumerate(chunk):
                            clean = escape_ass_text(w.word)
                            if j == i:
                                parts.append(f"{{\\c{preset_high_ass}\\fscx110\\fscy110}}{clean}{{\\r}}")
                            else:
                                parts.append(f"{{\\c{preset_prim_ass}}}{clean}")

                        line = " ".join(parts)
                        events.append(
                            f"Dialogue: 0,{us_to_ass_timestamp(w_start_us)},{us_to_ass_timestamp(w_end_us)},{style_name},,0,0,{margin_v_override},,{pos_prefix}{line}"
                        )

        return header + "".join(events) if events and events[-1].endswith("\n") else header + "\n".join(events) + "\n"

    def write_ass_file(
        self,
        output_file_path: str,
        face_boxes: Optional[List[FaceBoxSample]] = None
    ) -> str:
        """Write generated script to target path and return absolute path."""
        content = self.generate_ass_script(face_boxes=face_boxes)
        out_p = Path(output_file_path).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(content, encoding="utf-8")
        return str(out_p)
