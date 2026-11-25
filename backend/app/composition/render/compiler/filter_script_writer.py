"""
ClipForge AI - Filter Script Writer
Phase 9 Stage 3: Generates -filter_complex_script files safely to prevent Windows command line length overflow.
"""

import os
from pathlib import Path
from typing import Optional


class FilterScriptWriter:
    """Safely writes multi-line or long FFmpeg filtergraphs to a script file."""

    DEFAULT_CACHE_DIR = Path("storage/clipforge_data/cache/render_scripts")

    @classmethod
    def write_script(
        cls,
        filtergraph_content: str,
        render_id: str,
        custom_dir: Optional[Path] = None,
    ) -> Path:
        """
        Write filtergraph content to a deterministic .ffscript file.
        Returns the absolute path to the generated script file.
        """
        target_dir = custom_dir or cls.DEFAULT_CACHE_DIR
        target_dir.mkdir(parents=True, exist_ok=True)

        script_file = target_dir / f"filtergraph_{render_id}.ffscript"
        
        # Write clean UTF-8 text with Unix newlines for FFmpeg parser compatibility
        with open(script_file, "w", encoding="utf-8", newline="\n") as f:
            f.write(filtergraph_content)

        return script_file.resolve()
