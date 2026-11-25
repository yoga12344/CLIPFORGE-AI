import asyncio
import logging
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Callable, Coroutine, Dict, List, Optional
from pydantic import BaseModel

from .capabilities import CapabilityDetector

logger = logging.getLogger("clipforge.video.ffmpeg")

class FFmpegProgress(BaseModel):
    frame: int = 0
    fps: float = 0.0
    out_time_seconds: float = 0.0
    total_duration_seconds: float = 0.0
    progress_percent: int = 0
    speed: str = "0x"
    eta_seconds: Optional[float] = None
    is_completed: bool = False

class FFmpegResult(BaseModel):
    success: bool
    return_code: int
    output_path: Optional[str] = None
    stdout: str = ""
    stderr: str = ""
    elapsed_seconds: float = 0.0
    error_message: Optional[str] = None

class FFmpegManager:
    _active_processes: Dict[str, asyncio.subprocess.Process] = {}

    @classmethod
    def get_active_process(cls, process_id: str) -> Optional[asyncio.subprocess.Process]:
        return cls._active_processes.get(process_id)

    @classmethod
    async def cancel_process(cls, process_id: str) -> bool:
        """Terminate an active FFmpeg process by ID."""
        proc = cls._active_processes.get(process_id)
        if not proc:
            return False

        logger.warning(f"Cancelling FFmpeg process {process_id} (PID: {proc.pid})")
        try:
            if os.name == "nt":
                # On Windows, kill process tree cleanly
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True,
                    text=True
                )
            else:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=3.0)
                except asyncio.TimeoutError:
                    proc.kill()
            return True
        except Exception as e:
            logger.error(f"Error terminating process {process_id}: {e}")
            return False
        finally:
            cls._active_processes.pop(process_id, None)

    @classmethod
    async def run(
        cls,
        args: List[str],
        process_id: Optional[str] = None,
        total_duration: float = 0.0,
        on_progress: Optional[Callable[[FFmpegProgress], Coroutine[None, None, None]]] = None,
        timeout: Optional[float] = None,
        output_file_to_verify: Optional[str] = None
    ) -> FFmpegResult:
        """
        Execute an FFmpeg command safely using asyncio.create_subprocess_exec.
        No shell=True. Parses -progress pipe:1 for real-time progress callbacks.
        """
        caps = CapabilityDetector.detect()
        if not caps.ffmpeg_available:
            return FFmpegResult(
                success=False,
                return_code=-1,
                error_message="FFmpeg executable is not available on this system."
            )

        ffmpeg_bin = caps.ffmpeg_path
        cmd = [ffmpeg_bin, "-y", "-hide_banner"]

        # If progress callback requested, ensure -progress pipe:1 is included
        has_progress_arg = "-progress" in args
        if on_progress and not has_progress_arg:
            cmd.extend(["-progress", "pipe:1", "-nostats"])

        cmd.extend(args)

        proc_key = process_id or f"proc_{int(time.time() * 1000)}"
        start_time = time.time()
        stderr_buffer: List[str] = []
        stdout_buffer: List[str] = []

        logger.info(f"Starting FFmpeg process [{proc_key}]: {' '.join(cmd[:12])}...")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            cls._active_processes[proc_key] = proc

            async def read_stdout():
                nonlocal stdout_buffer
                progress_state: Dict[str, str] = {}
                while True:
                    line_bytes = await proc.stdout.readline()
                    if not line_bytes:
                        break
                    line = line_bytes.decode("utf-8", errors="replace").strip()
                    stdout_buffer.append(line)

                    if "=" in line:
                        k, v = line.split("=", 1)
                        progress_state[k.strip()] = v.strip()

                        if k.strip() == "progress":
                            # Progress report batch complete
                            frame = int(progress_state.get("frame", 0))
                            try:
                                fps = float(progress_state.get("fps", 0.0))
                            except ValueError:
                                fps = 0.0
                            
                            speed = progress_state.get("speed", "0x")
                            out_time_us_str = progress_state.get("out_time_us")
                            out_time_sec = 0.0
                            if out_time_us_str and out_time_us_str.isdigit():
                                out_time_sec = int(out_time_us_str) / 1_000_000.0
                            
                            percent = 0
                            eta_sec = None
                            if total_duration > 0.05:
                                percent = min(100, int((out_time_sec / total_duration) * 100))
                                remaining_sec = max(0.0, total_duration - out_time_sec)
                                try:
                                    speed_val = float(speed.replace("x", ""))
                                    if speed_val > 0.01:
                                        eta_sec = round(remaining_sec / speed_val, 1)
                                except Exception:
                                    pass

                            is_end = v.strip() == "end"
                            if is_end:
                                percent = 100

                            prog_obj = FFmpegProgress(
                                frame=frame,
                                fps=fps,
                                out_time_seconds=out_time_sec,
                                total_duration_seconds=total_duration,
                                progress_percent=percent,
                                speed=speed,
                                eta_seconds=eta_sec,
                                is_completed=is_end
                            )

                            if on_progress:
                                try:
                                    await on_progress(prog_obj)
                                except Exception as cb_err:
                                    logger.debug(f"Progress callback exception: {cb_err}")

            async def read_stderr():
                nonlocal stderr_buffer
                while True:
                    line_bytes = await proc.stderr.readline()
                    if not line_bytes:
                        break
                    line = line_bytes.decode("utf-8", errors="replace").strip()
                    stderr_buffer.append(line)

            readers = asyncio.gather(read_stdout(), read_stderr())

            if timeout:
                await asyncio.wait_for(asyncio.gather(proc.wait(), readers), timeout=timeout)
            else:
                await asyncio.gather(proc.wait(), readers)

            elapsed = time.time() - start_time
            rc = proc.returncode

            # Output file verification
            success = rc == 0
            err_msg = None
            if not success:
                err_msg = "\n".join(stderr_buffer[-20:]) if stderr_buffer else f"Process exited with code {rc}"
            elif output_file_to_verify:
                out_p = Path(output_file_to_verify)
                if not out_p.exists() or out_p.stat().st_size == 0:
                    success = False
                    err_msg = f"Expected output file was not created or is empty: {output_file_to_verify}"

            logger.info(f"FFmpeg process [{proc_key}] finished: success={success}, rc={rc}, elapsed={elapsed:.2f}s")

            return FFmpegResult(
                success=success,
                return_code=rc if rc is not None else -1,
                output_path=output_file_to_verify if success else None,
                stdout="\n".join(stdout_buffer),
                stderr="\n".join(stderr_buffer),
                elapsed_seconds=elapsed,
                error_message=err_msg
            )

        except asyncio.TimeoutError:
            await cls.cancel_process(proc_key)
            return FFmpegResult(
                success=False,
                return_code=-2,
                elapsed_seconds=time.time() - start_time,
                error_message=f"Process timed out after {timeout} seconds."
            )
        except asyncio.CancelledError:
            await cls.cancel_process(proc_key)
            return FFmpegResult(
                success=False,
                return_code=-3,
                elapsed_seconds=time.time() - start_time,
                error_message="Process was cancelled by caller."
            )
        except Exception as e:
            await cls.cancel_process(proc_key)
            return FFmpegResult(
                success=False,
                return_code=-4,
                elapsed_seconds=time.time() - start_time,
                error_message=f"Execution failed: {str(e)}"
            )
        finally:
            cls._active_processes.pop(proc_key, None)
