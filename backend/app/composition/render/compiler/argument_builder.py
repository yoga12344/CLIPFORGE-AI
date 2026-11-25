"""
ClipForge AI - FFmpeg Argument Builder
Phase 9 Stage 3: Assembles safe, non-shell argument arrays for subprocess execution.
"""

from typing import Dict, List, Optional
from pathlib import Path
from pydantic import BaseModel, Field

from ...schemas.delivery import DeliveryProfile
from .filter_script_writer import FilterScriptWriter


class FFmpegExecutionPlan(BaseModel):
    """Complete, validated plan ready for FFmpeg execution."""
    command_args: List[str] = Field(..., description="Array of arguments passed directly to asyncio.create_subprocess_exec")
    filter_complex_string: str = Field(..., description="Raw FFmpeg filtergraph string")
    filter_script_path: Optional[str] = Field(default=None, description="Path to .ffscript file if script was generated")
    input_files: List[str] = Field(default_factory=list, description="List of source media paths used as inputs")
    output_file_path: str = Field(..., description="Target destination path for the rendered MP4")
    video_encoder: str = Field(..., description="Encoder used (h264_nvenc or libx264)")
    is_script_file: bool = Field(default=False, description="Whether filtergraph is executed via -filter_complex_script")
    estimated_duration_seconds: float = Field(default=0.0, description="Nominal duration of output video in seconds")


class ArgumentBuilder:
    """Constructs explicit FFmpeg argument arrays without shell interpolation."""

    DEFAULT_SCRIPT_THRESHOLD = 2048

    @classmethod
    def build_plan(
        cls,
        input_files: List[str],
        filter_complex_str: str,
        output_path: str,
        delivery: DeliveryProfile,
        video_encoder: str,
        render_id: str,
        estimated_duration_seconds: float = 0.0,
        script_threshold_chars: int = DEFAULT_SCRIPT_THRESHOLD,
        force_script_file: bool = False,
        custom_script_dir: Optional[Path] = None,
    ) -> FFmpegExecutionPlan:
        """
        Assemble the complete command arguments.
        Determines whether to inline -filter_complex or write a -filter_complex_script.
        """
        cmd_args: List[str] = ["-y", "-hide_banner"]

        # Add input files
        for inp in input_files:
            cmd_args.extend(["-i", str(Path(inp).resolve())])

        # Evaluate script threshold
        use_script = force_script_file or (len(filter_complex_str) > script_threshold_chars)
        script_path_str: Optional[str] = None

        if use_script:
            script_path = FilterScriptWriter.write_script(
                filtergraph_content=filter_complex_str,
                render_id=render_id,
                custom_dir=custom_script_dir,
            )
            script_path_str = str(script_path)
            cmd_args.extend(["-filter_complex_script", script_path_str])
        else:
            cmd_args.extend(["-filter_complex", filter_complex_str])

        # Stream mapping
        cmd_args.extend(["-map", "[v_out]", "-map", "[a_out]"])

        # Video Encoder options
        v_bitrate = getattr(delivery, "bitrate_kbps", getattr(delivery, "video_bitrate_kbps", 6500))
        if video_encoder == "h264_nvenc":
            cmd_args.extend([
                "-c:v", "h264_nvenc",
                "-preset", "p4",
                "-b:v", f"{v_bitrate}k",
            ])
        else:
            cmd_args.extend([
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "20",
                "-b:v", f"{v_bitrate}k",
            ])

        # Pixel format
        pix_fmt = getattr(delivery, "pixel_format", getattr(delivery, "pix_fmt", "yuv420p"))
        cmd_args.extend(["-pix_fmt", pix_fmt])

        # Audio Encoder options
        a_bitrate = getattr(delivery, "audio_bitrate_kbps", 192)
        a_sample_rate = getattr(delivery, "audio_sample_rate", getattr(delivery, "sample_rate", 48000))
        a_channels = getattr(delivery, "channels", 2)
        cmd_args.extend([
            "-c:a", "aac",
            "-b:a", f"{a_bitrate}k",
            "-ar", str(a_sample_rate),
            "-ac", str(a_channels),
        ])

        # Faststart for web streaming & final output destination
        cmd_args.extend(["-movflags", "+faststart"])
        cmd_args.append(str(Path(output_path).resolve()))

        return FFmpegExecutionPlan(
            command_args=cmd_args,
            filter_complex_string=filter_complex_str,
            filter_script_path=script_path_str,
            input_files=input_files,
            output_file_path=output_path,
            video_encoder=video_encoder,
            is_script_file=use_script,
            estimated_duration_seconds=estimated_duration_seconds,
        )
