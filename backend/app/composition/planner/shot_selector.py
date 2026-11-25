"""
ClipForge AI - Intelligent Shot Selector
Determines shot framing (Close-Up, Medium Shot, Wide Shot) and cut vs smooth transitions
while enforcing cinematic minimum hold durations.
"""

from dataclasses import dataclass
from typing import Optional, Literal
from ..schemas.layout import NormalizedRect
from .subject_evaluator import SubjectCandidate


@dataclass
class ShotDecision:
    """Framing decision for a time window."""
    shot_type: Literal["close_up", "medium_shot", "wide_shot"]
    transition_mode: Literal["cut", "smooth", "hold"]
    target_subject: Optional[SubjectCandidate]
    hold_duration_sec: float


class ShotSelector:
    """
    Selects framing scale and transition dynamics based on dialogue pace and speaker activity.
    """

    def __init__(
        self,
        min_hold_duration_sec: float = 1.2,
        close_up_scale: float = 1.4,
        medium_shot_scale: float = 2.2,
        wide_shot_scale: float = 3.5,
    ):
        self.min_hold_duration = min_hold_duration_sec
        self.cu_scale = close_up_scale
        self.ms_scale = medium_shot_scale
        self.ws_scale = wide_shot_scale

    def select_shot(
        self,
        current_time_sec: float,
        last_decision: Optional[ShotDecision],
        candidates: list[SubjectCandidate],
        is_dialogue_turn: bool = False,
    ) -> ShotDecision:
        """
        Evaluate candidate subjects and decide shot type and transition mode.
        """
        if not candidates:
            # No face detected: Fall back to wide center shot or hold last known
            if last_decision and last_decision.target_subject:
                return ShotDecision(
                    shot_type=last_decision.shot_type,
                    transition_mode="hold",
                    target_subject=last_decision.target_subject,
                    hold_duration_sec=self.min_hold_duration,
                )
            return ShotDecision(
                shot_type="wide_shot",
                transition_mode="smooth",
                target_subject=None,
                hold_duration_sec=self.min_hold_duration,
            )

        top_candidate = candidates[0]

        # Check if we should hold previous shot to avoid jitter
        if last_decision and last_decision.target_subject:
            prev_track_id = last_decision.target_subject.face_track_id
            curr_track_id = top_candidate.face_track_id

            # If it's a different person but minimum hold duration has not elapsed
            # and it is not a strong dialogue turn, hold the shot
            time_since_cut = current_time_sec - getattr(last_decision, "_cut_timestamp", current_time_sec)
            if prev_track_id != curr_track_id and time_since_cut < self.min_hold_duration and not is_dialogue_turn:
                return ShotDecision(
                    shot_type=last_decision.shot_type,
                    transition_mode="hold",
                    target_subject=last_decision.target_subject,
                    hold_duration_sec=self.min_hold_duration - time_since_cut,
                )

        # Decide shot type based on confidence and face size
        if top_candidate.is_active_speaker and top_candidate.confidence > 0.85:
            shot_type = "close_up"
        elif top_candidate.importance_score > 0.4:
            shot_type = "medium_shot"
        else:
            shot_type = "wide_shot"

        # Decide transition mode:
        # A change of subject or a distinct dialogue turn warrants a cut
        transition_mode: Literal["cut", "smooth", "hold"] = "smooth"
        if last_decision and last_decision.target_subject:
            if last_decision.target_subject.face_track_id != top_candidate.face_track_id:
                transition_mode = "cut"
        elif last_decision is None:
            transition_mode = "cut"

        decision = ShotDecision(
            shot_type=shot_type,
            transition_mode=transition_mode,
            target_subject=top_candidate,
            hold_duration_sec=self.min_hold_duration,
        )
        if transition_mode == "cut":
            setattr(decision, "_cut_timestamp", current_time_sec)
        elif last_decision and hasattr(last_decision, "_cut_timestamp"):
            setattr(decision, "_cut_timestamp", getattr(last_decision, "_cut_timestamp"))

        return decision
