"""
ClipForge AI - Render Graph Node Definitions & Registry
Phase 9 Stage 3: Typed node definitions, port schemas, and validation rules.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from .stream_registry import Port, PortDirection, StreamType


class UnsupportedNodeError(Exception):
    """Raised when a graph attempts to instantiate an unsupported node type."""
    def __init__(self, node_type: str, reason: str = ""):
        self.node_type = node_type
        self.reason = reason or f"Node type '{node_type}' is planned for a future phase and not supported in Stage 3."
        super().__init__(f"Node type '{node_type}' is unsupported: {self.reason}")


class BaseNode(BaseModel):
    """Abstract base class for all nodes in the render DAG."""
    id: str = Field(..., description="Unique, stable node identifier within the graph")
    node_type: str = Field(..., description="Canonical node type identifier")
    label: Optional[str] = Field(default=None, description="Human-readable label for debugging")
    params: Dict[str, Any] = Field(default_factory=dict, description="Node-specific configuration parameters")
    inputs: List[Port] = Field(default_factory=list, description="Input ports declared by this node")
    outputs: List[Port] = Field(default_factory=list, description="Output ports declared by this node")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Telemetry, layout slot ref, or profiling annotations")

    def get_input_port(self, name: str) -> Optional[Port]:
        for p in self.inputs:
            if p.name == name:
                return p
        return None

    def get_output_port(self, name: str) -> Optional[Port]:
        for p in self.outputs:
            if p.name == name:
                return p
        return None

    def validate_parameters(self) -> List[str]:
        """Validate node-specific configuration. Return list of validation error messages."""
        return []


# =============================================================================
# INPUT NODES
# =============================================================================

class VideoInputNode(BaseNode):
    """Demuxes a video stream from a local source media file."""
    node_type: str = "VideoInput"

    def __init__(self, **data: Any):
        if "inputs" not in data:
            data["inputs"] = []
        if "outputs" not in data:
            data["outputs"] = [
                Port(name="out", stream_type=StreamType.VIDEO, direction=PortDirection.OUTPUT, description="Decoded video frames")
            ]
        data["node_type"] = "VideoInput"
        super().__init__(**data)

    def validate_parameters(self) -> List[str]:
        errors = []
        file_path = self.params.get("file_path")
        if not file_path:
            errors.append(f"Node '{self.id}' (VideoInput) requires 'file_path' in params.")
        return errors


class AudioInputNode(BaseNode):
    """Demuxes an audio stream from a local source media file."""
    node_type: str = "AudioInput"

    def __init__(self, **data: Any):
        if "inputs" not in data:
            data["inputs"] = []
        if "outputs" not in data:
            data["outputs"] = [
                Port(name="out", stream_type=StreamType.AUDIO, direction=PortDirection.OUTPUT, description="Decoded audio samples")
            ]
        data["node_type"] = "AudioInput"
        super().__init__(**data)

    def validate_parameters(self) -> List[str]:
        errors = []
        file_path = self.params.get("file_path")
        if not file_path:
            errors.append(f"Node '{self.id}' (AudioInput) requires 'file_path' in params.")
        return errors


class ImageInputNode(BaseNode):
    """Loads a still image asset."""
    node_type: str = "ImageInput"

    def __init__(self, **data: Any):
        if "inputs" not in data:
            data["inputs"] = []
        if "outputs" not in data:
            data["outputs"] = [
                Port(name="out", stream_type=StreamType.IMAGE, direction=PortDirection.OUTPUT, description="Decoded image buffer")
            ]
        data["node_type"] = "ImageInput"
        super().__init__(**data)

    def validate_parameters(self) -> List[str]:
        errors = []
        file_path = self.params.get("file_path")
        if not file_path:
            errors.append(f"Node '{self.id}' (ImageInput) requires 'file_path' in params.")
        return errors


# =============================================================================
# TIMELINE NODES
# =============================================================================

class VideoTrimNode(BaseNode):
    """Trims a video stream between start_us and end_us."""
    node_type: str = "VideoTrim"

    def __init__(self, **data: Any):
        if "inputs" not in data:
            data["inputs"] = [Port(name="in", stream_type=StreamType.VIDEO, direction=PortDirection.INPUT)]
        if "outputs" not in data:
            data["outputs"] = [Port(name="out", stream_type=StreamType.VIDEO, direction=PortDirection.OUTPUT)]
        data["node_type"] = "VideoTrim"
        super().__init__(**data)

    def validate_parameters(self) -> List[str]:
        errors = []
        start_us = self.params.get("start_us")
        end_us = self.params.get("end_us")
        if start_us is None or end_us is None:
            errors.append(f"Node '{self.id}' (VideoTrim) requires 'start_us' and 'end_us'.")
        elif not isinstance(start_us, int) or not isinstance(end_us, int):
            errors.append(f"Node '{self.id}' (VideoTrim) start_us and end_us must be integers.")
        elif start_us < 0:
            errors.append(f"Node '{self.id}' (VideoTrim) start_us cannot be negative.")
        elif end_us <= start_us:
            errors.append(f"Node '{self.id}' (VideoTrim) end_us ({end_us}) must be greater than start_us ({start_us}).")
        return errors


class AudioTrimNode(BaseNode):
    """Trims an audio stream between start_us and end_us."""
    node_type: str = "AudioTrim"

    def __init__(self, **data: Any):
        if "inputs" not in data:
            data["inputs"] = [Port(name="in", stream_type=StreamType.AUDIO, direction=PortDirection.INPUT)]
        if "outputs" not in data:
            data["outputs"] = [Port(name="out", stream_type=StreamType.AUDIO, direction=PortDirection.OUTPUT)]
        data["node_type"] = "AudioTrim"
        super().__init__(**data)

    def validate_parameters(self) -> List[str]:
        errors = []
        start_us = self.params.get("start_us")
        end_us = self.params.get("end_us")
        if start_us is None or end_us is None:
            errors.append(f"Node '{self.id}' (AudioTrim) requires 'start_us' and 'end_us'.")
        elif not isinstance(start_us, int) or not isinstance(end_us, int):
            errors.append(f"Node '{self.id}' (AudioTrim) start_us and end_us must be integers.")
        elif start_us < 0:
            errors.append(f"Node '{self.id}' (AudioTrim) start_us cannot be negative.")
        elif end_us <= start_us:
            errors.append(f"Node '{self.id}' (AudioTrim) end_us ({end_us}) must be greater than start_us ({start_us}).")
        return errors


class SetPTSNode(BaseNode):
    """Normalizes video presentation timestamps (default PTS-STARTPTS)."""
    node_type: str = "SetPTS"

    def __init__(self, **data: Any):
        if "inputs" not in data:
            data["inputs"] = [Port(name="in", stream_type=StreamType.VIDEO, direction=PortDirection.INPUT)]
        if "outputs" not in data:
            data["outputs"] = [Port(name="out", stream_type=StreamType.VIDEO, direction=PortDirection.OUTPUT)]
        if "params" not in data or "expr" not in data.get("params", {}):
            data.setdefault("params", {})["expr"] = "PTS-STARTPTS"
        data["node_type"] = "SetPTS"
        super().__init__(**data)


class SetAPTSNode(BaseNode):
    """Normalizes audio presentation timestamps (default PTS-STARTPTS)."""
    node_type: str = "SetAPTS"

    def __init__(self, **data: Any):
        if "inputs" not in data:
            data["inputs"] = [Port(name="in", stream_type=StreamType.AUDIO, direction=PortDirection.INPUT)]
        if "outputs" not in data:
            data["outputs"] = [Port(name="out", stream_type=StreamType.AUDIO, direction=PortDirection.OUTPUT)]
        if "params" not in data or "expr" not in data.get("params", {}):
            data.setdefault("params", {})["expr"] = "PTS-STARTPTS"
        data["node_type"] = "SetAPTS"
        super().__init__(**data)


class FPSNormalizeNode(BaseNode):
    """Converts variable framerate (VFR) to constant framerate (CFR)."""
    node_type: str = "FPSNormalize"

    def __init__(self, **data: Any):
        if "inputs" not in data:
            data["inputs"] = [Port(name="in", stream_type=StreamType.VIDEO, direction=PortDirection.INPUT)]
        if "outputs" not in data:
            data["outputs"] = [Port(name="out", stream_type=StreamType.VIDEO, direction=PortDirection.OUTPUT)]
        data["node_type"] = "FPSNormalize"
        super().__init__(**data)

    def validate_parameters(self) -> List[str]:
        errors = []
        fps = self.params.get("fps")
        if fps is None or not (isinstance(fps, (int, float)) and fps > 0):
            errors.append(f"Node '{self.id}' (FPSNormalize) requires positive numeric 'fps'.")
        return errors


# =============================================================================
# VIDEO FILTER NODES
# =============================================================================

class CropNode(BaseNode):
    """Crops a region of video frames (in pixels)."""
    node_type: str = "Crop"

    def __init__(self, **data: Any):
        if "inputs" not in data:
            data["inputs"] = [Port(name="in", stream_type=StreamType.VIDEO, direction=PortDirection.INPUT)]
        if "outputs" not in data:
            data["outputs"] = [Port(name="out", stream_type=StreamType.VIDEO, direction=PortDirection.OUTPUT)]
        data["node_type"] = "Crop"
        super().__init__(**data)

    def validate_parameters(self) -> List[str]:
        errors = []
        w = self.params.get("width")
        h = self.params.get("height")
        if w is None or h is None or w <= 0 or h <= 0:
            errors.append(f"Node '{self.id}' (Crop) requires positive integer width and height.")
        return errors


class ScaleNode(BaseNode):
    """Scales video to target pixel dimensions."""
    node_type: str = "Scale"

    def __init__(self, **data: Any):
        if "inputs" not in data:
            data["inputs"] = [Port(name="in", stream_type=StreamType.VIDEO, direction=PortDirection.INPUT)]
        if "outputs" not in data:
            data["outputs"] = [Port(name="out", stream_type=StreamType.VIDEO, direction=PortDirection.OUTPUT)]
        data["node_type"] = "Scale"
        super().__init__(**data)

    def validate_parameters(self) -> List[str]:
        errors = []
        w = self.params.get("width")
        h = self.params.get("height")
        if w is None or h is None or w <= 0 or h <= 0:
            errors.append(f"Node '{self.id}' (Scale) requires positive integer width and height.")
        return errors


class PadNode(BaseNode):
    """Pads video borders to meet aspect ratio canvas requirements."""
    node_type: str = "Pad"

    def __init__(self, **data: Any):
        if "inputs" not in data:
            data["inputs"] = [Port(name="in", stream_type=StreamType.VIDEO, direction=PortDirection.INPUT)]
        if "outputs" not in data:
            data["outputs"] = [Port(name="out", stream_type=StreamType.VIDEO, direction=PortDirection.OUTPUT)]
        data["node_type"] = "Pad"
        super().__init__(**data)

    def validate_parameters(self) -> List[str]:
        errors = []
        w = self.params.get("width")
        h = self.params.get("height")
        if w is None or h is None or w <= 0 or h <= 0:
            errors.append(f"Node '{self.id}' (Pad) requires positive integer width and height.")
        return errors


class SARNormalizeNode(BaseNode):
    """Forces Sample Aspect Ratio (SAR) to 1:1 square pixels."""
    node_type: str = "SARNormalize"

    def __init__(self, **data: Any):
        if "inputs" not in data:
            data["inputs"] = [Port(name="in", stream_type=StreamType.VIDEO, direction=PortDirection.INPUT)]
        if "outputs" not in data:
            data["outputs"] = [Port(name="out", stream_type=StreamType.VIDEO, direction=PortDirection.OUTPUT)]
        if "params" not in data or "sar" not in data.get("params", {}):
            data.setdefault("params", {})["sar"] = "1/1"
        data["node_type"] = "SARNormalize"
        super().__init__(**data)


class PixelFormatConvertNode(BaseNode):
    """Converts pixel format (default yuv420p for standard H.264 playback)."""
    node_type: str = "PixelFormatConvert"

    def __init__(self, **data: Any):
        if "inputs" not in data:
            data["inputs"] = [Port(name="in", stream_type=StreamType.VIDEO, direction=PortDirection.INPUT)]
        if "outputs" not in data:
            data["outputs"] = [Port(name="out", stream_type=StreamType.VIDEO, direction=PortDirection.OUTPUT)]
        if "params" not in data or "pixel_format" not in data.get("params", {}):
            data.setdefault("params", {})["pixel_format"] = "yuv420p"
        data["node_type"] = "PixelFormatConvert"
        super().__init__(**data)


class SubtitleBurnNode(BaseNode):
    """Burns Advanced SubStation Alpha (.ass) subtitles onto the video stream."""
    node_type: str = "SubtitleBurn"

    def __init__(self, **data: Any):
        if "inputs" not in data:
            data["inputs"] = [Port(name="in", stream_type=StreamType.VIDEO, direction=PortDirection.INPUT)]
        if "outputs" not in data:
            data["outputs"] = [Port(name="out", stream_type=StreamType.VIDEO, direction=PortDirection.OUTPUT)]
        data["node_type"] = "SubtitleBurn"
        super().__init__(**data)

    def validate_parameters(self) -> List[str]:
        errors = []
        ass_path = self.params.get("ass_file_path")
        if not ass_path:
            errors.append(f"Node '{self.id}' (SubtitleBurn) requires 'ass_file_path'.")
        return errors


class SplitNode(BaseNode):
    """Duplicates a single video stream into N parallel identical streams."""
    node_type: str = "Split"

    def __init__(self, **data: Any):
        outputs_count = int(data.get("params", {}).get("outputs_count", 2))
        if "inputs" not in data:
            data["inputs"] = [Port(name="in", stream_type=StreamType.VIDEO, direction=PortDirection.INPUT)]
        if "outputs" not in data:
            data["outputs"] = [
                Port(name=f"out_{i}", stream_type=StreamType.VIDEO, direction=PortDirection.OUTPUT)
                for i in range(outputs_count)
            ]
        data.setdefault("params", {})["outputs_count"] = outputs_count
        data["node_type"] = "Split"
        super().__init__(**data)

    def validate_parameters(self) -> List[str]:
        errors = []
        cnt = self.params.get("outputs_count", 2)
        if not isinstance(cnt, int) or cnt < 2:
            errors.append(f"Node '{self.id}' (Split) outputs_count must be an integer >= 2.")
        return errors


class OverlayNode(BaseNode):
    """Overlays one video stream onto a background stream."""
    node_type: str = "Overlay"

    def __init__(self, **data: Any):
        if "inputs" not in data:
            data["inputs"] = [
                Port(name="main_in", stream_type=StreamType.VIDEO, direction=PortDirection.INPUT),
                Port(name="overlay_in", stream_type=StreamType.VIDEO, direction=PortDirection.INPUT),
            ]
        if "outputs" not in data:
            data["outputs"] = [Port(name="out", stream_type=StreamType.VIDEO, direction=PortDirection.OUTPUT)]
        data["node_type"] = "Overlay"
        super().__init__(**data)


class VStackNode(BaseNode):
    """Stacks N video streams vertically."""
    node_type: str = "VStack"

    def __init__(self, **data: Any):
        inputs_count = int(data.get("params", {}).get("inputs_count", 2))
        if "inputs" not in data:
            data["inputs"] = [
                Port(name=f"in_{i}", stream_type=StreamType.VIDEO, direction=PortDirection.INPUT)
                for i in range(inputs_count)
            ]
        if "outputs" not in data:
            data["outputs"] = [Port(name="out", stream_type=StreamType.VIDEO, direction=PortDirection.OUTPUT)]
        data.setdefault("params", {})["inputs_count"] = inputs_count
        data["node_type"] = "VStack"
        super().__init__(**data)


class HStackNode(BaseNode):
    """Stacks N video streams horizontally."""
    node_type: str = "HStack"

    def __init__(self, **data: Any):
        inputs_count = int(data.get("params", {}).get("inputs_count", 2))
        if "inputs" not in data:
            data["inputs"] = [
                Port(name=f"in_{i}", stream_type=StreamType.VIDEO, direction=PortDirection.INPUT)
                for i in range(inputs_count)
            ]
        if "outputs" not in data:
            data["outputs"] = [Port(name="out", stream_type=StreamType.VIDEO, direction=PortDirection.OUTPUT)]
        data.setdefault("params", {})["inputs_count"] = inputs_count
        data["node_type"] = "HStack"
        super().__init__(**data)


class XStackNode(BaseNode):
    """Composites N video streams into a multi-panel custom grid layout."""
    node_type: str = "XStack"

    def __init__(self, **data: Any):
        inputs_count = int(data.get("params", {}).get("inputs_count", 4))
        if "inputs" not in data:
            data["inputs"] = [
                Port(name=f"in_{i}", stream_type=StreamType.VIDEO, direction=PortDirection.INPUT)
                for i in range(inputs_count)
            ]
        if "outputs" not in data:
            data["outputs"] = [Port(name="out", stream_type=StreamType.VIDEO, direction=PortDirection.OUTPUT)]
        data.setdefault("params", {})["inputs_count"] = inputs_count
        data["node_type"] = "XStack"
        super().__init__(**data)

    def validate_parameters(self) -> List[str]:
        errors = []
        if "layout" not in self.params:
            errors.append(f"Node '{self.id}' (XStack) requires 'layout' parameter string.")
        return errors


class BoxBlurNode(BaseNode):
    """Applies box blur filter to video stream (typically for blurred background landscape)."""
    node_type: str = "BoxBlur"

    def __init__(self, **data: Any):
        if "inputs" not in data:
            data["inputs"] = [Port(name="in", stream_type=StreamType.VIDEO, direction=PortDirection.INPUT)]
        if "outputs" not in data:
            data["outputs"] = [Port(name="out", stream_type=StreamType.VIDEO, direction=PortDirection.OUTPUT)]
        data.setdefault("params", {}).setdefault("luma_radius", 25)
        data.setdefault("params", {}).setdefault("luma_power", 2)
        data["node_type"] = "BoxBlur"
        super().__init__(**data)


class VideoOutputNode(BaseNode):
    """Final video stream endpoint feeding into container muxer."""
    node_type: str = "VideoOutput"

    def __init__(self, **data: Any):
        if "inputs" not in data:
            data["inputs"] = [Port(name="in", stream_type=StreamType.VIDEO, direction=PortDirection.INPUT)]
        if "outputs" not in data:
            data["outputs"] = [Port(name="out", stream_type=StreamType.ENCODED_OUTPUT, direction=PortDirection.OUTPUT)]
        if "params" not in data or "label" not in data.get("params", {}):
            data.setdefault("params", {})["label"] = "v_out"
        data["node_type"] = "VideoOutput"
        super().__init__(**data)


# =============================================================================
# AUDIO FILTER NODES
# =============================================================================

class AudioResampleNode(BaseNode):
    """Resamples audio stream to a uniform sample rate (e.g. 48000 Hz)."""
    node_type: str = "AudioResample"

    def __init__(self, **data: Any):
        if "inputs" not in data:
            data["inputs"] = [Port(name="in", stream_type=StreamType.AUDIO, direction=PortDirection.INPUT)]
        if "outputs" not in data:
            data["outputs"] = [Port(name="out", stream_type=StreamType.AUDIO, direction=PortDirection.OUTPUT)]
        if "params" not in data or "sample_rate" not in data.get("params", {}):
            data.setdefault("params", {})["sample_rate"] = 48000
        data["node_type"] = "AudioResample"
        super().__init__(**data)

    def validate_parameters(self) -> List[str]:
        errors = []
        sr = self.params.get("sample_rate", 48000)
        if not (isinstance(sr, int) and sr in (16000, 22050, 44100, 48000, 96000)):
            errors.append(f"Node '{self.id}' (AudioResample) sample_rate must be a valid audio rate (e.g. 44100, 48000).")
        return errors


class AudioGainNode(BaseNode):
    """Adjusts volume level of an audio stream."""
    node_type: str = "AudioGain"

    def __init__(self, **data: Any):
        if "inputs" not in data:
            data["inputs"] = [Port(name="in", stream_type=StreamType.AUDIO, direction=PortDirection.INPUT)]
        if "outputs" not in data:
            data["outputs"] = [Port(name="out", stream_type=StreamType.AUDIO, direction=PortDirection.OUTPUT)]
        data["node_type"] = "AudioGain"
        super().__init__(**data)

    def validate_parameters(self) -> List[str]:
        errors = []
        vol = self.params.get("volume", 1.0)
        if not (isinstance(vol, (int, float)) and 0.0 <= vol <= 10.0):
            errors.append(f"Node '{self.id}' (AudioGain) volume must be between 0.0 and 10.0.")
        return errors


class AudioFadeNode(BaseNode):
    """Applies audio fade-in or fade-out."""
    node_type: str = "AudioFade"

    def __init__(self, **data: Any):
        if "inputs" not in data:
            data["inputs"] = [Port(name="in", stream_type=StreamType.AUDIO, direction=PortDirection.INPUT)]
        if "outputs" not in data:
            data["outputs"] = [Port(name="out", stream_type=StreamType.AUDIO, direction=PortDirection.OUTPUT)]
        data["node_type"] = "AudioFade"
        super().__init__(**data)

    def validate_parameters(self) -> List[str]:
        errors = []
        fade_type = self.params.get("fade_type", "in")
        if fade_type not in ("in", "out"):
            errors.append(f"Node '{self.id}' (AudioFade) fade_type must be 'in' or 'out'.")
        return errors


class HighPassFilterNode(BaseNode):
    """High-pass (low-cut) rumble audio filter."""
    node_type: str = "HighPassFilter"

    def __init__(self, **data: Any):
        if "inputs" not in data:
            data["inputs"] = [Port(name="in", stream_type=StreamType.AUDIO, direction=PortDirection.INPUT)]
        if "outputs" not in data:
            data["outputs"] = [Port(name="out", stream_type=StreamType.AUDIO, direction=PortDirection.OUTPUT)]
        data["node_type"] = "HighPassFilter"
        super().__init__(**data)


class ASplitNode(BaseNode):
    """Splits an audio stream into N identical audio streams."""
    node_type: str = "ASplit"

    def __init__(self, **data: Any):
        outputs_count = int(data.get("params", {}).get("outputs_count", 2))
        if "inputs" not in data:
            data["inputs"] = [Port(name="in", stream_type=StreamType.AUDIO, direction=PortDirection.INPUT)]
        if "outputs" not in data:
            data["outputs"] = [
                Port(name=f"out_{i}", stream_type=StreamType.AUDIO, direction=PortDirection.OUTPUT)
                for i in range(outputs_count)
            ]
        data["node_type"] = "ASplit"
        super().__init__(**data)


class AudioMixNode(BaseNode):
    """Mixes N audio streams into a single composite audio stream."""
    node_type: str = "AudioMix"

    def __init__(self, **data: Any):
        inputs_count = int(data.get("params", {}).get("inputs_count", 2))
        if "inputs" not in data:
            data["inputs"] = [
                Port(name=f"in_{i}", stream_type=StreamType.AUDIO, direction=PortDirection.INPUT)
                for i in range(inputs_count)
            ]
        if "outputs" not in data:
            data["outputs"] = [Port(name="out", stream_type=StreamType.AUDIO, direction=PortDirection.OUTPUT)]
        data["node_type"] = "AudioMix"
        super().__init__(**data)


class SidechainCompressNode(BaseNode):
    """Applies sidechain compression ducking to main audio using sidechain signal."""
    node_type: str = "SidechainCompress"

    def __init__(self, **data: Any):
        if "inputs" not in data:
            data["inputs"] = [
                Port(name="main_in", stream_type=StreamType.AUDIO, direction=PortDirection.INPUT),
                Port(name="sidechain_in", stream_type=StreamType.AUDIO, direction=PortDirection.INPUT),
            ]
        if "outputs" not in data:
            data["outputs"] = [Port(name="out", stream_type=StreamType.AUDIO, direction=PortDirection.OUTPUT)]
        data["node_type"] = "SidechainCompress"
        super().__init__(**data)


class LoudnessNormalizeNode(BaseNode):
    """EBU R128 two-pass / single-pass broadcast loudness normalization filter."""
    node_type: str = "LoudnessNormalize"

    def __init__(self, **data: Any):
        if "inputs" not in data:
            data["inputs"] = [Port(name="in", stream_type=StreamType.AUDIO, direction=PortDirection.INPUT)]
        if "outputs" not in data:
            data["outputs"] = [Port(name="out", stream_type=StreamType.AUDIO, direction=PortDirection.OUTPUT)]
        if "params" not in data or "target_lufs" not in data.get("params", {}):
            data.setdefault("params", {})["target_lufs"] = -14.0
            data.setdefault("params", {})["max_true_peak_dbtp"] = -1.0
            data.setdefault("params", {})["lra"] = 7.0
        data["node_type"] = "LoudnessNormalize"
        super().__init__(**data)


class AudioOutputNode(BaseNode):
    """Final audio stream endpoint feeding into container muxer."""
    node_type: str = "AudioOutput"

    def __init__(self, **data: Any):
        if "inputs" not in data:
            data["inputs"] = [Port(name="in", stream_type=StreamType.AUDIO, direction=PortDirection.INPUT)]
        if "outputs" not in data:
            data["outputs"] = [Port(name="out", stream_type=StreamType.ENCODED_OUTPUT, direction=PortDirection.OUTPUT)]
        if "params" not in data or "label" not in data.get("params", {}):
            data.setdefault("params", {})["label"] = "a_out"
        data["node_type"] = "AudioOutput"
        super().__init__(**data)


# =============================================================================
# MUXING & CONTAINER NODES
# =============================================================================

class VideoAudioMuxNode(BaseNode):
    """Muxes a finalized video stream and audio stream into a single output stream."""
    node_type: str = "VideoAudioMux"

    def __init__(self, **data: Any):
        if "inputs" not in data:
            data["inputs"] = [
                Port(name="video", stream_type=StreamType.ENCODED_OUTPUT, direction=PortDirection.INPUT),
                Port(name="audio", stream_type=StreamType.ENCODED_OUTPUT, direction=PortDirection.INPUT)
            ]
        if "outputs" not in data:
            data["outputs"] = [Port(name="out", stream_type=StreamType.ENCODED_OUTPUT, direction=PortDirection.OUTPUT)]
        data["node_type"] = "VideoAudioMux"
        super().__init__(**data)


class OutputContainerNode(BaseNode):
    """Final output container file destination."""
    node_type: str = "OutputContainer"

    def __init__(self, **data: Any):
        if "inputs" not in data:
            data["inputs"] = [Port(name="in", stream_type=StreamType.ENCODED_OUTPUT, direction=PortDirection.INPUT)]
        if "outputs" not in data:
            data["outputs"] = []
        data["node_type"] = "OutputContainer"
        super().__init__(**data)

    def validate_parameters(self) -> List[str]:
        errors = []
        path = self.params.get("output_path")
        if not path:
            errors.append(f"Node '{self.id}' (OutputContainer) requires 'output_path'.")
        return errors


# =============================================================================
# NODE REGISTRY & UNSUPPORTED CHECK
# =============================================================================

NODE_REGISTRY: Dict[str, type] = {
    "VideoInput": VideoInputNode,
    "AudioInput": AudioInputNode,
    "ImageInput": ImageInputNode,
    "VideoTrim": VideoTrimNode,
    "AudioTrim": AudioTrimNode,
    "SetPTS": SetPTSNode,
    "SetAPTS": SetAPTSNode,
    "FPSNormalize": FPSNormalizeNode,
    "Crop": CropNode,
    "Scale": ScaleNode,
    "Pad": PadNode,
    "SARNormalize": SARNormalizeNode,
    "PixelFormatConvert": PixelFormatConvertNode,
    "SubtitleBurn": SubtitleBurnNode,
    "Split": SplitNode,
    "ASplit": ASplitNode,
    "Overlay": OverlayNode,
    "VStack": VStackNode,
    "HStack": HStackNode,
    "XStack": XStackNode,
    "BoxBlur": BoxBlurNode,
    "VideoOutput": VideoOutputNode,
    "AudioResample": AudioResampleNode,
    "AudioGain": AudioGainNode,
    "AudioFade": AudioFadeNode,
    "AudioMix": AudioMixNode,
    "SidechainCompress": SidechainCompressNode,
    "HighPassFilter": HighPassFilterNode,
    "LoudnessNormalize": LoudnessNormalizeNode,
    "AudioOutput": AudioOutputNode,
    "VideoAudioMux": VideoAudioMuxNode,
    "OutputContainer": OutputContainerNode,
}

UNSUPPORTED_NODES = {
    "Transition": "Dynamic scene transitions will be implemented in Phase 9 Stage 6.",
    "PictureInPicture": "PiP composite rendering will be implemented via Overlay/Scale.",
    "ColorAdjustment": "LUT and color correction will be implemented in Phase 9 Stage 7.",
    "SidechainDucking": "Automated sidechain music ducking will be implemented in Phase 9 Stage 8.",
}


def create_node(node_type: str, **kwargs: Any) -> BaseNode:
    """Factory creating a typed node, rejecting unsupported or unknown node types."""
    if node_type in UNSUPPORTED_NODES:
        raise UnsupportedNodeError(node_type, UNSUPPORTED_NODES[node_type])
    if node_type not in NODE_REGISTRY:
        raise ValueError(f"Unknown node type: '{node_type}'. Supported types: {list(NODE_REGISTRY.keys())}")
    cls = NODE_REGISTRY[node_type]
    return cls(**kwargs)
