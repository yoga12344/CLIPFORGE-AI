"""
ClipForge AI - FFmpeg Filter Node Compiler
Phase 9 Stage 3: Compiles individual typed graph nodes into valid FFmpeg filter syntax.
"""

from typing import Dict, List, Optional
from pathlib import Path

from ..graph.nodes import (
    BaseNode,
    VideoTrimNode,
    AudioTrimNode,
    SetPTSNode,
    SetAPTSNode,
    FPSNormalizeNode,
    CropNode,
    ScaleNode,
    PadNode,
    SARNormalizeNode,
    PixelFormatConvertNode,
    SubtitleBurnNode,
    SplitNode,
    ASplitNode,
    OverlayNode,
    VStackNode,
    HStackNode,
    XStackNode,
    BoxBlurNode,
    AudioResampleNode,
    AudioGainNode,
    AudioFadeNode,
    AudioMixNode,
    SidechainCompressNode,
    HighPassFilterNode,
    LoudnessNormalizeNode,
)


def format_ffmpeg_filter_path(file_path: str) -> str:
    """
    Format a Windows filesystem path safely for FFmpeg filter arguments (e.g. ass=filename='...').
    Converts backslashes to forward slashes and escapes drive letter colons (C\\:/...).
    """
    resolved = str(Path(file_path).resolve())
    forward_slash = resolved.replace("\\", "/")
    # Escape colon (e.g. C: -> C\:)
    return forward_slash.replace(":", "\\:")


class FilterCompiler:
    """Compiles individual filter nodes into FFmpeg filter expressions."""

    @classmethod
    def compile_node_filter(cls, node: BaseNode) -> Optional[str]:
        """
        Produce the FFmpeg filter expression string for a supported filter node.
        Returns None for non-filter nodes (such as inputs, outputs, muxers).
        """
        if isinstance(node, VideoTrimNode):
            start_s = node.params["start_us"] / 1_000_000.0
            end_s = node.params["end_us"] / 1_000_000.0
            return f"trim=start={start_s:.3f}:end={end_s:.3f}"

        elif isinstance(node, AudioTrimNode):
            start_s = node.params["start_us"] / 1_000_000.0
            end_s = node.params["end_us"] / 1_000_000.0
            return f"atrim=start={start_s:.3f}:end={end_s:.3f}"

        elif isinstance(node, SetPTSNode):
            expr = node.params.get("expr", "PTS-STARTPTS")
            return f"setpts={expr}"

        elif isinstance(node, SetAPTSNode):
            expr = node.params.get("expr", "PTS-STARTPTS")
            return f"asetpts={expr}"

        elif isinstance(node, FPSNormalizeNode):
            fps = float(node.params["fps"])
            round_mode = node.params.get("round_mode", "near")
            return f"fps=fps={fps:.3f}:round={round_mode}"

        elif isinstance(node, SARNormalizeNode):
            sar = node.params.get("sar", "1/1")
            return f"setsar=sar={sar}"

        elif isinstance(node, CropNode):
            w = int(node.params["width"])
            h = int(node.params["height"])
            x = int(node.params.get("x", 0))
            y = int(node.params.get("y", 0))
            return f"crop=w={w}:h={h}:x={x}:y={y}"

        elif isinstance(node, ScaleNode):
            w = int(node.params["width"])
            h = int(node.params["height"])
            flags = node.params.get("flags", "bicubic")
            return f"scale={w}:{h}:flags={flags}"

        elif isinstance(node, PadNode):
            w = int(node.params["width"])
            h = int(node.params["height"])
            x = int(node.params.get("x", 0))
            y = int(node.params.get("y", 0))
            color = node.params.get("color", "black")
            return f"pad=w={w}:h={h}:x={x}:y={y}:color={color}"

        elif isinstance(node, PixelFormatConvertNode):
            pix_fmt = node.params.get("pixel_format", "yuv420p")
            return f"format={pix_fmt}"

        elif isinstance(node, SubtitleBurnNode):
            raw_path = node.params["ass_file_path"]
            clean_path = format_ffmpeg_filter_path(raw_path)
            return f"ass=filename='{clean_path}'"

        elif isinstance(node, SplitNode):
            cnt = int(node.params.get("outputs_count", 2))
            return f"split={cnt}"

        elif isinstance(node, OverlayNode):
            x = node.params.get("x", 0)
            y = node.params.get("y", 0)
            eof_action = node.params.get("eof_action", "repeat")
            enable = node.params.get("enable")
            if enable:
                return f"overlay=x={x}:y={y}:eof_action={eof_action}:enable='{enable}'"
            return f"overlay=x={x}:y={y}:eof_action={eof_action}"

        elif isinstance(node, VStackNode):
            inputs_count = int(node.params.get("inputs_count", 2))
            return f"vstack=inputs={inputs_count}"

        elif isinstance(node, HStackNode):
            inputs_count = int(node.params.get("inputs_count", 2))
            return f"hstack=inputs={inputs_count}"

        elif isinstance(node, XStackNode):
            inputs_count = int(node.params.get("inputs_count", 4))
            layout = node.params.get("layout", "0_0|w0_0|0_h0|w0_h0")
            return f"xstack=inputs={inputs_count}:layout={layout}"

        elif isinstance(node, BoxBlurNode):
            lr = int(node.params.get("luma_radius", 25))
            lp = int(node.params.get("luma_power", 2))
            return f"boxblur=luma_radius={lr}:luma_power={lp}"

        elif isinstance(node, AudioResampleNode):
            sr = int(node.params.get("sample_rate", 48000))
            return f"aresample={sr}"

        elif isinstance(node, AudioGainNode):
            vol = float(node.params.get("volume", 1.0))
            return f"volume={vol:.3f}"

        elif isinstance(node, AudioFadeNode):
            fade_type = node.params.get("fade_type", "in")
            start_s = node.params.get("start_us", 0) / 1_000_000.0
            dur_s = node.params.get("duration_us", 0) / 1_000_000.0
            return f"afade=t={fade_type}:ss={start_s:.3f}:d={dur_s:.3f}"

        elif isinstance(node, ASplitNode):
            outputs_count = int(node.params.get("outputs_count", 2))
            return f"asplit={outputs_count}"

        elif isinstance(node, AudioMixNode):
            inputs_count = int(node.params.get("inputs_count", 2))
            duration = node.params.get("duration", "first")
            dropout = node.params.get("dropout_transition", 2)
            return f"amix=inputs={inputs_count}:duration={duration}:dropout_transition={dropout}"

        elif isinstance(node, SidechainCompressNode):
            threshold = float(node.params.get("threshold", 0.03125))
            ratio = float(node.params.get("ratio", 4.0))
            attack = float(node.params.get("attack", 50.0))
            release = float(node.params.get("release", 350.0))
            return f"sidechaincompress=threshold={threshold:.5f}:ratio={ratio:.1f}:attack={attack:.1f}:release={release:.1f}"

        elif isinstance(node, HighPassFilterNode):
            freq = int(node.params.get("frequency", 80))
            return f"highpass=f={freq}"

        elif isinstance(node, LoudnessNormalizeNode):
            target_lufs = float(node.params.get("target_lufs", -14.0))
            tp = float(node.params.get("max_true_peak_dbtp", -1.0))
            lra = float(node.params.get("lra", 7.0))
            return f"loudnorm=I={target_lufs:.1f}:TP={tp:.1f}:LRA={lra:.1f}"

        return None
