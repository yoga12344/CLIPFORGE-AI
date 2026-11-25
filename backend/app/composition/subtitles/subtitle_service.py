"""
ClipForge AI - Subtitle Composition Service
Coordinates subtitle generation, styling, collision avoidance, and render graph asset delivery.
"""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any

from app.composition.schemas.subtitles import SubtitleCompositionConfig
from app.composition.subtitles.karaoke_generator import SubtitleKaraokeGenerator
from app.composition.subtitles.collision_avoidance import FaceBoxSample
from app.services.subtitle_renderer import format_ffmpeg_ass_path


class SubtitleCompositionService:
    """High-level service managing subtitle lifecycle for Phase 9 compositions."""

    @classmethod
    def generate_subtitles_for_composition(
        cls,
        subtitle_config: SubtitleCompositionConfig,
        output_dir: str,
        composition_id: str,
        version_number: int,
        canvas_width: int = 1080,
        canvas_height: int = 1920,
        face_boxes: Optional[List[FaceBoxSample]] = None,
    ) -> Optional[str]:
        """
        Generates and writes an ASS subtitle file for a given composition version.
        Returns the absolute filesystem path to the generated ASS script, or None if disabled.
        """
        if not subtitle_config.enabled or not subtitle_config.segments:
            return None

        generator = SubtitleKaraokeGenerator(
            config=subtitle_config,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
        )

        out_dir = Path(output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = f"subtitles_{composition_id}_v{version_number}.ass"
        target_path = str(out_dir / filename)

        return generator.write_ass_file(target_path, face_boxes=face_boxes)
