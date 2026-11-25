"""
ClipForge AI - Composition Spec to Render Graph Builder
Phase 9 Stage 3: Adapter translating immutable CompositionSpec AST into a validated RenderGraph.
"""

from typing import Dict, Optional
from pathlib import Path

from ...schemas.composition import CompositionSpec
from ...schemas.layout import LayoutConfig
from .graph import RenderGraph
from .nodes import (
    VideoInputNode,
    AudioInputNode,
    ImageInputNode,
    VideoTrimNode,
    AudioTrimNode,
    SetPTSNode,
    SetAPTSNode,
    FPSNormalizeNode,
    CropNode,
    ScaleNode,
    PadNode,
    SplitNode,
    ASplitNode,
    OverlayNode,
    VStackNode,
    HStackNode,
    BoxBlurNode,
    SARNormalizeNode,
    PixelFormatConvertNode,
    SubtitleBurnNode,
    VideoOutputNode,
    AudioResampleNode,
    AudioGainNode,
    AudioFadeNode,
    AudioMixNode,
    SidechainCompressNode,
    HighPassFilterNode,
    LoudnessNormalizeNode,
    AudioOutputNode,
    VideoAudioMuxNode,
    OutputContainerNode,
)
from app.composition.overlays.overlay_planner import OverlayPlanner
from app.composition.audio.audio_mixer import db_to_linear, AudioMixPlanner


class UnsupportedCompositionFeatureError(Exception):
    """Raised when a composition requests a feature not yet supported in the current stage."""
    def __init__(self, feature: str, message: str = ""):
        self.feature = feature
        self.message = message or f"Feature '{feature}' is not supported in the Stage 3 render graph."
        super().__init__(self.message)


