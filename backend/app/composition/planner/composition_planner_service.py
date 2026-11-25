"""
ClipForge AI - Intelligent Composition Planner Service
Fuses Highlights, ASR Transcripts, YuNet Face Tracks, Silero VAD, CAM++ Diarization,
and MediaPipe/Light-ASD Active Speaker Detection into an automated, production-ready CompositionSpec v1.0.0.
"""

import logging
import uuid
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Composition,
    CompositionVersion,
    Video,
    Project,
    HighlightCandidate,
    Transcript,
    TranscriptSegment,
    VisionAnalysis,
    FaceTrack,
    ActiveSpeakerInterval,
    SpeakerFaceAssociation,
    AudioAnalysis,
    SpeakerTurn,
    ManualCropCorrection,
)
from ..schemas.composition import CompositionSpec, SourceMediaMetadata
from ..schemas.timeline import ClipBoundary, TimelineSpec, RationalTimebase, seconds_to_us
from ..schemas.layout import LayoutConfig
from ..schemas.camera import CameraPlan, ManualOverride
from ..schemas.tracks import VideoTrack, AudioTrack, SubtitleTrackSpec, TrackSegment
from ..schemas.subtitles import SubtitleCompositionConfig, SubtitleSegmentRef, SubtitleWordRef
from ..schemas.delivery import DeliveryProfile, get_default_delivery_profile
from ..schemas.audio import AudioCompositionConfig, VoiceDialogueConfig, LoudnessMasteringConfig
from ..services.composition_service import CompositionService, ResourceOwnershipError
from .subject_evaluator import SubjectEvaluator
from .shot_selector import ShotSelector
from .transition_planner import TransitionPlanner

logger = logging.getLogger("clipforge.composition.planner")


class CompositionPlanningError(Exception):
    """Raised when composition auto-planning fails."""
    pass


