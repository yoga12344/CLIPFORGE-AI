"""
ClipForge AI - Duplicate Highlight Detector and Ranker
Filters temporal overlaps and textual redundancies to assemble a diverse, high-value candidate set.
"""

import logging
from typing import Any, List, Set, Tuple
from pydantic import BaseModel

logger = logging.getLogger("clipforge.ai.highlights.duplicates")


def calculate_temporal_iou(start1: float, end1: float, start2: float, end2: float) -> float:
    """Calculate temporal Intersection over Union (IoU) of two intervals."""
    intersection_start = max(start1, start2)
    intersection_end = min(end1, end2)
    intersection = max(0.0, intersection_end - intersection_start)

    union = max(end1, end2) - min(start1, start2)
    if union <= 0:
        return 0.0
    return intersection / union


def calculate_text_jaccard(text1: str, text2: str) -> float:
    """Calculate Jaccard similarity coefficient between two word sets."""
    words1 = set(w.lower() for w in text1.split() if len(w) > 2)
    words2 = set(w.lower() for w in text2.split() if len(w) > 2)
    if not words1 or not words2:
        return 0.0
    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))
    return intersection / union if union > 0 else 0.0


class DuplicateDetector:
    """Deduplicates candidate highlights based on time overlap and semantic text overlap."""

    @classmethod
    def filter_and_rank_candidates(
        cls,
        candidates: List[Any],
        max_temporal_iou: float = 0.60,
        max_text_similarity: float = 0.70,
        max_results: int = 10
    ) -> Tuple[List[Any], int, int]:
        """
        Rank candidates by overall_score descending, then greedily filter duplicates.
        Returns: (filtered_ranked_candidates, total_discovered, total_remaining)
        """
        total_discovered = len(candidates)
        if total_discovered <= 1:
            return candidates, total_discovered, total_discovered

        # Sort by overall score descending, breaking ties with narrative completeness or duration
        def _sort_key(c):
            score = getattr(c, "overall_score", 0)
            dur = getattr(c, "duration_seconds", 0)
            return (score, -abs(dur - 45.0))

        sorted_candidates = sorted(candidates, key=_sort_key, reverse=True)
        accepted: List[Any] = []

        for candidate in sorted_candidates:
            c_start = getattr(candidate, "start_time", 0.0)
            c_end = getattr(candidate, "end_time", 0.0)
            c_text = getattr(candidate, "summary", "") + " " + getattr(candidate, "key_quote", "")

            is_duplicate = False
            for existing in accepted:
                e_start = getattr(existing, "start_time", 0.0)
                e_end = getattr(existing, "end_time", 0.0)
                e_text = getattr(existing, "summary", "") + " " + getattr(existing, "key_quote", "")

                iou = calculate_temporal_iou(c_start, c_end, e_start, e_end)
                text_sim = calculate_text_jaccard(c_text, e_text)

                # Consider duplicate if temporal overlap exceeds threshold AND text overlap is significant
                if iou >= max_temporal_iou or text_sim >= max_text_similarity:
                    is_duplicate = True
                    break

            if not is_duplicate:
                accepted.append(candidate)
                if len(accepted) >= max_results:
                    break

        return accepted, total_discovered, len(accepted)