class CompositionToGraphBuilder:
    """Builds an explicit, typed RenderGraph from a validated CompositionSpec AST."""

    @classmethod
    def build_graph(
        cls,
        spec: CompositionSpec,
        source_media_path: str,
        output_file_path: str,
        ass_subtitle_path: Optional[str] = None,
        graph_id: Optional[str] = None,
        asset_resolver: Optional[Dict[str, str]] = None,
    ) -> RenderGraph:
        """
        Transform CompositionSpec into a full DAG.
        Verifies feature support, calculates crop dimensions, and wires video & audio pipelines.
        """
        # 1. Feature Support Guard
        layout_type = getattr(spec.layout, "layout_type", None) or getattr(spec.layout, "topology", "single_full_frame")
        supported_layouts = (
            "single_full_frame",
            "portrait_crop",
            "split_vertical",
            "split_horizontal",
            "blurred_background",
            "picture_in_picture",
        )
        if layout_type not in supported_layouts:
            raise UnsupportedCompositionFeatureError(
                feature=f"layout_type:{layout_type}",
                message=(
                    f"Layout '{layout_type}' is unsupported. "
                    f"Supported topologies: {', '.join(supported_layouts)}."
                )
            )

        comp_id = getattr(spec, "composition_id", None) or (spec.metadata.get("id") if isinstance(getattr(spec, "metadata", None), dict) else getattr(getattr(spec, "metadata", None), "id", "comp"))
        comp_title = getattr(spec, "title", None) or (spec.metadata.get("title") if isinstance(getattr(spec, "metadata", None), dict) else getattr(getattr(spec, "metadata", None), "title", "Composition"))

        gid = graph_id or f"graph_{str(comp_id)[:8]}"
        graph = RenderGraph(id=gid, name=f"RenderGraph_{comp_title}")

        # 2. Extract Boundary & Resolution Information
        delivery = getattr(spec, "delivery_profile", None) or getattr(spec, "delivery", None)
        if not delivery:
            from ...schemas.delivery import get_default_delivery_profile
            delivery = get_default_delivery_profile()

        src_w = spec.source_media.width
        src_h = spec.source_media.height
        dst_w = delivery.width
        dst_h = delivery.height

        boundary = getattr(spec, "clip_boundary", None) or getattr(getattr(spec, "timeline", None), "composition_boundary", None)
        start_us = getattr(boundary, "source_start_us", getattr(boundary, "in_point_us", 0)) if boundary else 0
        end_us = getattr(boundary, "source_end_us", getattr(boundary, "out_point_us", 1000000)) if boundary else getattr(getattr(spec, "timeline", None), "total_duration_us", 1000000)
        
        # FPS handling
        fps_attr = delivery.fps
        fps_val = fps_attr.fps if hasattr(fps_attr, "fps") else float(fps_attr)

        # 3. Create Input Nodes
        v_in = VideoInputNode(id="node_v_in", params={"file_path": source_media_path})
        a_in = AudioInputNode(id="node_a_in", params={"file_path": source_media_path})
        graph.add_node(v_in)
        graph.add_node(a_in)

        # 4. Video Pipeline
        v_trim = VideoTrimNode(id="node_v_trim", params={"start_us": start_us, "end_us": end_us})
        v_pts = SetPTSNode(id="node_v_pts", params={"expr": "PTS-STARTPTS"})
        v_fps = FPSNormalizeNode(id="node_v_fps", params={"fps": fps_val, "round_mode": "near"})
        v_sar = SARNormalizeNode(id="node_v_sar", params={"sar": "1/1"})

        graph.add_node(v_trim)
        graph.add_node(v_pts)
        graph.add_node(v_fps)
        graph.add_node(v_sar)

        graph.add_edge("node_v_in", "out", "node_v_trim", "in", stream_label="[v_raw]")
        graph.add_edge("node_v_trim", "out", "node_v_pts", "in", stream_label="[v_trim]")
        graph.add_edge("node_v_pts", "out", "node_v_fps", "in", stream_label="[v_pts]")
        graph.add_edge("node_v_fps", "out", "node_v_sar", "in", stream_label="[v_fps]")

        last_v_node = "node_v_sar"
        last_v_port = "out"
        last_v_label = "[v_sar]"

        if layout_type in ("single_full_frame", "portrait_crop"):
            target_aspect = dst_w / dst_h
            source_aspect = src_w / src_h

            if source_aspect > target_aspect:
                crop_h = src_h
                crop_w = int(src_h * target_aspect)
                if crop_w % 2 != 0:
                    crop_w -= 1
                center_x = src_w / 2.0
                camera_obj = getattr(spec, "camera", None) or getattr(spec, "camera_plan", None)
                if camera_obj and getattr(camera_obj, "keyframes", None):
                    kf0 = camera_obj.keyframes[0]
                    rect = getattr(kf0, "crop_rect", getattr(kf0, "viewport", None))
                    if rect:
                        center_x = (rect.x + rect.width / 2.0) * src_w
                crop_x = int(max(0, min(src_w - crop_w, center_x - crop_w / 2.0)))
                crop_y = 0
            else:
                crop_w = src_w
                crop_h = int(src_w / target_aspect)
                if crop_h % 2 != 0:
                    crop_h -= 1
                crop_x = 0
                crop_y = int(max(0, (src_h - crop_h) / 2))

            v_crop = CropNode(id="node_v_crop", params={"width": crop_w, "height": crop_h, "x": crop_x, "y": crop_y})
            v_scale = ScaleNode(id="node_v_scale", params={"width": dst_w, "height": dst_h, "flags": "bicubic"})
            graph.add_node(v_crop)
            graph.add_node(v_scale)
            graph.add_edge(last_v_node, last_v_port, "node_v_crop", "in", stream_label=last_v_label)
            graph.add_edge("node_v_crop", "out", "node_v_scale", "in", stream_label="[v_crop]")
            last_v_node = "node_v_scale"
            last_v_port = "out"
            last_v_label = "[v_scaled]"

        elif layout_type == "split_vertical":
            slot_h = dst_h // 2
            slot_aspect = dst_w / slot_h

            v_split = SplitNode(id="node_v_split", params={"outputs_count": 2})
            graph.add_node(v_split)
            graph.add_edge(last_v_node, last_v_port, "node_v_split", "in", stream_label=last_v_label)

            # Top slot
            crop_w0 = int(src_h * slot_aspect)
            if crop_w0 > src_w:
                crop_w0 = src_w
            crop_w0 = crop_w0 - (crop_w0 % 2)
            crop_x0 = int(max(0, min(src_w - crop_w0, src_w * 0.25 - crop_w0 / 2.0)))
            v_crop0 = CropNode(id="node_v_crop_0", params={"width": crop_w0, "height": src_h, "x": crop_x0, "y": 0})
            v_scale0 = ScaleNode(id="node_v_scale_0", params={"width": dst_w, "height": slot_h, "flags": "bicubic"})
            graph.add_node(v_crop0)
            graph.add_node(v_scale0)
            graph.add_edge("node_v_split", "out_0", "node_v_crop_0", "in", stream_label="[v_sp0]")
            graph.add_edge("node_v_crop_0", "out", "node_v_scale_0", "in", stream_label="[v_cr0]")

            # Bottom slot
            crop_x1 = int(max(0, min(src_w - crop_w0, src_w * 0.75 - crop_w0 / 2.0)))
            v_crop1 = CropNode(id="node_v_crop_1", params={"width": crop_w0, "height": src_h, "x": crop_x1, "y": 0})
            v_scale1 = ScaleNode(id="node_v_scale_1", params={"width": dst_w, "height": slot_h, "flags": "bicubic"})
            graph.add_node(v_crop1)
            graph.add_node(v_scale1)
            graph.add_edge("node_v_split", "out_1", "node_v_crop_1", "in", stream_label="[v_sp1]")
            graph.add_edge("node_v_crop_1", "out", "node_v_scale_1", "in", stream_label="[v_cr1]")

            # Vertical stack
            v_stack = VStackNode(id="node_v_stack", params={"inputs_count": 2})
            graph.add_node(v_stack)
            graph.add_edge("node_v_scale_0", "out", "node_v_stack", "in_0", stream_label="[v_top]")
            graph.add_edge("node_v_scale_1", "out", "node_v_stack", "in_1", stream_label="[v_bot]")
            last_v_node = "node_v_stack"
            last_v_port = "out"
            last_v_label = "[v_stacked]"

        elif layout_type == "split_horizontal":
            slot_w = dst_w // 2
            slot_aspect = slot_w / dst_h

            v_split = SplitNode(id="node_v_split", params={"outputs_count": 2})
            graph.add_node(v_split)
            graph.add_edge(last_v_node, last_v_port, "node_v_split", "in", stream_label=last_v_label)

            crop_w = int(src_h * slot_aspect)
            crop_w = crop_w - (crop_w % 2)
            crop_x0 = int(max(0, min(src_w - crop_w, src_w * 0.3 - crop_w / 2.0)))
            v_crop0 = CropNode(id="node_v_crop_0", params={"width": crop_w, "height": src_h, "x": crop_x0, "y": 0})
            v_scale0 = ScaleNode(id="node_v_scale_0", params={"width": slot_w, "height": dst_h, "flags": "bicubic"})
            graph.add_node(v_crop0)
            graph.add_node(v_scale0)
            graph.add_edge("node_v_split", "out_0", "node_v_crop_0", "in", stream_label="[v_sp0]")
            graph.add_edge("node_v_crop_0", "out", "node_v_scale_0", "in", stream_label="[v_cr0]")

            crop_x1 = int(max(0, min(src_w - crop_w, src_w * 0.7 - crop_w / 2.0)))
            v_crop1 = CropNode(id="node_v_crop_1", params={"width": crop_w, "height": src_h, "x": crop_x1, "y": 0})
            v_scale1 = ScaleNode(id="node_v_scale_1", params={"width": slot_w, "height": dst_h, "flags": "bicubic"})
            graph.add_node(v_crop1)
            graph.add_node(v_scale1)
            graph.add_edge("node_v_split", "out_1", "node_v_crop_1", "in", stream_label="[v_sp1]")
            graph.add_edge("node_v_crop_1", "out", "node_v_scale_1", "in", stream_label="[v_cr1]")

            v_stack = HStackNode(id="node_v_stack", params={"inputs_count": 2})
            graph.add_node(v_stack)
            graph.add_edge("node_v_scale_0", "out", "node_v_stack", "in_0", stream_label="[v_left]")
            graph.add_edge("node_v_scale_1", "out", "node_v_stack", "in_1", stream_label="[v_right]")
            last_v_node = "node_v_stack"
            last_v_port = "out"
            last_v_label = "[v_stacked]"

        elif layout_type == "blurred_background":
            v_split = SplitNode(id="node_v_split", params={"outputs_count": 2})
            graph.add_node(v_split)
            graph.add_edge(last_v_node, last_v_port, "node_v_split", "in", stream_label=last_v_label)

            # Background branch
            v_bg_scale = ScaleNode(id="node_v_bg_scale", params={"width": dst_w, "height": dst_h, "flags": "bicubic"})
            v_bg_blur = BoxBlurNode(id="node_v_bg_blur", params={"luma_radius": 25, "luma_power": 2})
            graph.add_node(v_bg_scale)
            graph.add_node(v_bg_blur)
            graph.add_edge("node_v_split", "out_0", "node_v_bg_scale", "in", stream_label="[v_bg_in]")
            graph.add_edge("node_v_bg_scale", "out", "node_v_bg_blur", "in", stream_label="[v_bg_sc]")

            # Foreground branch
            fg_h = int(dst_w / (src_w / src_h))
            fg_h = fg_h - (fg_h % 2)
            v_fg_scale = ScaleNode(id="node_v_fg_scale", params={"width": dst_w, "height": fg_h, "flags": "bicubic"})
            graph.add_node(v_fg_scale)
            graph.add_edge("node_v_split", "out_1", "node_v_fg_scale", "in", stream_label="[v_fg_in]")

            # Overlay centered
            v_overlay = OverlayNode(id="node_v_overlay", params={"x": "(W-w)/2", "y": "(H-h)/2"})
            graph.add_node(v_overlay)
            graph.add_edge("node_v_bg_blur", "out", "node_v_overlay", "main_in", stream_label="[v_bg]")
            graph.add_edge("node_v_fg_scale", "out", "node_v_overlay", "overlay_in", stream_label="[v_fg]")
            last_v_node = "node_v_overlay"
            last_v_port = "out"
            last_v_label = "[v_overlaid]"

        elif layout_type == "picture_in_picture":
            v_split = SplitNode(id="node_v_split", params={"outputs_count": 2})
            graph.add_node(v_split)
            graph.add_edge(last_v_node, last_v_port, "node_v_split", "in", stream_label=last_v_label)

            # Main branch
            crop_w = int(src_h * (dst_w / dst_h))
            crop_w = crop_w - (crop_w % 2)
            crop_x = int(max(0, (src_w - crop_w) / 2))
            v_main_crop = CropNode(id="node_v_main_crop", params={"width": crop_w, "height": src_h, "x": crop_x, "y": 0})
            v_main_scale = ScaleNode(id="node_v_main_scale", params={"width": dst_w, "height": dst_h, "flags": "bicubic"})
            graph.add_node(v_main_crop)
            graph.add_node(v_main_scale)
            graph.add_edge("node_v_split", "out_0", "node_v_main_crop", "in", stream_label="[v_m_in]")
            graph.add_edge("node_v_main_crop", "out", "node_v_main_scale", "in", stream_label="[v_m_cr]")

            # PiP Inset branch
            pip_w = 360
            pip_h = 480
            pip_crop_w = int(src_h * (pip_w / pip_h))
            pip_crop_w = pip_crop_w - (pip_crop_w % 2)
            pip_crop_x = int(max(0, src_w * 0.75 - pip_crop_w / 2.0))
            v_pip_crop = CropNode(id="node_v_pip_crop", params={"width": pip_crop_w, "height": src_h, "x": pip_crop_x, "y": 0})
            v_pip_scale = ScaleNode(id="node_v_pip_scale", params={"width": pip_w, "height": pip_h, "flags": "bicubic"})
            graph.add_node(v_pip_crop)
            graph.add_node(v_pip_scale)
            graph.add_edge("node_v_split", "out_1", "node_v_pip_crop", "in", stream_label="[v_p_in]")
            graph.add_edge("node_v_pip_crop", "out", "node_v_pip_scale", "in", stream_label="[v_p_cr]")

            v_overlay = OverlayNode(id="node_v_pip_overlay", params={"x": "W-w-36", "y": "36"})
            graph.add_node(v_overlay)
            graph.add_edge("node_v_main_scale", "out", "node_v_pip_overlay", "main_in", stream_label="[v_main]")
            graph.add_edge("node_v_pip_scale", "out", "node_v_pip_overlay", "overlay_in", stream_label="[v_pip]")
            last_v_node = "node_v_pip_overlay"
            last_v_port = "out"
            last_v_label = "[v_pip_out]"

        # Process B-roll and Graphic Overlays
        overlays_cfg = getattr(spec, "overlays", None)
        if overlays_cfg:
            def _resolve_path(uri: str) -> str:
                if asset_resolver and uri in asset_resolver:
                    return asset_resolver[uri]
                if Path(uri).exists():
                    return uri
                cleaned = uri.replace("asset://", "")
                return str(Path(cleaned).resolve())

            # 1. B-roll cutaway and PiP inserts
            for b_idx, broll_item in enumerate(getattr(overlays_cfg, "b_roll_items", [])):
                broll_path = _resolve_path(broll_item.asset_uri)
                if not Path(broll_path).exists():
                    continue

                resolved = OverlayPlanner.resolve_broll_placement(
                    spec=broll_item,
                    canvas_width=dst_w,
                    canvas_height=dst_h,
                )

                b_in = VideoInputNode(id=f"node_broll_in_{b_idx}", params={"file_path": broll_path})
                b_trim = VideoTrimNode(id=f"node_broll_trim_{b_idx}", params={
                    "start_us": broll_item.source_offset_us,
                    "end_us": broll_item.source_offset_us + broll_item.duration_us,
                })
                b_pts = SetPTSNode(id=f"node_broll_pts_{b_idx}", params={
                    "expr": f"PTS-STARTPTS+{broll_item.timeline_start_seconds}/TB"
                })
                b_fps = FPSNormalizeNode(id=f"node_broll_fps_{b_idx}", params={"fps": fps_val, "round_mode": "near"})
                b_scale = ScaleNode(id=f"node_broll_scale_{b_idx}", params={
                    "width": resolved.target_width,
                    "height": resolved.target_height,
                    "flags": "bicubic"
                })
                b_overlay = OverlayNode(id=f"node_broll_overlay_{b_idx}", params={
                    "x": resolved.x_expr,
                    "y": resolved.y_expr,
                    "enable": resolved.enable_expr,
                    "eof_action": "pass"
                })

                graph.add_node(b_in)
                graph.add_node(b_trim)
                graph.add_node(b_pts)
                graph.add_node(b_fps)
                graph.add_node(b_scale)
                graph.add_node(b_overlay)

                graph.add_edge(f"node_broll_in_{b_idx}", "out", f"node_broll_trim_{b_idx}", "in", stream_label=f"[br_in_{b_idx}]")
                graph.add_edge(f"node_broll_trim_{b_idx}", "out", f"node_broll_pts_{b_idx}", "in", stream_label=f"[br_tr_{b_idx}]")
                graph.add_edge(f"node_broll_pts_{b_idx}", "out", f"node_broll_fps_{b_idx}", "in", stream_label=f"[br_pt_{b_idx}]")
                graph.add_edge(f"node_broll_fps_{b_idx}", "out", f"node_broll_scale_{b_idx}", "in", stream_label=f"[br_sc_{b_idx}]")

                graph.add_edge(last_v_node, last_v_port, f"node_broll_overlay_{b_idx}", "main_in", stream_label=last_v_label)
                graph.add_edge(f"node_broll_scale_{b_idx}", "out", f"node_broll_overlay_{b_idx}", "overlay_in", stream_label=f"[br_ov_{b_idx}]")

                last_v_node = f"node_broll_overlay_{b_idx}"
                last_v_port = "out"
                last_v_label = f"[v_broll_{b_idx}]"

            # 2. Graphic image overlays (watermarks, logos)
            for g_idx, graphic_item in enumerate(getattr(overlays_cfg, "graphic_items", [])):
                graphic_path = _resolve_path(graphic_item.asset_uri)
                if not Path(graphic_path).exists():
                    continue

                resolved = OverlayPlanner.resolve_graphic_placement(
                    spec=graphic_item,
                    canvas_width=dst_w,
                    canvas_height=dst_h,
                )

                g_in = ImageInputNode(id=f"node_graphic_in_{g_idx}", params={"file_path": graphic_path})
                g_scale = ScaleNode(id=f"node_graphic_scale_{g_idx}", params={
                    "width": resolved.target_width,
                    "height": resolved.target_height,
                    "flags": "bicubic"
                })
                g_overlay = OverlayNode(id=f"node_graphic_overlay_{g_idx}", params={
                    "x": resolved.x_expr,
                    "y": resolved.y_expr,
                    "enable": resolved.enable_expr,
                    "eof_action": "repeat"
                })

                graph.add_node(g_in)
                graph.add_node(g_scale)
                graph.add_node(g_overlay)

                graph.add_edge(f"node_graphic_in_{g_idx}", "out", f"node_graphic_scale_{g_idx}", "in", stream_label=f"[gr_in_{g_idx}]")
                graph.add_edge(last_v_node, last_v_port, f"node_graphic_overlay_{g_idx}", "main_in", stream_label=last_v_label)
                graph.add_edge(f"node_graphic_scale_{g_idx}", "out", f"node_graphic_overlay_{g_idx}", "overlay_in", stream_label=f"[gr_sc_{g_idx}]")

                last_v_node = f"node_graphic_overlay_{g_idx}"
                last_v_port = "out"
                last_v_label = f"[v_graphic_{g_idx}]"

        pix_fmt = getattr(delivery, "pixel_format", getattr(delivery, "pix_fmt", "yuv420p"))
        v_fmt = PixelFormatConvertNode(id="node_v_fmt", params={"pixel_format": pix_fmt})

        # Subtitle burning if ASS file is present
        if ass_subtitle_path:
            v_sub = SubtitleBurnNode(id="node_v_sub", params={"ass_file_path": ass_subtitle_path})
            graph.add_node(v_sub)
            graph.add_edge(last_v_node, last_v_port, "node_v_sub", "in", stream_label=last_v_label)
            last_v_node = "node_v_sub"
            last_v_port = "out"
            last_v_label = "[v_sub]"

        graph.add_node(v_fmt)
        graph.add_edge(last_v_node, last_v_port, "node_v_fmt", "in", stream_label=last_v_label)

        v_out = VideoOutputNode(id="node_v_out", params={"label": "v_out"})
        graph.add_node(v_out)
        graph.add_edge("node_v_fmt", "out", "node_v_out", "in", stream_label="[v_out]")

        # 5. Audio Pipeline
        a_trim = AudioTrimNode(id="node_a_trim", params={"start_us": start_us, "end_us": end_us})
        a_pts = SetAPTSNode(id="node_a_pts", params={"expr": "PTS-STARTPTS"})
        sample_rate = getattr(delivery, "audio_sample_rate", getattr(delivery, "sample_rate", 48000))
        a_resample = AudioResampleNode(id="node_a_resample", params={"sample_rate": sample_rate})

        graph.add_node(a_trim)
        graph.add_node(a_pts)
        graph.add_node(a_resample)

        graph.add_edge("node_a_in", "out", "node_a_trim", "in", stream_label="[a_raw]")
        graph.add_edge("node_a_trim", "out", "node_a_pts", "in", stream_label="[a_trim]")
        graph.add_edge("node_a_pts", "out", "node_a_resample", "in", stream_label="[a_pts]")

        last_a_node = "node_a_resample"
        last_a_port = "out"
        last_a_label = "[a_resample]"

        # Voice gain & High Pass
        voice_cfg = getattr(spec.audio, "voice", None) or getattr(spec.audio, "dialogue", None)
        dialogue_gain = 1.0
        if voice_cfg:
            if hasattr(voice_cfg, "high_pass_filter_hz") and voice_cfg.high_pass_filter_hz > 0:
                a_hp = HighPassFilterNode(id="node_a_hp", params={"frequency": voice_cfg.high_pass_filter_hz})
                graph.add_node(a_hp)
                graph.add_edge(last_a_node, last_a_port, "node_a_hp", "in", stream_label=last_a_label)
                last_a_node = "node_a_hp"
                last_a_port = "out"
                last_a_label = "[a_hp]"

            if hasattr(voice_cfg, "gain"):
                dialogue_gain = float(voice_cfg.gain)
            elif hasattr(voice_cfg, "gain_db"):
                dialogue_gain = db_to_linear(voice_cfg.gain_db)

        a_gain = AudioGainNode(id="node_a_gain", params={"volume": dialogue_gain})
        graph.add_node(a_gain)
        graph.add_edge(last_a_node, last_a_port, "node_a_gain", "in", stream_label=last_a_label)
        last_a_node = "node_a_gain"
        last_a_port = "out"
        last_a_label = "[a_gain]"

        # Check background music
        music_cfg = getattr(spec.audio, "music", None)
        music_uri = getattr(music_cfg, "asset_uri", None) if music_cfg else None
        music_path = None
        if music_uri:
            if asset_resolver and music_uri in asset_resolver:
                music_path = asset_resolver[music_uri]
            elif Path(music_uri).exists():
                music_path = music_uri
            else:
                cleaned = music_uri.replace("asset://", "")
                resolved_p = Path(cleaned).resolve()
                if resolved_p.exists():
                    music_path = str(resolved_p)

        if music_path and Path(music_path).exists():
            m_in = AudioInputNode(id="node_music_in", params={"file_path": music_path})
            m_trim = AudioTrimNode(id="node_music_trim", params={"start_us": 0, "end_us": end_us - start_us})
            m_pts = SetAPTSNode(id="node_music_pts", params={"expr": "PTS-STARTPTS"})
            m_resample = AudioResampleNode(id="node_music_resample", params={"sample_rate": sample_rate})
            m_vol = db_to_linear(music_cfg.gain_db) if hasattr(music_cfg, "gain_db") else 0.125
            m_gain = AudioGainNode(id="node_music_gain", params={"volume": m_vol})

            graph.add_node(m_in)
            graph.add_node(m_trim)
            graph.add_node(m_pts)
            graph.add_node(m_resample)
            graph.add_node(m_gain)

            graph.add_edge("node_music_in", "out", "node_music_trim", "in", stream_label="[m_raw]")
            graph.add_edge("node_music_trim", "out", "node_music_pts", "in", stream_label="[m_trim]")
            graph.add_edge("node_music_pts", "out", "node_music_resample", "in", stream_label="[m_pts]")
            graph.add_edge("node_music_resample", "out", "node_music_gain", "in", stream_label="[m_resample]")

            ducking_cfg = getattr(spec.audio, "ducking", None)
            music_final_node = "node_music_gain"
            music_final_port = "out"
            music_final_label = "[m_gain]"

            if ducking_cfg and getattr(ducking_cfg, "enabled", False):
                duck_params = AudioMixPlanner.calculate_ducking_parameters(ducking_cfg)
                a_split = ASplitNode(id="node_a_split", params={"outputs_count": 2})
                m_duck = SidechainCompressNode(id="node_music_duck", params=duck_params)
                graph.add_node(a_split)
                graph.add_node(m_duck)

                graph.add_edge(last_a_node, last_a_port, "node_a_split", "in", stream_label=last_a_label)
                graph.add_edge("node_a_split", "out_0", "node_music_duck", "sidechain_in", stream_label="[a_duck_sc]")
                graph.add_edge("node_music_gain", "out", "node_music_duck", "main_in", stream_label="[m_gain]")

                # Mix voice dialogue (out_1) and ducked music
                a_mix = AudioMixNode(id="node_a_mix", params={"inputs_count": 2, "duration": "first", "dropout_transition": 2})
                graph.add_node(a_mix)
                graph.add_edge("node_a_split", "out_1", "node_a_mix", "in_0", stream_label="[a_voice_mix]")
                graph.add_edge("node_music_duck", "out", "node_a_mix", "in_1", stream_label="[m_duck]")

            else:
                # Direct mix voice and music without ducking
                a_mix = AudioMixNode(id="node_a_mix", params={"inputs_count": 2, "duration": "first", "dropout_transition": 2})
                graph.add_node(a_mix)
                graph.add_edge(last_a_node, last_a_port, "node_a_mix", "in_0", stream_label=last_a_label)
                graph.add_edge("node_music_gain", "out", "node_a_mix", "in_1", stream_label="[m_gain]")

            last_a_node = "node_a_mix"
            last_a_port = "out"
            last_a_label = "[a_mix]"

        # Loudness mastering (EBU R128)
        loudness = getattr(spec.audio, "master_loudness", None) or getattr(spec.audio, "loudness", None)
        target_lufs = getattr(loudness, "integrated_lufs", getattr(loudness, "target_lufs", -14.0)) if loudness else -14.0
        tp = getattr(loudness, "true_peak_dbtp", getattr(loudness, "max_true_peak_dbtp", -1.0)) if loudness else -1.0
        lra = getattr(loudness, "loudness_range_lu", getattr(loudness, "loudness_range_target", getattr(loudness, "lra", 7.0))) if loudness else 7.0

        a_loud = LoudnessNormalizeNode(
            id="node_a_loud",
            params={
                "target_lufs": target_lufs,
                "max_true_peak_dbtp": tp,
                "lra": lra,
            }
        )
        a_out = AudioOutputNode(id="node_a_out", params={"label": "a_out"})

        graph.add_node(a_loud)
        graph.add_node(a_out)

        graph.add_edge(last_a_node, last_a_port, "node_a_loud", "in", stream_label=last_a_label)
        graph.add_edge("node_a_loud", "out", "node_a_out", "in", stream_label="[a_out]")

        # 6. Muxing and Output Container
        mux = VideoAudioMuxNode(id="node_mux", params={"output_path": output_file_path})
        container = OutputContainerNode(id="node_container", params={"output_path": output_file_path})
        graph.add_node(mux)
        graph.add_node(container)

        graph.add_edge("node_v_out", "out", "node_mux", "video")
        graph.add_edge("node_a_out", "out", "node_mux", "audio")
        graph.add_edge("node_mux", "out", "node_container", "in")

        return graph
