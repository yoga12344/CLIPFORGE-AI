import math
from pathlib import Path
from typing import List
from ..models.schemas import TranscriptSegment, WordTimestamp

def format_ass_timestamp(seconds: float) -> str:
    """Format seconds into ASS timestamp format: H:MM:SS.cs"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

class SubtitleGenerator:
    @staticmethod
    def generate_ass(
        segments: List[TranscriptSegment],
        clip_start: float,
        clip_end: float,
        output_file: str,
        style_preset: str = "karaoke_yellow"
    ) -> str:
        """
        Generate an Advanced SubStation Alpha (.ass) subtitle file with word-level karaoke timing.
        clip_start and clip_end are used to offset timestamps relative to the cut video (0.0s).
        """
        # Collect relevant words within [clip_start, clip_end]
        all_words: List[WordTimestamp] = []
        for s in segments:
            for w in s.words:
                if w.start >= clip_start - 0.2 and w.end <= clip_end + 0.5:
                    all_words.append(w)
                    
        # Group words into chunks of 3-5 words for fast-paced vertical video reading
        CHUNK_SIZE = 4
        word_chunks = [all_words[i:i + CHUNK_SIZE] for i in range(0, len(all_words), CHUNK_SIZE)]

        # Determine colors (ASS color format: &HAABBGGRR)
        if style_preset == "karaoke_green":
            active_color = "&H0000FF00"  # Neon Green
            inactive_color = "&H00FFFFFF" # White
        elif style_preset == "minimal_white":
            active_color = "&H00FFFFFF"
            inactive_color = "&H00D0D0D0"
        else: # karaoke_yellow
            active_color = "&H0000FFFF"  # Vibrant Yellow
            inactive_color = "&H00FFFFFF" # White

        header = f"""[Script Info]
Title: ClipsMaster Viral Karaoke
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,68,{inactive_color},{active_color},&H00000000,&H80000000,1,0,0,0,100,100,2,0,1,6,3,2,60,60,450,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        events = []

        for chunk in word_chunks:
            if not chunk:
                continue
                
            chunk_start_abs = chunk[0].start
            chunk_end_abs = chunk[-1].end
            
            # Offset to clip relative timeline
            rel_chunk_start = max(0.0, chunk_start_abs - clip_start)
            rel_chunk_end = max(rel_chunk_start + 0.3, chunk_end_abs - clip_start)
            
            # For each word in the chunk, generate an active highlight state
            for i, target_word in enumerate(chunk):
                w_start_rel = max(0.0, target_word.start - clip_start)
                w_end_rel = max(w_start_rel + 0.1, target_word.end - clip_start)
                
                # Construct line with current word highlighted
                line_parts = []
                for j, w in enumerate(chunk):
                    clean_word = w.word.upper()
                    if j == i:
                        # Highlighted active word with pop effect
                        line_parts.append(f"{{\\c{active_color}\\fscx108\\fscy108}}{clean_word}{{\\r}}")
                    else:
                        line_parts.append(f"{{\\c{inactive_color}}}{clean_word}")

                text_line = " ".join(line_parts)
                start_str = format_ass_timestamp(w_start_rel)
                end_str = format_ass_timestamp(w_end_rel)
                
                events.append(
                    f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{text_line}"
                )

        content = header + "\n".join(events) + "\n"
        
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content)
            
        return output_file
