"""
ClipForge AI - Intelligent Reframe & Dynamic Crop Trajectory Engine
Calculates aspect-ratio-accurate crop coordinates with headroom protection,
exponential moving average (EMA) smoothing, velocity limits, and hard boundary clamping.
"""

import math
from typing import Dict, List, Optional
from app.ai.vision.schemas import (
    CropCoordinate,
    FaceDetection,
    ManualCropInput,
    NormalizedBBox,
    ReframeConfig,
    TrackedFace,
)
from app.ai.vision.subject_selector import SubjectSelector


ASPECT_RATIOS = {
    "9:16": 9.0 / 16.0,
    "1:1": 1.0 / 1.0,
    "4:5": 4.0 / 5.0,
    "16:9": 16.0 / 9.0,
}


def get_aspect_ratio_value(ratio_str: str) -> float:
    """Parse aspect ratio string into float value."""
    if ratio_str in ASPECT_RATIOS:
        return ASPECT_RATIOS[ratio_str]
    try:
        parts = ratio_str.split(":")
        if len(parts) == 2:
            return float(parts[0]) / float(parts[1])
    except Exception:
        pass
    return 9.0 / 16.0 # Default fallback


class ReframeEngine:
    """
    Computes smooth, bounding-box-following crop trajectories for vertical and social reframing.
    """

    @staticmethod
    def calculate_crop_dimensions(
        source_width: int,
        source_height: int,
        aspect_ratio: str = "9:16",
    ) -> Dict[str, float]:
        """
        Calculate normalized and pixel dimensions for target aspect ratio.
        Guarantees even pixel dimensions for libx264 compatibility.
        """
        target_ratio = get_aspect_ratio_value(aspect_ratio)
        source_ratio = float(source_width) / float(source_height)

        if target_ratio <= source_ratio:
            # Taller or equal aspect ratio (e.g. 9:16 or 1:1 in 16:9 video)
            # Crop height is full height
            crop_h_px = source_height
            crop_w_px = int(round(crop_h_px * target_ratio))
        else:
            # Wider aspect ratio (e.g. 16:9 in 4:3 video)
            crop_w_px = source_width
            crop_h_px = int(round(crop_w_px / target_ratio))

        # Ensure even pixel dimensions
        if crop_w_px % 2 != 0:
            crop_w_px -= 1
        if crop_h_px % 2 != 0:
            crop_h_px -= 1

        # Prevent exceeding source boundaries
        crop_w_px = min(source_width, max(2, crop_w_px))
        crop_h_px = min(source_height, max(2, crop_h_px))

        norm_w = crop_w_px / float(source_width)
        norm_h = crop_h_px / float(source_height)

        return {
            "norm_width": norm_w,
            "norm_height": norm_h,
            "pixel_width": crop_w_px,
            "pixel_height": crop_h_px,
        }

    @classmethod
    def generate_trajectory(
        cls,
        source_width: int,
        source_height: int,
        frame_detections: Dict[float, List[FaceDetection]], # timestamp -> detections
        config: Optional[ReframeConfig] = None,
        manual_corrections: Optional[List[ManualCropInput]] = None,
    ) -> List[CropCoordinate]:
        """
        Compute frame-by-frame crop coordinates with smoothing and boundary limits.
        """
        if config is None:
            config = ReframeConfig()

        dims = cls.calculate_crop_dimensions(source_width, source_height, config.aspect_ratio)
        crop_norm_w = dims["norm_width"]
        crop_norm_h = dims["norm_height"]
        pixel_w = int(dims["pixel_width"])
        pixel_h = int(dims["pixel_height"])

        # Prepare manual corrections lookup if provided
        manual_map: Dict[float, ManualCropInput] = {}
        if manual_corrections:
            for mc in manual_corrections:
                manual_map[round(mc.timestamp_seconds, 2)] = mc

        sorted_timestamps = sorted(frame_detections.keys())
        if not sorted_timestamps:
            # Produce default center crop
            center_x = max(0.0, (1.0 - crop_norm_w) / 2.0)
            center_y = max(0.0, (1.0 - crop_norm_h) / 2.0)
            px_x = int(round(center_x * source_width))
            px_y = int(round(center_y * source_height))
            if px_x % 2 != 0:
                px_x -= 1
            if px_y % 2 != 0:
                px_y -= 1
            return [
                CropCoordinate(
                    timestamp_seconds=0.0,
                    crop_x=center_x,
                    crop_y=center_y,
                    crop_width=crop_norm_w,
                    crop_height=crop_norm_h,
                    pixel_x=px_x,
                    pixel_y=px_y,
                    pixel_width=pixel_w,
                    pixel_height=pixel_h,
                    reframing_mode="center_fallback",
                )
            ]

        trajectory: List[CropCoordinate] = []

        prev_x: Optional[float] = None
        prev_y: Optional[float] = None
        prev_ts: Optional[float] = None
        last_known_target_bbox: Optional[NormalizedBBox] = None

        default_center_x = max(0.0, (1.0 - crop_norm_w) / 2.0)
        default_center_y = max(0.0, (1.0 - crop_norm_h) / 2.0)

        for ts in sorted_timestamps:
            rounded_ts = round(ts, 2)

            # 1. Check for manual keyframe override
            if rounded_ts in manual_map:
                mc = manual_map[rounded_ts]
                curr_x = max(0.0, min(1.0 - crop_norm_w, mc.crop_x))
                curr_y = max(0.0, min(1.0 - crop_norm_h, mc.crop_y))
                mode = "manual_override"
                conf = 1.0
            else:
                # 2. Select subject target
                detections = frame_detections[ts]
                target_bbox = SubjectSelector.select_target(
                    detections=detections,
                    strategy=config.strategy,
                    selected_track_id=config.selected_track_id,
                    last_known_bbox=last_known_target_bbox,
                )

                if target_bbox is not None:
                    last_known_target_bbox = target_bbox
                    # Center horizontally on subject
                    ideal_x = target_bbox.center_x - (crop_norm_w / 2.0)

                    # Vertical placement with headroom
                    if crop_norm_h >= 0.999:
                        ideal_y = 0.0
                    else:
                        ideal_y = target_bbox.y - (config.headroom * target_bbox.height)

                    mode = "auto_tracking"
                    conf = 1.0
                else:
                    # Fallback when no face detected: smoothly return to center or hold
                    ideal_x = default_center_x
                    ideal_y = default_center_y
                    mode = "center_fallback"
                    conf = 0.5

                # Hard clamp target ideals
                ideal_x = max(0.0, min(1.0 - crop_norm_w, ideal_x))
                ideal_y = max(0.0, min(1.0 - crop_norm_h, ideal_y))

                # 3. Temporal smoothing & velocity clamp
                if prev_x is None:
                    curr_x = ideal_x
                    curr_y = ideal_y
                else:
                    dt = max(0.01, ts - (prev_ts or ts))
                    max_step = config.max_crop_velocity_per_sec * dt

                    # Exponential Moving Average
                    alpha = max(0.0, min(0.98, config.smoothing_strength))
                    smoothed_x = alpha * prev_x + (1.0 - alpha) * ideal_x
                    smoothed_y = alpha * prev_y + (1.0 - alpha) * ideal_y

                    # Velocity clamp to avoid snap
                    step_x = smoothed_x - prev_x
                    if abs(step_x) > max_step:
                        smoothed_x = prev_x + math.copysign(max_step, step_x)

                    step_y = smoothed_y - prev_y
                    if abs(step_y) > max_step:
                        smoothed_y = prev_y + math.copysign(max_step, step_y)

                    curr_x = max(0.0, min(1.0 - crop_norm_w, smoothed_x))
                    curr_y = max(0.0, min(1.0 - crop_norm_h, smoothed_y))

            # Update previous
            prev_x = curr_x
            prev_y = curr_y
            prev_ts = ts

            # Calculate absolute pixel coordinates (even integers for FFmpeg)
            px_x = int(round(curr_x * source_width))
            px_y = int(round(curr_y * source_height))

            if px_x % 2 != 0:
                px_x -= 1
            if px_y % 2 != 0:
                px_y -= 1

            # Clamp pixel bounds
            px_x = max(0, min(source_width - pixel_w, px_x))
            px_y = max(0, min(source_height - pixel_h, px_y))

            trajectory.append(
                CropCoordinate(
                    timestamp_seconds=round(ts, 3),
                    crop_x=round(curr_x, 4),
                    crop_y=round(curr_y, 4),
                    crop_width=round(crop_norm_w, 4),
                    crop_height=round(crop_norm_h, 4),
                    pixel_x=px_x,
                    pixel_y=px_y,
                    pixel_width=pixel_w,
                    pixel_height=pixel_h,
                    selected_track_id=config.selected_track_id,
                    confidence=conf,
                    reframing_mode=mode,
                )
            )

        return trajectory
