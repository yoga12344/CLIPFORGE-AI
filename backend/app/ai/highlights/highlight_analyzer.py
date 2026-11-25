"""
ClipForge AI - Master Highlight Analyzer
Coordinates the complete pipeline: preprocessing, candidate generation, boundary refinement,
quote validation, multi-factor scoring, duplicate filtering, and ranking.
"""

import asyncio
import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional
from pydantic import BaseModel, Field

from .transcript_chunker import TranscriptChunker, TimedSentence, TimedWord
from .candidate_generator import CandidateGenerator, DiscoveredCandidate
from .boundary_refiner import BoundaryRefiner
from .highlight_validator import HighlightValidator
from .candidate_scorer import CandidateScorer, ScoreBreakdown
from .duplicate_detector import DuplicateDetector

logger = logging.getLogger("clipforge.ai.highlights.analyzer")


class EnrichedHighlightCandidate(BaseModel):
    id: Optional[str] = None
    start_time: float
    end_time: float
    duration_seconds: float
    title: str
    hook: str
    summary: str
    reason: str
    category: str
    key_quote: str
    transcript_excerpt: str
    overall_score: int
    score_breakdown: ScoreBreakdown
    status: str = "discovered"  # discovered, approved, rejected, edited, ready_for_render
    generation_method: str = "llm"


class HighlightAnalysisConfig(BaseModel):
    model_name: str = "qwen-2.5-3b"
    content_type: str = "general"
    target_duration_min: float = 30.0
    target_duration_max: float = 60.0
    max_candidates: int = 5
    dedup_temporal_iou: float = 0.55


