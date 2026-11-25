"""
ClipForge AI - Render Process Runner with NVENC Fallback
Phase 9 Stage 3: Subprocess lifecycle management, live progress parsing, and CPU fallback.
"""

import logging
from typing import Callable, Coroutine, Optional

from ....video.ffmpeg_manager import FFmpegManager, FFmpegResult, FFmpegProgress
from ..compiler.argument_builder import FFmpegExecutionPlan
from .render_progress import RenderProgressTracker

logger = logging.getLogger("clipforge.composition.render.process")


class RenderProcessRunner:
    """Executes FFmpeg rendering commands with automatic CPU fallback on NVENC failures."""

    @classmethod
    async def run_plan(
        cls,
        plan: FFmpegExecutionPlan,
        process_id: str,
        progress_tracker: Optional[RenderProgressTracker] = None,
        total_duration: float = 0.0,
    ) -> FFmpegResult:
        """
        Execute an FFmpegExecutionPlan.
        If NVENC fails mid-execution, automatically fall back to CPU libx264.
        """
        on_prog: Optional[Callable[[FFmpegProgress], Coroutine[None, None, None]]] = None
        if progress_tracker:
            on_prog = progress_tracker.handle_ffmpeg_progress

        logger.info(f"Executing render plan with {plan.video_encoder} (script_file={plan.is_script_file})")

        # Strip ['-y', '-hide_banner'] since FFmpegManager.run prepends them
        clean_args = [a for a in plan.command_args if a not in ("-y", "-hide_banner")]
        logger.info(f"Executing FFmpeg with args: {' '.join(clean_args)}")
        result = await FFmpegManager.run(
            args=clean_args,
            process_id=process_id,
            total_duration=total_duration,
            on_progress=on_prog,
            output_file_to_verify=plan.output_file_path,
        )
        print(f"FFmpeg command finished: rc={result.return_code}, success={result.success}, err={result.error_message}", flush=True)
        if not result.success:
            print(f"FFmpeg stderr tail:\n{result.stderr[-1000:]}", flush=True)

        # Automatic CPU Fallback if NVENC failed
        if not result.success and plan.video_encoder == "h264_nvenc":
            print(f"NVENC render failed ({result.error_message}). Automatically falling back to libx264 CPU encoder...", flush=True)
            
            # Replace NVENC arguments with libx264
            fallback_args = []
            i = 0
            while i < len(plan.command_args):
                arg = plan.command_args[i]
                if arg == "-c:v" and i + 1 < len(plan.command_args) and plan.command_args[i + 1] == "h264_nvenc":
                    fallback_args.extend(["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"])
                    i += 2
                    # Skip next -preset p4 if present
                    if i < len(plan.command_args) and plan.command_args[i] == "-preset":
                        i += 2
                else:
                    fallback_args.append(arg)
                    i += 1

            clean_fallback = [a for a in fallback_args if a not in ("-y", "-hide_banner")]
            # Re-run via CPU
            result = await FFmpegManager.run(
                args=clean_fallback,
                process_id=f"{process_id}_cpu_fallback",
                total_duration=total_duration,
                on_progress=on_prog,
                output_file_to_verify=plan.output_file_path,
            )
            print(f"CPU fallback finished: rc={result.return_code}, success={result.success}, err={result.error_message}", flush=True)
            if not result.success:
                print(f"CPU fallback stderr tail:\n{result.stderr[-1000:]}", flush=True)

        return result
