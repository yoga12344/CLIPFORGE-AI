"""
ClipForge AI - Intelligent Multi-Person Layout Selector
Analyzes speaker counts, dialogue turns, and visual presence to select
the optimal layout topology (single_full_frame, split_vertical, blurred_background, picture_in_picture).
"""

from typing import List, Dict, Any, Optional


class LayoutSelector:
    """
    Intelligently assigns layout topology and slot configuration based on scene context.
    """

    @classmethod
    def select_optimal_layout(
        cls,
        face_tracks: List[Dict[str, Any]],
        active_speaker_tracks: List[str],
        speaker_turns_count: int = 0,
        prefer_multi_person: bool = True,
    ) -> str:
        """
        Choose best layout topology.
        """
        unique_active_speakers = set(active_speaker_tracks)
        num_faces = len(face_tracks)

        # 1. No faces detected: blurred background landscape
        if num_faces == 0:
            return "blurred_background"

        # 2. Multi-speaker conversation: 2 active speakers with dialogue turns
        if prefer_multi_person and len(unique_active_speakers) >= 2 and speaker_turns_count >= 2:
            return "split_vertical"

        # 3. Two distinct visible faces with back-and-forth dialogue
        if prefer_multi_person and num_faces >= 2 and speaker_turns_count >= 3:
            return "split_vertical"

        # 4. Default solo or dominant speaker: single full frame 9:16 vertical crop
        return "single_full_frame"
