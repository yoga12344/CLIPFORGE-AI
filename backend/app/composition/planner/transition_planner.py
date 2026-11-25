"""
ClipForge AI - Transition & Camera Keyframe Planner
Calculates cinematic 9:16 crop trajectories, exponential moving average smoothing,
velocity clamping, and keyframe generation for CompositionSpec CameraPlan.
"""

import math
from typing import List, Optional, Tuple
from ..schemas.layout import NormalizedRect
from ..schemas.camera import CameraPlan, CameraKeyframe, SubjectReference, ManualOverride
from ..schemas.timeline import seconds_to_us
from .shot_selector import ShotDecision


class TransitionPlanner:
    """
    Translates shot decisions into smooth, broadcast-safe camera trajectories.
    """

    def __init__(
        self,
        source_width: int = 1920,
        source_height: int = 1080,
        target_width: int = 1080,
        target_height: int = 1920,
        smoothing_strength: float = 0.85,
        max_velocity_per_sec: float = 0.40,
        min_hold_duration_sec: float = 1.2,
    ):
        self.src_w = source_width
        self.src_h = source_height
        self.tgt_w = target_width
        self.tgt_h = target_height
        self.smoothing = smoothing_strength
        self.max_velocity = max_velocity_per_sec
        self.min_hold_duration_us = int(min_hold_duration_sec * 1_000_000)

        # Aspect ratios
        self.ar_src = source_width / source_height
        self.ar_tgt = target_width / target_height
        # w_norm_scale = (tgt_w / tgt_h) / (src_w / src_h)
        self.w_norm_scale = self.ar_tgt / self.ar_src

    def calculate_crop_rect(
        self,
        face_bbox: Optional[NormalizedRect],
        shot_type: str = "medium_shot",
    ) -> NormalizedRect:
        """
        Calculate target NormalizedRect maintaining exact target aspect ratio.
        """
        # Determine normalized crop height based on shot framing
        if shot_type == "close_up" and face_bbox:
            # Zoomed in: height roughly 2.0x face height (minimum 0.5)
            h_norm = max(0.45, min(0.85, face_bbox.height * 2.2))
        elif shot_type == "medium_shot" and face_bbox:
            # Standard dialogue: comfortable chest & headroom
            h_norm = max(0.70, min(1.0, face_bbox.height * 3.5))
        else:
            # Wide / Full height
            h_norm = 1.0

        w_norm = h_norm * self.w_norm_scale

        # If w_norm > 1.0 (unlikely for 9:16 in 16:9, but safe guard), clamp
        if w_norm > 1.0:
            w_norm = 1.0
            h_norm = w_norm / self.w_norm_scale

        if face_bbox:
            # Target face center
            center_x = face_bbox.center_x
            center_y = face_bbox.center_y
            # Place face around 35% from the top of the crop window
            target_x = center_x - (w_norm / 2.0)
            target_y = center_y - (0.35 * h_norm)
        else:
            # Center of source frame
            target_x = (1.0 - w_norm) / 2.0
            target_y = (1.0 - h_norm) / 2.0

        # Strict clamping within [0.0, 1.0]
        clamped_x = max(0.0, min(1.0 - w_norm, target_x))
        clamped_y = max(0.0, min(1.0 - h_norm, target_y))

        # Precision rounding
        return NormalizedRect(
            x=round(clamped_x, 5),
            y=round(clamped_y, 5),
            width=round(w_norm, 5),
            height=round(h_norm, 5),
        )

    def plan_camera(
        self,
        timeline_duration_sec: float,
        shot_decisions: List[Tuple[float, ShotDecision]],
        manual_overrides: Optional[List[ManualOverride]] = None,
    ) -> CameraPlan:
        """
        Assemble the complete CameraPlan and sequence of CameraKeyframes.
        """
        manual_overrides = manual_overrides or []
        keyframes: List[CameraKeyframe] = []

        if not shot_decisions:
            # Default single center keyframe
            default_rect = self.calculate_crop_rect(None, "wide_shot")
            keyframes.append(
                CameraKeyframe(
                    timeline_position_us=0,
                    slot_id="slot_0",
                    crop_rect=default_rect,
                    interpolation_mode="smooth",
                    confidence=1.0,
                )
            )
            return CameraPlan(
                default_strategy="active_speaker",
                smoothing_strength=self.smoothing,
                max_velocity_per_sec=self.max_velocity,
                min_hold_duration_us=self.min_hold_duration_us,
                keyframes=keyframes,
                manual_overrides=manual_overrides,
            )

        # Track smoothing state
        current_x: Optional[float] = None
        current_y: Optional[float] = None
        current_w: Optional[float] = None
        current_h: Optional[float] = None
        last_time_sec: float = 0.0

        for t_sec, decision in shot_decisions:
            target_sub = decision.target_subject
            face_bbox = target_sub.bbox if target_sub else None
            ideal_rect = self.calculate_crop_rect(face_bbox, decision.shot_type)

            dt = max(0.001, t_sec - last_time_sec)

            if decision.transition_mode == "cut" or current_x is None:
                # Instant transition: no velocity clamp or EMA
                current_x = ideal_rect.x
                current_y = ideal_rect.y
                current_w = ideal_rect.width
                current_h = ideal_rect.height
                mode = "cut" if len(keyframes) > 0 else "smooth"
            else:
                # Smooth transition with velocity clamping and EMA
                max_shift = self.max_velocity * dt

                # Velocity clamp in X
                diff_x = ideal_rect.x - current_x
                if abs(diff_x) > max_shift:
                    target_x = current_x + math.copysign(max_shift, diff_x)
                else:
                    target_x = ideal_rect.x

                # Velocity clamp in Y
                diff_y = ideal_rect.y - current_y
                if abs(diff_y) > max_shift:
                    target_y = current_y + math.copysign(max_shift, diff_y)
                else:
                    target_y = ideal_rect.y

                # Exponential moving average filter
                alpha = 1.0 - self.smoothing
                current_x = current_x + alpha * (target_x - current_x)
                current_y = current_y + alpha * (target_y - current_y)
                current_w = current_w + alpha * (ideal_rect.width - current_w)
                current_h = current_h + alpha * (ideal_rect.height - current_h)
                mode = "smooth"

            # Re-clamp boundaries
            w_norm = min(1.0, max(0.01, current_w))
            h_norm = min(1.0, max(0.01, current_h))
            x_norm = max(0.0, min(1.0 - w_norm, current_x))
            y_norm = max(0.0, min(1.0 - h_norm, current_y))

            rect = NormalizedRect(
                x=round(x_norm, 5),
                y=round(y_norm, 5),
                width=round(w_norm, 5),
                height=round(h_norm, 5),
            )

            # Create SubjectReference if applicable
            sub_ref = None
            if target_sub:
                sub_ref = SubjectReference(
                    face_track_id=target_sub.face_track_id,
                    speaker_id=target_sub.speaker_id,
                    strategy=target_sub.strategy if target_sub.strategy in ("active_speaker", "largest_face", "centroid", "manual", "fallback") else "active_speaker",
                    confidence=target_sub.confidence,
                )

            keyframe = CameraKeyframe(
                timeline_position_us=seconds_to_us(t_sec),
                slot_id="slot_0",
                crop_rect=rect,
                target_subject=sub_ref,
                interpolation_mode=mode,
                confidence=target_sub.confidence if target_sub else 0.8,
            )
            keyframes.append(keyframe)
            last_time_sec = t_sec

        # Apply any manual overrides, replacing or overriding nearest keyframes
        for mo in manual_overrides:
            keyframes.append(
                CameraKeyframe(
                    timeline_position_us=mo.timeline_position_us,
                    slot_id=mo.slot_id,
                    crop_rect=mo.crop_rect,
                    interpolation_mode="smooth",
                    confidence=1.0,
                    is_manual_override=True,
                )
            )

        # Sort keyframes deterministically by timeline_position_us
        keyframes.sort(key=lambda k: k.timeline_position_us)

        return CameraPlan(
            default_strategy="active_speaker",
            smoothing_strength=self.smoothing,
            max_velocity_per_sec=self.max_velocity,
            min_hold_duration_us=self.min_hold_duration_us,
            fallback_behavior="hold_last_known",
            keyframes=keyframes,
            manual_overrides=manual_overrides,
        )
