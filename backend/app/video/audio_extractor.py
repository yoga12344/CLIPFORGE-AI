import asyncio
import logging
import os
from pathlib import Path
from typing import Callable, Coroutine, Optional

from .ffmpeg_manager import FFmpegManager, FFmpegProgress
from .ffprobe_manager import FFprobeManager

logger = logging.getLogger("clipforge.video.audio")

class AudioExtractor:
    @classmethod
    async def extract_for_transcription(
        cls,
        video_path: str,
        output_wav_path: str,
        on_progress: Optional[Callable[[FFmpegProgress], Coroutine[None, None, None]]] = None,
        process_id: Optional[str] = None
    ) -> str:
        """
        Extract clean 16kHz mono 16-bit PCM WAV audio optimized for Whisper AI inference.
        """
        in_p = Path(video_path).resolve()
        if not in_p.exists():
            raise FileNotFoundError(f"Source video not found: {video_path}")

        out_p = Path(output_wav_path).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)

        meta = FFprobeManager.probe(str(in_p))
        if not meta.valid or not meta.has_audio:
            raise ValueError("Source media has no audio stream to extract.")

        total_duration = meta.duration_seconds

        args = [
            "-i", str(in_p),
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            str(out_p)
        ]

        logger.info(f"Extracting 16kHz audio from {in_p.name} to {out_p.name}...")
        res = await FFmpegManager.run(
            args=args,
            process_id=process_id,
            total_duration=total_duration,
            on_progress=on_progress,
            output_file_to_verify=str(out_p)
        )

        if not res.success:
            raise RuntimeError(f"Audio extraction failed: {res.error_message}")

        # Verify output WAV properties
        wav_meta = FFprobeManager.probe(str(out_p))
        if not wav_meta.valid or not wav_meta.audio_stream:
            raise RuntimeError("Audio extraction created an unreadable or corrupt WAV file.")

        logger.info(
            f"Audio extracted successfully: {out_p.name} ({out_p.stat().st_size} bytes, "
            f"{wav_meta.audio_stream.sample_rate}Hz, channels={wav_meta.audio_stream.channels})"
        )
        return str(out_p)
