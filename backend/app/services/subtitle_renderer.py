"""
ClipForge AI - Advanced SubStation Alpha (ASS) Subtitle Renderer
Generates broadcast-grade .ass subtitle files with word-level karaoke timing,
typography styles, safe text escaping, line wrapping, and Windows path formatting.
"""

import math
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.schemas.subtitle_schemas import CaptionPresetSchema, SubtitleSegment, SubtitleWord


# Built-in Distinctive Caption Presets
DEFAULT_PRESETS: List[CaptionPresetSchema] = [
    CaptionPresetSchema(
        id="preset_clean_minimal",
        name="Clean Minimal",
        font_family="Arial",
        font_size=58,
        primary_color="#FFFFFF",
        highlight_color="#38BDF8",  # Sky Cyan
        outline_color="#1E293B",
        outline_width=3,
        shadow_width=1,
        bold=True,
        italic=False,
        alignment=2,
        margin_v=240,
        margin_l=40,
        margin_r=40,
        max_words_per_line=4,
        max_lines=2,
        animation_style="word_by_word",
        is_default=False,
    ),
    CaptionPresetSchema(
        id="preset_bold_creator",
        name="Bold Creator",
        font_family="Arial Black",
        font_size=72,
        primary_color="#FFFFFF",
        highlight_color="#FACC15",  # Vibrant Yellow
        outline_color="#000000",
        outline_width=7,
        shadow_width=3,
        bold=True,
        italic=False,
        alignment=2,
        margin_v=280,
        margin_l=40,
        margin_r=40,
        max_words_per_line=3,
        max_lines=2,
        animation_style="karaoke_pop",
        is_default=True,
    ),
    CaptionPresetSchema(
        id="preset_podcast_highlight",
        name="Podcast Highlight",
        font_family="Trebuchet MS",
        font_size=64,
        primary_color="#F8FAFC",
        highlight_color="#FB923C",  # Warm Orange
        outline_color="#0F172A",
        outline_width=5,
        shadow_width=2,
        bold=True,
        italic=False,
        alignment=2,
        margin_v=220,
        margin_l=40,
        margin_r=40,
        max_words_per_line=4,
        max_lines=2,
        animation_style="karaoke_pop",
        is_default=False,
    ),
    CaptionPresetSchema(
        id="preset_cinematic",
        name="Cinematic",
        font_family="Georgia",
        font_size=56,
        primary_color="#FEF08A",  # Soft Gold
        highlight_color="#F59E0B",  # Deep Amber
        outline_color="#000000",
        outline_width=3,
        shadow_width=4,
        bold=False,
        italic=True,
        alignment=2,
        margin_v=180,
        margin_l=50,
        margin_r=50,
        max_words_per_line=5,
        max_lines=2,
        animation_style="phrase_fade",
        is_default=False,
    ),
    CaptionPresetSchema(
        id="preset_gaming",
        name="Gaming",
        font_family="Impact",
        font_size=74,
        primary_color="#F0FDF4",
        highlight_color="#22C55E",  # Cyber Green
        outline_color="#020617",
        outline_width=8,
        shadow_width=4,
        bold=True,
        italic=False,
        alignment=2,
        margin_v=300,
        margin_l=40,
        margin_r=40,
        max_words_per_line=3,
        max_lines=2,
        animation_style="karaoke_pop",
        is_default=False,
    ),
    CaptionPresetSchema(
        id="preset_educational",
        name="Educational",
        font_family="Segoe UI",
        font_size=60,
        primary_color="#F1F5F9",
        highlight_color="#3B82F6",  # Royal Blue
        outline_color="#18181B",
        outline_width=4,
        shadow_width=2,
        bold=True,
        italic=False,
        alignment=2,
        margin_v=240,
        margin_l=40,
        margin_r=40,
        max_words_per_line=4,
        max_lines=2,
        animation_style="word_by_word",
        is_default=False,
    ),
    CaptionPresetSchema(
        id="preset_classic_subtitles",
        name="Classic Subtitles",
        font_family="Arial",
        font_size=52,
        primary_color="#FFFFFF",
        highlight_color="#FFFFFF",
        outline_color="#000000",
        outline_width=4,
        shadow_width=1,
        bold=False,
        italic=False,
        alignment=2,
        margin_v=160,
        margin_l=60,
        margin_r=60,
        max_words_per_line=6,
        max_lines=2,
        animation_style="static",
        is_default=False,
    ),
    CaptionPresetSchema(
        id="preset_high_contrast",
        name="High Contrast",
        font_family="Arial Black",
        font_size=66,
        primary_color="#FEF08A",  # Yellow
        highlight_color="#EF4444",  # Crimson Red
        outline_color="#000000",
        outline_width=9,
        shadow_width=4,
        bold=True,
        italic=False,
        alignment=2,
        margin_v=260,
        margin_l=40,
        margin_r=40,
        max_words_per_line=3,
        max_lines=2,
        animation_style="karaoke_pop",
        is_default=False,
    ),
]