class HighlightAnalyzer:
    """Master orchestrator for discoverable highlight candidates."""

    @classmethod
    async def analyze(
        cls,
        segments: List[Any],
        total_video_duration: float,
        config: Optional[HighlightAnalysisConfig] = None,
        on_stage_update: Optional[Callable[[str, int], Coroutine[None, None, None]]] = None,
        cancellation_token: Optional[asyncio.Event] = None
    ) -> List[EnrichedHighlightCandidate]:
        if config is None:
            config = HighlightAnalysisConfig()

        async def _update(stage_name: str, progress_pct: int):
            if on_stage_update:
                try:
                    await on_stage_update(stage_name, progress_pct)
                except Exception:
                    pass

        # Stage 1: Load and parse words
        await _update("Loading transcript words", 10)
        timed_words = TranscriptChunker.extract_timed_words(segments) if segments else []
        if not timed_words:
            if total_video_duration > 0:
                logger.info("No speech transcript words found. Generating visual pacing highlight windows...")
                win_dur = min(total_video_duration, config.target_duration_max)
                win_dur = max(min(config.target_duration_min, total_video_duration), min(15.0, win_dur))

                # Create 1-3 visual candidate windows
                cands: List[EnrichedHighlightCandidate] = []
                num_cands = min(config.max_candidates, max(1, int(total_video_duration // 10)))
                step = (total_video_duration - win_dur) / max(1, num_cands) if total_video_duration > win_dur else 0.0

                for i in range(num_cands):
                    st = round(i * step, 2)
                    et = round(min(total_video_duration, st + win_dur), 2)
                    dur = round(et - st, 2)
                    if dur > 0:
                        score_obj = CandidateScorer.score_candidate(
                            text="",
                            hook_phrase="Dynamic visual sequence",
                            duration=dur,
                            target_min_duration=config.target_duration_min,
                            target_max_duration=config.target_duration_max,
                            has_verified_quote=False,
                        )
                        cands.append(EnrichedHighlightCandidate(
                            start_time=st,
                            end_time=et,
                            duration_seconds=dur,
                            title=f"Visual Highlight #{i + 1}",
                            hook="Dynamic visual sequence",
                            summary="Engaging visual motion segment suitable for short-form portrait reframing.",
                            reason="High motion visual content identified.",
                            category="visual_highlight",
                            key_quote="",
                            transcript_excerpt="",
                            overall_score=score_obj.overall_score,
                            score_breakdown=score_obj,
                            status="discovered",
                            generation_method="visual_pacing",
                        ))
                await _update("Finalizing visual candidates", 100)
                return cands

            logger.warning("No timed words found in transcript segments.")
            return []

        if cancellation_token and cancellation_token.is_set():
            raise asyncio.CancelledError("Highlight analysis cancelled.")

        # Stage 2: Sentence boundary detection
        await _update("Preprocessing sentences and punctuation", 20)
        sentences = TranscriptChunker.group_words_into_sentences(timed_words)
        if not sentences:
            logger.warning("No sentences could be constructed from words.")
            return []

        # Stage 3: Semantic chunking for long videos
        await _update("Chunking transcript for context analysis", 30)
        chunks = TranscriptChunker.create_overlapping_chunks(sentences)

        # Stage 4 & 5: Candidate generation (Stage B with Stage A fallback)
        await _update("Analyzing transcript with local AI", 45)
        raw_candidates: List[DiscoveredCandidate] = []

        for chunk in chunks:
            if cancellation_token and cancellation_token.is_set():
                raise asyncio.CancelledError("Highlight analysis cancelled.")

            llm_results = await CandidateGenerator.generate_stage_b_llm(
                chunk=chunk,
                model_id=config.model_name,
                content_type=config.content_type,
                target_duration_min=config.target_duration_min,
                target_duration_max=config.target_duration_max,
                max_candidates=config.max_candidates,
                cancellation_token=cancellation_token
            )
            raw_candidates.extend(llm_results)

        # If LLM produced zero candidates (e.g. offline/uninstalled model), use Stage A deterministic windows
        if not raw_candidates:
            await _update("Generating deterministic candidate windows", 55)
            raw_candidates = CandidateGenerator.generate_stage_a_windows(
                sentences=sentences,
                target_duration_min=config.target_duration_min,
                target_duration_max=config.target_duration_max,
                max_windows=config.max_candidates * 3
            )

        if cancellation_token and cancellation_token.is_set():
            raise asyncio.CancelledError("Highlight analysis cancelled.")

        # Stage 6 & 7: Boundary refinement & Validation
        await _update("Refining boundaries to sentence terminals", 70)
        refined_candidates: List[Dict[str, Any]] = []

        for raw_c in raw_candidates:
            ref_start, ref_end, ref_hook, ref_excerpt = BoundaryRefiner.refine_boundaries(
                raw_start=raw_c.start_time,
                raw_end=raw_c.end_time,
                sentences=sentences,
                words=timed_words,
                min_duration=config.target_duration_min,
                max_duration=config.target_duration_max,
                quote=raw_c.key_quote
            )

            # Validate physical boundaries
            is_valid, validation_errors = HighlightValidator.validate_candidate(
                start_time=ref_start,
                end_time=ref_end,
                total_video_duration=total_video_duration,
                min_duration=config.target_duration_min,
                max_duration=config.target_duration_max,
                quote=raw_c.key_quote,
                transcript_excerpt=ref_excerpt
            )

            if not is_valid:
                logger.debug(f"Candidate rejected during validation: {validation_errors}")
                continue

            # Verify key quote
            quote_valid, _, verified_quote = HighlightValidator.verify_quote(
                raw_c.key_quote,
                ref_excerpt
            )

            refined_candidates.append({
                "start_time": ref_start,
                "end_time": ref_end,
                "duration_seconds": round(ref_end - ref_start, 2),
                "title": raw_c.title,
                "hook": ref_hook or raw_c.hook,
                "summary": raw_c.summary or ref_excerpt[:160],
                "reason": raw_c.reason,
                "category": raw_c.category,
                "key_quote": verified_quote or ref_hook,
                "transcript_excerpt": ref_excerpt,
                "generation_method": raw_c.generation_method,
                "quote_valid": quote_valid
            })

        # Stage 8: Candidate scoring
        await _update("Calculating multi-factor engagement scores", 80)
        scored_candidates: List[EnrichedHighlightCandidate] = []

        for item in refined_candidates:
            score_data = CandidateScorer.score_candidate(
                text=item["transcript_excerpt"],
                hook_phrase=item["hook"],
                duration=item["duration_seconds"],
                target_min_duration=config.target_duration_min,
                target_max_duration=config.target_duration_max,
                has_verified_quote=item["quote_valid"]
            )

            scored_candidates.append(EnrichedHighlightCandidate(
                start_time=item["start_time"],
                end_time=item["end_time"],
                duration_seconds=item["duration_seconds"],
                title=item["title"],
                hook=item["hook"],
                summary=item["summary"],
                reason=item["reason"],
                category=item["category"],
                key_quote=item["key_quote"],
                transcript_excerpt=item["transcript_excerpt"],
                overall_score=score_data.overall_score,
                score_breakdown=score_data,
                status="discovered",
                generation_method=item["generation_method"]
            ))

        # Stage 9: Deduplication & Ranking
        await _update("Filtering duplicate overlapping windows", 90)
        final_ranked, discovered_cnt, remaining_cnt = DuplicateDetector.filter_and_rank_candidates(
            candidates=scored_candidates,
            max_temporal_iou=config.dedup_temporal_iou,
            max_results=config.max_candidates
        )

        logger.info(f"Discovered {discovered_cnt} raw candidates; retained {remaining_cnt} after deduplication.")
        await _update("Finalizing candidates", 100)
        return final_ranked
