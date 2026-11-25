"""
ClipForge AI - Two-Stage Candidate Generator
Implements Stage A (Deterministic Window Generation) and Stage B (Local LLM Semantic Analysis).
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from .transcript_chunker import TimedSentence, TimedWord, TranscriptChunk
from ..llm.inference_manager import LLMInferenceManager
from ..llm.model_manager import LLMModelManager
from ..llm.prompt_templates import build_highlight_prompt, SYSTEM_PROMPT_BASE
from ..llm.structured_output import parse_and_validate_candidates, RawCandidateItem

logger = logging.getLogger("clipforge.ai.highlights.generator")


class DiscoveredCandidate(BaseModel):
    start_time: float
    end_time: float
    duration_seconds: float
    title: str
    hook: str
    summary: str
    reason: str
    category: str = "general"
    key_quote: str = ""
    transcript_excerpt: str = ""
    generation_method: str = "llm"  # "llm" or "deterministic_stage_a"
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)


class CandidateGenerator:
    """Coordinates deterministic window generation and LLM semantic discovery."""

    @classmethod
    def generate_stage_a_windows(
        cls,
        sentences: List[TimedSentence],
        target_duration_min: float = 30.0,
        target_duration_max: float = 60.0,
        max_windows: int = 15
    ) -> List[DiscoveredCandidate]:
        """
        Stage A: Deterministic candidate window generation.
        Combines adjacent sentences into valid candidate duration blocks.
        """
        candidates: List[DiscoveredCandidate] = []
        if not sentences:
            return []

        for start_idx in range(len(sentences)):
            curr_start = sentences[start_idx].start_time
            accumulated_text = []

            for end_idx in range(start_idx, len(sentences)):
                sent = sentences[end_idx]
                accumulated_text.append(sent.text)
                curr_end = sent.end_time
                dur = curr_end - curr_start

                if dur >= target_duration_min:
                    if dur <= target_duration_max or (end_idx == start_idx):
                        # Valid window found
                        full_text = " ".join(accumulated_text)
                        first_sentence = sentences[start_idx].text
                        title = " ".join(first_sentence.split()[:6]) + "..."

                        candidates.append(DiscoveredCandidate(
                            start_time=round(curr_start, 2),
                            end_time=round(curr_end, 2),
                            duration_seconds=round(dur, 2),
                            title=title,
                            hook=first_sentence,
                            summary=full_text[:160] + "...",
                            reason="Natural speech topic block spanning complete sentences",
                            category="general",
                            key_quote=first_sentence,
                            transcript_excerpt=full_text,
                            generation_method="deterministic_stage_a",
                            strengths=["Complete sentence boundaries"],
                            weaknesses=[]
                        ))

                        if len(candidates) >= max_windows:
                            return candidates
                    else:
                        # Exceeded maximum duration
                        break

        return candidates

    @classmethod
    async def generate_stage_b_llm(
        cls,
        chunk: TranscriptChunk,
        model_id: str = "qwen-2.5-3b",
        content_type: str = "general",
        target_duration_min: float = 30.0,
        target_duration_max: float = 60.0,
        max_candidates: int = 4,
        cancellation_token: Optional[asyncio.Event] = None
    ) -> List[DiscoveredCandidate]:
        """
        Stage B: Call local LLM to perform deep semantic analysis on a transcript chunk.
        """
        # If model is not installed locally, return empty list so caller can fall back to Stage A
        status = LLMModelManager.check_model_status(model_id)
        if not status.is_installed:
            logger.info(f"Model '{model_id}' is not installed locally; skipping Stage B LLM inference.")
            return []

        prompt = build_highlight_prompt(
            transcript_text_with_timestamps=chunk.formatted_text_with_timestamps,
            content_type=content_type,
            target_duration_min=target_duration_min,
            target_duration_max=target_duration_max,
            max_candidates=max_candidates
        )

        inference_mgr = LLMInferenceManager.get_instance()
        try:
            raw_output = await inference_mgr.execute_inference(
                model_id=model_id,
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT_BASE,
                max_tokens=1024,
                temperature=0.2,
                cancellation_token=cancellation_token
            )

            parsed = parse_and_validate_candidates(raw_output)
            results: List[DiscoveredCandidate] = []

            for item in parsed.candidates:
                dur = item.end_time - item.start_time
                results.append(DiscoveredCandidate(
                    start_time=round(item.start_time, 2),
                    end_time=round(item.end_time, 2),
                    duration_seconds=round(dur, 2),
                    title=item.title.strip(),
                    hook=item.hook or item.title,
                    summary=item.summary or "",
                    reason=item.reason or "",
                    category=item.category or content_type,
                    key_quote=item.key_quote or "",
                    transcript_excerpt="",  # Will be populated by boundary refiner
                    generation_method="llm",
                    strengths=item.strengths,
                    weaknesses=item.weaknesses
                ))

            logger.info(f"LLM generated {len(results)} raw candidates for chunk {chunk.chunk_index}.")
            return results

        except Exception as e:
            logger.warning(f"Stage B LLM analysis encountered error: {e}. Falling back to Stage A windows.")
            return []