class CompositionPlannerService:
    """
    High-level orchestrator transforming raw AI analysis assets into an editable,
    validated CompositionSpec and persisting it into versioned database storage.
    """

    @classmethod
    async def plan_composition_for_candidate(
        cls,
        db: AsyncSession,
        candidate_id: str,
        project_id: Optional[str] = None,
        aspect_ratio: str = "9:16",
        subtitle_preset: str = "preset_bold_creator",
        enable_subtitles: bool = True,
    ) -> Tuple[Composition, CompositionVersion, CompositionSpec]:
        """
        Auto-plans a composition directly from an approved or discovered HighlightCandidate.
        """
        # 1. Fetch candidate
        stmt = select(HighlightCandidate).where(HighlightCandidate.id == candidate_id)
        res = await db.execute(stmt)
        cand = res.scalar_one_or_none()
        if not cand:
            raise CompositionPlanningError(f"HighlightCandidate '{candidate_id}' not found.")

        p_id = project_id or cand.project_id
        if cand.project_id != p_id:
            raise ResourceOwnershipError(
                f"Candidate '{candidate_id}' belongs to project '{cand.project_id}', not '{p_id}'"
            )

        title = cand.title or "Highlight Clip"
        description = cand.summary or cand.reason

        return await cls.plan_composition_for_range(
            db=db,
            video_id=cand.video_id,
            project_id=p_id,
            start_time=cand.start_time,
            end_time=cand.end_time,
            title=title,
            description=description,
            candidate_id=candidate_id,
            aspect_ratio=aspect_ratio,
            subtitle_preset=subtitle_preset,
            enable_subtitles=enable_subtitles,
        )

    @classmethod
    async def plan_composition_for_range(
        cls,
        db: AsyncSession,
        video_id: str,
        project_id: str,
        start_time: float,
        end_time: float,
        title: str = "Composition Clip",
        description: Optional[str] = None,
        candidate_id: Optional[str] = None,
        aspect_ratio: str = "9:16",
        subtitle_preset: str = "preset_bold_creator",
        enable_subtitles: bool = True,
    ) -> Tuple[Composition, CompositionVersion, CompositionSpec]:
        """
        Auto-plans a composition for an arbitrary time range in a source video.
        """
        if end_time <= start_time:
            raise CompositionPlanningError(f"end_time ({end_time}) must be greater than start_time ({start_time})")

        # 1. Fetch video
        v_res = await db.execute(select(Video).where(Video.id == video_id))
        video = v_res.scalar_one_or_none()
        if not video:
            raise CompositionPlanningError(f"Video '{video_id}' not found.")
        if video.project_id != project_id:
            raise ResourceOwnershipError(
                f"Video '{video_id}' belongs to project '{video.project_id}', not '{project_id}'"
            )

        clip_dur_sec = end_time - start_time
        source_start_us = seconds_to_us(start_time)
        source_end_us = seconds_to_us(end_time)
        duration_us = source_end_us - source_start_us

        # 2. Query Transcripts & Subtitle Words
        sub_segments: List[SubtitleSegmentRef] = []
        t_stmt = select(Transcript).where(Transcript.video_id == video_id)
        t_res = await db.execute(t_stmt)
        transcript = t_res.scalar_one_or_none()

        if transcript:
            seg_stmt = select(TranscriptSegment).where(
                and_(
                    TranscriptSegment.transcript_id == transcript.id,
                    TranscriptSegment.end_time > start_time,
                    TranscriptSegment.start_time < end_time,
                )
            ).order_by(TranscriptSegment.start_time)
            seg_res = await db.execute(seg_stmt)
            raw_segs = seg_res.scalars().all()

            for s in raw_segs:
                # Clamp segment bounds to clip
                c_start = max(start_time, s.start_time)
                c_end = min(end_time, s.end_time)
                if c_end <= c_start:
                    continue

                rel_start_us = seconds_to_us(c_start - start_time)
                rel_end_us = seconds_to_us(c_end - start_time)

                word_refs: List[SubtitleWordRef] = []
                if s.words and isinstance(s.words, list):
                    for w in s.words:
                        w_start = float(w.get("start", s.start_time))
                        w_end = float(w.get("end", s.end_time))
                        if w_end > start_time and w_start < end_time and w_end > w_start:
                            cw_start = max(start_time, w_start)
                            cw_end = min(end_time, w_end)
                            if cw_end > cw_start:
                                word_refs.append(
                                    SubtitleWordRef(
                                        word=str(w.get("word", "")),
                                        start_us=seconds_to_us(cw_start - start_time),
                                        end_us=seconds_to_us(cw_end - start_time),
                                        probability=float(w.get("prob", w.get("probability", 1.0))),
                                    )
                                )

                sub_segments.append(
                    SubtitleSegmentRef(
                        segment_id=f"sub_{s.id}",
                        start_us=rel_start_us,
                        end_us=rel_end_us,
                        text=s.text,
                        speaker_id=s.speaker_id,
                        words=word_refs,
                    )
                )

        # 3. Query Vision Analyses and Face Tracks
        face_tracks_data: List[Dict[str, Any]] = []
        vis_stmt = select(VisionAnalysis).where(VisionAnalysis.video_id == video_id)
        vis_res = await db.execute(vis_stmt)
        vis_analyses = vis_res.scalars().all()

        for va in vis_analyses:
            ft_stmt = select(FaceTrack).where(
                and_(
                    FaceTrack.vision_analysis_id == va.id,
                    FaceTrack.end_time > start_time,
                    FaceTrack.start_time < end_time,
                )
            )
            ft_res = await db.execute(ft_stmt)
            tracks = ft_res.scalars().all()
            for t in tracks:
                face_tracks_data.append({
                    "track_id": t.track_id,
                    "start_time": t.start_time,
                    "end_time": t.end_time,
                    "average_bbox": t.average_bbox,
                    "samples": t.samples,
                    "average_confidence": t.average_confidence,
                })

        # 4. Query Active Speaker Intervals
        active_intervals_data: List[Dict[str, Any]] = []
        asi_stmt = select(ActiveSpeakerInterval).where(
            and_(
                ActiveSpeakerInterval.video_id == video_id,
                ActiveSpeakerInterval.end_time > start_time,
                ActiveSpeakerInterval.start_time < end_time,
            )
        )
        asi_res = await db.execute(asi_stmt)
        for asi in asi_res.scalars().all():
            active_intervals_data.append({
                "face_track_id": asi.face_track_id,
                "speaker_id": asi.speaker_id,
                "start_time": asi.start_time,
                "end_time": asi.end_time,
                "state": asi.state,
                "confidence": asi.confidence,
                "speaking_score": asi.speaking_score,
            })

        # 5. Query Speaker Turns (Acoustic Diarization)
        speaker_turns_data: List[Dict[str, Any]] = []
        aud_stmt = select(AudioAnalysis).where(AudioAnalysis.video_id == video_id)
        aud_res = await db.execute(aud_stmt)
        aud_analyses = aud_res.scalars().all()

        for aa in aud_analyses:
            st_stmt = select(SpeakerTurn).where(
                and_(
                    SpeakerTurn.analysis_id == aa.id,
                    SpeakerTurn.end_time > start_time,
                    SpeakerTurn.start_time < end_time,
                )
            )
            st_res = await db.execute(st_stmt)
            for st in st_res.scalars().all():
                speaker_turns_data.append({
                    "speaker_id": st.speaker_id,
                    "start_time": st.start_time,
                    "end_time": st.end_time,
                    "turn_index": st.turn_index,
                })

        # 6. Query Speaker-Face Associations
        speaker_face_map: Dict[str, str] = {}
        sfa_stmt = select(SpeakerFaceAssociation).where(SpeakerFaceAssociation.video_id == video_id)
        sfa_res = await db.execute(sfa_stmt)
        for sfa in sfa_res.scalars().all():
            if sfa.speaker_id and sfa.face_track_id:
                speaker_face_map[sfa.speaker_id] = sfa.face_track_id

        # 7. Query Manual Crop Corrections within range
        manual_overrides: List[ManualOverride] = []
        for va in vis_analyses:
            mc_stmt = select(ManualCropCorrection).where(
                and_(
                    ManualCropCorrection.vision_analysis_id == va.id,
                    ManualCropCorrection.timestamp_seconds >= start_time,
                    ManualCropCorrection.timestamp_seconds <= end_time,
                )
            )
            mc_res = await db.execute(mc_stmt)
            for mc in mc_res.scalars().all():
                from ..schemas.layout import NormalizedRect
                rel_t = mc.timestamp_seconds - start_time
                x_c = max(0.0, min(0.99, mc.crop_x))
                y_c = max(0.0, min(0.99, mc.crop_y))
                w_c = max(0.01, min(1.0 - x_c, mc.crop_width))
                h_c = max(0.01, min(1.0 - y_c, mc.crop_height))
                manual_overrides.append(
                    ManualOverride(
                        timeline_position_us=seconds_to_us(rel_t),
                        slot_id="slot_0",
                        crop_rect=NormalizedRect(
                            x=round(x_c, 5),
                            y=round(y_c, 5),
                            width=round(w_c, 5),
                            height=round(h_c, 5),
                        ),
                        is_locked=True,
                    )
                )

        # 8. Run Subject Evaluator & Shot Selector & Transition Planner
        evaluator = SubjectEvaluator()
        selector = ShotSelector(min_hold_duration_sec=1.2)
        planner = TransitionPlanner(
            source_width=video.width or 1920,
            source_height=video.height or 1080,
            target_width=1080 if aspect_ratio == "9:16" else 1920,
            target_height=1920 if aspect_ratio == "9:16" else 1080,
        )

        # Sample timeline at 0.5s steps and at dialogue boundaries
        sample_times_set = {0.0, clip_dur_sec}
        # Add intermediate points
        cur_t = 0.0
        while cur_t < clip_dur_sec:
            sample_times_set.add(round(cur_t, 3))
            cur_t += 0.5

        # Add active speaker boundaries
        for asi in active_intervals_data:
            rel_s = asi["start_time"] - start_time
            rel_e = asi["end_time"] - start_time
            if 0.0 <= rel_s <= clip_dur_sec:
                sample_times_set.add(round(rel_s, 3))
            if 0.0 <= rel_e <= clip_dur_sec:
                sample_times_set.add(round(rel_e, 3))

        sample_times = sorted(list(sample_times_set))

        shot_decisions = []
        last_dec = None
        for rel_t in sample_times:
            abs_t = start_time + rel_t
            candidates = evaluator.evaluate_candidates_at(
                timestamp_sec=abs_t,
                face_tracks=face_tracks_data,
                active_intervals=active_intervals_data,
                speaker_turns=speaker_turns_data,
                speaker_face_map=speaker_face_map,
            )
            dec = selector.select_shot(
                current_time_sec=rel_t,
                last_decision=last_dec,
                candidates=candidates,
            )
            shot_decisions.append((rel_t, dec))
            last_dec = dec

        camera_plan = planner.plan_camera(
            timeline_duration_sec=clip_dur_sec,
            shot_decisions=shot_decisions,
            manual_overrides=manual_overrides,
        )

        # 9. Build CompositionSpec AST
        comp_id = str(uuid.uuid4())
        source_media = SourceMediaMetadata(
            video_id=video.id,
            asset_uri=f"asset://videos/{video.id}",
            width=video.width or 1920,
            height=video.height or 1080,
            fps=video.fps or 30.0,
            duration_us=seconds_to_us(video.duration_seconds or 10.0),
            has_audio=video.has_audio if video.has_audio is not None else True,
            audio_channels=video.audio_channels or 2,
            audio_sample_rate=48000,
        )

        clip_boundary = ClipBoundary(
            source_start_us=source_start_us,
            source_end_us=source_end_us,
            duration_us=duration_us,
            approved_candidate_id=candidate_id,
        )

        timeline = TimelineSpec(
            total_duration_us=duration_us,
            timebase=RationalTimebase.from_float(video.fps or 30.0),
        )

        tracks = [
            VideoTrack(
                track_id="track_v1",
                name="Primary Video",
                target_slot_id="slot_0",
                segments=[
                    TrackSegment(
                        segment_id="seg_v1",
                        source_asset_uri=f"asset://videos/{video.id}",
                        source_start_us=source_start_us,
                        source_end_us=source_end_us,
                        timeline_start_us=0,
                        timeline_end_us=duration_us,
                        duration_us=duration_us,
                    )
                ],
            ),
            AudioTrack(
                track_id="track_a1",
                name="Primary Audio",
                gain_db=0.0,
                is_voice_dialogue=True,
                segments=[
                    TrackSegment(
                        segment_id="seg_a1",
                        source_asset_uri=f"asset://videos/{video.id}",
                        source_start_us=source_start_us,
                        source_end_us=source_end_us,
                        timeline_start_us=0,
                        timeline_end_us=duration_us,
                        duration_us=duration_us,
                    )
                ],
            ),
            SubtitleTrackSpec(
                track_id="track_sub1",
                name="Auto Subtitles",
                preset_id=subtitle_preset,
                enabled=enable_subtitles,
            ),
        ]

        subtitles_config = SubtitleCompositionConfig(
            enabled=enable_subtitles,
            preset_id=subtitle_preset,
            position_mode="bottom_safe",
            segments=sub_segments,
        )

        delivery_profile = get_default_delivery_profile(aspect_ratio)

        audio_config = AudioCompositionConfig(
            voice=VoiceDialogueConfig(gain_db=0.0),
            master_loudness=LoudnessMasteringConfig(integrated_lufs=-14.0, true_peak_dbtp=-1.5),
        )

        spec = CompositionSpec(
            composition_id=comp_id,
            project_id=project_id,
            source_video_id=video_id,
            title=title,
            description=description,
            source_media=source_media,
            clip_boundary=clip_boundary,
            timeline=timeline,
            layout=LayoutConfig(layout_type="single_full_frame"),
            camera=camera_plan,
            tracks=tracks,
            subtitles=subtitles_config,
            audio=audio_config,
            delivery_profile=delivery_profile,
        )

        # 10. Persist Composition and CompositionVersion
        comp, version = await CompositionService.create_composition(
            db=db,
            project_id=project_id,
            video_id=video_id,
            title=title,
            description=description,
            candidate_id=candidate_id,
            initial_spec=spec,
            aspect_ratio=aspect_ratio,
        )

        return comp, version, spec
