"""
ClipForge AI - Rendered Output Validator
Phase 9 Stage 3: Deep inspection of final rendered files using FFprobe to ensure delivery specs.
"""

from typing import Any, Dict, List, Optional
from pathlib import Path
from pydantic import BaseModel, Field

from ...schemas.delivery import DeliveryProfile
from ....video.ffprobe_manager import FFprobeManager, DetailedVideoMetadata


class OutputValidationResult(BaseModel):
    """Deep verification outcome of a rendered media file."""
    status: str = Field(..., description="'valid', 'valid_with_warnings', or 'invalid'")
    is_valid: bool = Field(..., description="True if valid or valid_with_warnings")
    file_path: str = Field(...)
    file_size_bytes: int = Field(default=0)
    video_width: Optional[int] = Field(default=None)
    video_height: Optional[int] = Field(default=None)
    video_fps: Optional[float] = Field(default=None)
    video_codec: Optional[str] = Field(default=None)
    video_pix_fmt: Optional[str] = Field(default=None)
    video_duration_seconds: Optional[float] = Field(default=None)
    audio_sample_rate: Optional[int] = Field(default=None)
    audio_channels: Optional[int] = Field(default=None)
    audio_duration_seconds: Optional[float] = Field(default=None)
    av_sync_delta_seconds: Optional[float] = Field(default=None)
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)


class OutputValidator:
    """Validates rendered output against target DeliveryProfile specifications."""

    FPS_TOLERANCE_PERCENT = 0.02  # 2% tolerance for variable timestamps
    DURATION_TOLERANCE_SECONDS = 0.35  # max boundary variance
    AV_SYNC_TOLERANCE_SECONDS = 0.25  # max video vs audio duration delta

    @classmethod
    def validate_file(
        cls,
        file_path: str,
        expected_delivery: DeliveryProfile,
        expected_duration_seconds: Optional[float] = None,
    ) -> OutputValidationResult:
        """
        Probe rendered output and compare against delivery requirements.
        """
        p = Path(file_path).resolve()
        errors: List[str] = []
        warnings: List[str] = []

        if not p.exists() or not p.is_file():
            return OutputValidationResult(
                status="invalid",
                is_valid=False,
                file_path=str(p),
                errors=[f"Rendered output file does not exist: {file_path}"]
            )

        file_size = p.stat().st_size
        if file_size == 0:
            return OutputValidationResult(
                status="invalid",
                is_valid=False,
                file_path=str(p),
                file_size_bytes=0,
                errors=["Rendered output file is empty (0 bytes)."]
            )

        # Probe with FFprobeManager
        meta: DetailedVideoMetadata = FFprobeManager.probe(str(p))
        if not meta.valid or not meta.has_video or not meta.video_stream:
            return OutputValidationResult(
                status="invalid",
                is_valid=False,
                file_path=str(p),
                file_size_bytes=file_size,
                errors=[f"FFprobe could not read valid video stream: {meta.error or 'No video stream found'}"]
            )

        v_stream = meta.video_stream
        a_stream = meta.audio_stream

        # 1. Video Dimension Verification
        if v_stream.width != expected_delivery.width or v_stream.height != expected_delivery.height:
            errors.append(
                f"Resolution mismatch: expected {expected_delivery.width}x{expected_delivery.height}, "
                f"got {v_stream.width}x{v_stream.height}"
            )

        # 2. Frame Rate Verification
        fps_attr = expected_delivery.fps
        target_fps = fps_attr.fps if hasattr(fps_attr, "fps") else float(fps_attr)
        actual_fps = v_stream.fps
        if abs(actual_fps - target_fps) / target_fps > cls.FPS_TOLERANCE_PERCENT:
            warnings.append(
                f"Frame rate deviation: expected ~{target_fps:.2f} fps, got {actual_fps:.2f} fps"
            )

        # 3. Pixel Format Verification
        expected_pix_fmt = getattr(expected_delivery, "pixel_format", getattr(expected_delivery, "pix_fmt", "yuv420p"))
        if v_stream.pix_fmt and v_stream.pix_fmt != expected_pix_fmt:
            warnings.append(
                f"Pixel format deviation: expected {expected_pix_fmt}, got {v_stream.pix_fmt}"
            )

        # 4. Duration Verification
        v_dur = getattr(v_stream, "duration_seconds", None) or meta.duration_seconds or 0.0
        if expected_duration_seconds and expected_duration_seconds > 0.05:
            delta_dur = abs(v_dur - expected_duration_seconds)
            if delta_dur > cls.DURATION_TOLERANCE_SECONDS:
                warnings.append(
                    f"Video duration delta {delta_dur:.3f}s exceeds tolerance ({cls.DURATION_TOLERANCE_SECONDS}s). "
                    f"Expected {expected_duration_seconds:.3f}s, got {v_dur:.3f}s"
                )

        # 5. Audio Stream Verification
        a_sample_rate = None
        a_channels = None
        a_dur = None
        av_delta = None

        if a_stream:
            a_sample_rate = a_stream.sample_rate
            a_channels = a_stream.channels
            a_dur = getattr(a_stream, "duration_seconds", None) or v_dur

            expected_sr = getattr(expected_delivery, "audio_sample_rate", getattr(expected_delivery, "sample_rate", 48000))
            if a_sample_rate != expected_sr:
                warnings.append(
                    f"Audio sample rate deviation: expected {expected_sr} Hz, got {a_sample_rate} Hz"
                )
            expected_ch = getattr(expected_delivery, "channels", 2)
            if a_channels != expected_ch:
                warnings.append(
                    f"Audio channels deviation: expected {expected_ch}, got {a_channels}"
                )

            # A/V Sync Delta Check
            av_delta = abs(v_dur - a_dur)
            if av_delta > cls.AV_SYNC_TOLERANCE_SECONDS:
                warnings.append(
                    f"Audio-Video duration mismatch: delta of {av_delta:.3f}s exceeds {cls.AV_SYNC_TOLERANCE_SECONDS}s tolerance."
                )

        status = "invalid" if errors else ("valid_with_warnings" if warnings else "valid")
        is_valid = len(errors) == 0

        v_codec = getattr(v_stream, "codec_name", getattr(v_stream, "codec", None))

        return OutputValidationResult(
            status=status,
            is_valid=is_valid,
            file_path=str(p),
            file_size_bytes=file_size,
            video_width=v_stream.width,
            video_height=v_stream.height,
            video_fps=v_stream.fps,
            video_codec=v_codec,
            video_pix_fmt=v_stream.pix_fmt,
            video_duration_seconds=v_dur,
            audio_sample_rate=a_sample_rate,
            audio_channels=a_channels,
            audio_duration_seconds=a_dur,
            av_sync_delta_seconds=av_delta,
            errors=errors,
            warnings=warnings,
            metrics={
                "bitrate_kbps": (meta.bitrate // 1000) if getattr(meta, "bitrate", None) else None,
                "format_name": meta.format_name,
                "has_audio": meta.has_audio,
                "is_faststart": True,
            }
        )