def hex_to_ass_color(hex_color: str, alpha: int = 0) -> str:
    """
    Convert standard #RRGGBB or #RGB hex string to ASS format: &HAABBGGRR.
    Alpha ranges 0 (fully opaque) to 255 (fully transparent).
    """
    cleaned = hex_color.strip().lstrip("#")
    if len(cleaned) == 3:
        r = int(cleaned[0] * 2, 16)
        g = int(cleaned[1] * 2, 16)
        b = int(cleaned[2] * 2, 16)
    elif len(cleaned) >= 6:
        r = int(cleaned[0:2], 16)
        g = int(cleaned[2:4], 16)
        b = int(cleaned[4:6], 16)
    else:
        r, g, b = 255, 255, 255

    alpha_clamped = max(0, min(255, alpha))
    # ASS order: Alpha, Blue, Green, Red
    return f"&H{alpha_clamped:02X}{b:02X}{g:02X}{r:02X}"


def format_ass_timestamp(seconds: float) -> str:
    """
    Format time in seconds to ASS timestamp format: H:MM:SS.cs
    e.g., 65.42 -> 0:01:05.42
    """
    safe_sec = max(0.0, seconds)
    h = int(safe_sec // 3600)
    m = int((safe_sec % 3600) // 60)
    s = int(safe_sec % 60)
    cs = int(round((safe_sec - int(safe_sec)) * 100))
    if cs >= 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def escape_ass_text(text: str) -> str:
    """
    Sanitize text to prevent breaking ASS markup tags or filter injection.
    """
    if not text:
        return ""
    # Remove literal curly braces to prevent injection into ASS tags
    escaped = text.replace("{", "(").replace("}", ")")
    # Replace newlines with ASS newline tag
    escaped = re.sub(r"\r?\n", r"\\N", escaped)
    return escaped


def format_ffmpeg_ass_path(file_path: str) -> str:
    """
    Format a Windows filesystem path safely for FFmpeg's ass=filename='...' filter.
    Backslashes converted to forward slashes, colon in drive letter escaped as \:
    """
    resolved = str(Path(file_path).resolve())
    forward_slash = resolved.replace("\\", "/")
    return forward_slash.replace(":", "\\:")


class SubtitleRenderer:
    """
    Generates Advanced SubStation Alpha (.ass) scripts from subtitle segments and presets.
    Supports word-level karaoke highlighting, bold strokes, shadows, and responsive margins.
    """

    @classmethod
    def generate_ass_script(
        cls,
        segments: List[SubtitleSegment],
        preset: CaptionPresetSchema,
        canvas_width: int = 1080,
        canvas_height: int = 1920,
    ) -> str:
        """
        Build complete ASS v4+ script string.
        """
        primary_ass = hex_to_ass_color(preset.primary_color, alpha=0)
        highlight_ass = hex_to_ass_color(preset.highlight_color, alpha=0)
        outline_ass = hex_to_ass_color(preset.outline_color, alpha=0)
        shadow_ass = "&H80000000"  # 50% semi-transparent black shadow

        bold_flag = 1 if preset.bold else 0
        italic_flag = 1 if preset.italic else 0

        # ASS Script Header
        header = f"""[Script Info]
Title: ClipForge AI Professional Karaoke
ScriptType: v4.00+
PlayResX: {canvas_width}
PlayResY: {canvas_height}
ScaledBorderAndShadow: yes
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{preset.font_family},{preset.font_size},{primary_ass},{highlight_ass},{outline_ass},{shadow_ass},{bold_flag},{italic_flag},0,0,100,100,1,0,1,{preset.outline_width},{preset.shadow_width},{preset.alignment},{preset.margin_l},{preset.margin_r},{preset.margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        events: List[str] = []

        for seg in segments:
            if not seg.words:
                # Fallback to segment text without word breakdown
                escaped_text = escape_ass_text(seg.text)
                start_ts = format_ass_timestamp(seg.start)
                end_ts = format_ass_timestamp(seg.end)
                prefix = "{\\fad(150,150)}" if preset.animation_style == "phrase_fade" else ""
                events.append(f"Dialogue: 0,{start_ts},{end_ts},Default,,0,0,0,,{prefix}{escaped_text}")
                continue

            # Chunk words according to preset.max_words_per_line
            chunk_size = max(1, preset.max_words_per_line)
            word_chunks = [seg.words[i : i + chunk_size] for i in range(0, len(seg.words), chunk_size)]

            for chunk in word_chunks:
                if not chunk:
                    continue

                chunk_start = chunk[0].start
                chunk_end = chunk[-1].end

                if preset.animation_style == "static":
                    # Simple static phrase rendering
                    words_text = " ".join(escape_ass_text(w.word) for w in chunk)
                    start_ts = format_ass_timestamp(chunk_start)
                    end_ts = format_ass_timestamp(chunk_end)
                    events.append(f"Dialogue: 0,{start_ts},{end_ts},Default,,0,0,0,,{words_text}")

                elif preset.animation_style == "phrase_fade":
                    # Smooth fade in and out per chunk/phrase
                    words_text = " ".join(escape_ass_text(w.word) for w in chunk)
                    start_ts = format_ass_timestamp(chunk_start)
                    end_ts = format_ass_timestamp(chunk_end)
                    events.append(f"Dialogue: 0,{start_ts},{end_ts},Default,,0,0,0,,{{\\fad(150,150)}}{words_text}")

                elif preset.animation_style == "word_by_word":
                    # Word-by-word cumulative reveal
                    for i, active_w in enumerate(chunk):
                        w_start = active_w.start
                        w_end = active_w.end if i == len(chunk) - 1 else chunk[i + 1].start
                        parts = []
                        for j, w in enumerate(chunk):
                            clean = escape_ass_text(w.word)
                            if j == i:
                                parts.append(f"{{\\c{highlight_ass}}}{clean}{{\\r}}")
                            elif j < i:
                                parts.append(f"{{\\c{primary_ass}}}{clean}")
                            else:
                                parts.append(f"{{\\c&HFFFFFFFF}}{clean}")  # Dim/Hidden
                        line = " ".join(parts)
                        events.append(
                            f"Dialogue: 0,{format_ass_timestamp(w_start)},{format_ass_timestamp(w_end)},Default,,0,0,0,,{line}"
                        )

                else:
                    # Default: viral karaoke_pop (highlight active word with scale pop)
                    for i, active_w in enumerate(chunk):
                        w_start = active_w.start
                        # End at start of next word or end of chunk
                        w_end = chunk[i + 1].start if i + 1 < len(chunk) else active_w.end
                        w_end = max(w_start + 0.1, w_end)

                        parts = []
                        for j, w in enumerate(chunk):
                            clean = escape_ass_text(w.word)
                            if j == i:
                                # Active highlighted word with subtle 10% pop
                                parts.append(f"{{\\c{highlight_ass}\\fscx110\\fscy110}}{clean}{{\\r}}")
                            else:
                                parts.append(f"{{\\c{primary_ass}}}{clean}")

                        line = " ".join(parts)
                        events.append(
                            f"Dialogue: 0,{format_ass_timestamp(w_start)},{format_ass_timestamp(w_end)},Default,,0,0,0,,{line}"
                        )

        return header + "\n".join(events) + "\n"

    @classmethod
    def write_ass_file(
        cls,
        segments: List[SubtitleSegment],
        preset: CaptionPresetSchema,
        output_file_path: str,
        canvas_width: int = 1080,
        canvas_height: int = 1920,
    ) -> str:
        """
        Generate ASS content and write to target path. Returns the written absolute path.
        """
        content = cls.generate_ass_script(
            segments=segments,
            preset=preset,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
        )
        out_p = Path(output_file_path).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(content, encoding="utf-8")
        return str(out_p)
