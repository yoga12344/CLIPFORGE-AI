"""
ClipForge AI - Transcript Preprocessor and Semantic Chunker
Groups word-level timestamps into grammatically bounded sentences and overlapping semantic chunks.
"""

import logging
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("clipforge.ai.highlights.chunker")


class TimedWord(BaseModel):
    word: str
    start: float
    end: float
    prob: Optional[float] = None


class TimedSentence(BaseModel):
    sentence_index: int
    text: str
    start_time: float
    end_time: float
    words: List[TimedWord] = Field(default_factory=list)
    has_terminal_punct: bool = False
    pause_after: float = 0.0


class TranscriptChunk(BaseModel):
    chunk_index: int
    start_time: float
    end_time: float
    sentences: List[TimedSentence] = Field(default_factory=list)
    formatted_text_with_timestamps: str = ""
    word_count: int = 0


class TranscriptChunker:
    """Preprocesses raw transcript segments and groups them into sentences and overlapping chunks."""

    @classmethod
    def extract_timed_words(cls, segments: List[Any]) -> List[TimedWord]:
        """Extract a flat chronological list of words with timestamps."""
        words: List[TimedWord] = []
        for seg in segments:
            seg_words = []
            if hasattr(seg, "words") and seg.words:
                seg_words = seg.words
            elif isinstance(seg, dict) and "words" in seg:
                seg_words = seg["words"]

            for w in seg_words:
                if isinstance(w, dict):
                    word_str = w.get("word", "").strip()
                    start_t = float(w.get("start", 0.0))
                    end_t = float(w.get("end", start_t + 0.3))
                    prob = w.get("prob")
                else:
                    word_str = getattr(w, "word", "").strip()
                    start_t = float(getattr(w, "start", 0.0))
                    end_t = float(getattr(w, "end", start_t + 0.3))
                    prob = getattr(w, "prob", None)

                if word_str:
                    words.append(TimedWord(
                        word=word_str,
                        start=start_t,
                        end=end_t,
                        prob=prob
                    ))

        # Sort strictly by start time
        words.sort(key=lambda x: x.start)
        return words

    @classmethod
    def group_words_into_sentences(
        cls,
        words: List[TimedWord],
        max_pause_seconds: float = 0.65
    ) -> List[TimedSentence]:
        """
        Group words into sentences based on terminal punctuation (.?!),
        long inter-word pauses (> 0.65s), or excessive word count.
        """
        if not words:
            return []

        sentences: List[TimedSentence] = []
        current_sentence_words: List[TimedWord] = []
        sentence_idx = 0

        for i, word in enumerate(words):
            current_sentence_words.append(word)

            has_terminal = bool(re.search(r"[.?!][\"')\]]?$", word.word))
            is_last_word = (i == len(words) - 1)

            # Check pause to next word
            pause_to_next = 0.0
            if not is_last_word:
                next_word = words[i + 1]
                pause_to_next = max(0.0, next_word.start - word.end)

            # Split condition: terminal punct OR significant pause (> 0.65s) OR long run without punct (> 25 words)
            should_split = (
                has_terminal
                or (pause_to_next >= max_pause_seconds and len(current_sentence_words) >= 3)
                or len(current_sentence_words) >= 30
                or is_last_word
            )

            if should_split and current_sentence_words:
                sent_text = " ".join(w.word for w in current_sentence_words).strip()
                sentences.append(TimedSentence(
                    sentence_index=sentence_idx,
                    text=sent_text,
                    start_time=current_sentence_words[0].start,
                    end_time=current_sentence_words[-1].end,
                    words=list(current_sentence_words),
                    has_terminal_punct=has_terminal,
                    pause_after=pause_to_next
                ))
                sentence_idx += 1
                current_sentence_words = []

        return sentences

    @classmethod
    def create_overlapping_chunks(
        cls,
        sentences: List[TimedSentence],
        target_chunk_duration: float = 120.0,  # 2 minutes ideal LLM context window
        overlap_sentences: int = 3             # 3 sentences overlap to avoid split stories
    ) -> List[TranscriptChunk]:
        """
        Chunk sentences into overlapping windows for long video processing.
        Never truncates; covers 100% of the speech timeline.
        """
        if not sentences:
            return []

        chunks: List[TranscriptChunk] = []
        start_idx = 0
        chunk_idx = 0

        while start_idx < len(sentences):
            current_chunk_sentences: List[TimedSentence] = []
            chunk_start_time = sentences[start_idx].start_time
            curr_idx = start_idx

            while curr_idx < len(sentences):
                sent = sentences[curr_idx]
                current_chunk_sentences.append(sent)
                chunk_duration = sent.end_time - chunk_start_time

                if chunk_duration >= target_chunk_duration and len(current_chunk_sentences) >= 6:
                    break
                curr_idx += 1

            # Format chunk text with timestamps for LLM prompt
            formatted_lines = []
            word_count = 0
            for s in current_chunk_sentences:
                formatted_lines.append(f"[{s.start_time:.1f}s - {s.end_time:.1f}s] {s.text}")
                word_count += len(s.words)

            chunk = TranscriptChunk(
                chunk_index=chunk_idx,
                start_time=current_chunk_sentences[0].start_time,
                end_time=current_chunk_sentences[-1].end_time,
                sentences=current_chunk_sentences,
                formatted_text_with_timestamps="\n".join(formatted_lines),
                word_count=word_count
            )
            chunks.append(chunk)
            chunk_idx += 1

            # Advance with overlap
            step = max(1, len(current_chunk_sentences) - overlap_sentences)
            start_idx += step

            # If the remaining sentences are few, wrap up
            if start_idx >= len(sentences) or (len(sentences) - start_idx) <= overlap_sentences:
                if curr_idx < len(sentences):
                    # Append remaining tail to last chunk
                    tail_sentences = sentences[start_idx:]
                    if tail_sentences and chunks:
                        for s in tail_sentences:
                            if s not in chunks[-1].sentences:
                                chunks[-1].sentences.append(s)
                                chunks[-1].end_time = s.end_time
                        # Re-format text
                        lines = [f"[{s.start_time:.1f}s - {s.end_time:.1f}s] {s.text}" for s in chunks[-1].sentences]
                        chunks[-1].formatted_text_with_timestamps = "\n".join(lines)
                break

        return chunks
