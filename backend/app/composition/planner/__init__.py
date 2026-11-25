"""
ClipForge AI - Composition Planner Module
Intelligent composition planning, multi-modal subject evaluation, and speaker-aware camera reframing.
"""

from .subject_evaluator import SubjectEvaluator, SubjectCandidate
from .shot_selector import ShotSelector, ShotDecision
from .transition_planner import TransitionPlanner
from .composition_planner_service import CompositionPlannerService, CompositionPlanningError

__all__ = [
    "SubjectEvaluator",
    "SubjectCandidate",
    "ShotSelector",
    "ShotDecision",
    "TransitionPlanner",
    "CompositionPlannerService",
    "CompositionPlanningError",
]
