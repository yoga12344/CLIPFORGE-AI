# Phase 9 Stage 6: Professional Subtitle Composition

## Overview
Phase 9 Stage 6 implements broadcast-grade subtitle and captions composition for ClipForge AI. Captions are vital for viewer retention in vertical short-form video (TikTok, YouTube Shorts, Reels), where over 70% of viewers watch without headphones or in noisy environments. The subtitle engine transforms word-level transcribed timings, speaker diarization tags, and visual face tracking coordinates into dynamic, responsive SubStation Alpha (.ass) scripts burned directly into the final render graph.

---

## 1. Core Architecture & Modules

The subtitle composition system consists of four coordinated modules in `backend/app/composition/subtitles/`:

### A. Subtitle Presets & Style Resolver (`subtitle_presets.py`)
- **8 Distinctive Broadcast Presets**:
  - `preset_bold_creator`: Arial Black, 72pt, vibrant yellow pop highlight, thick outline. (Default viral creator style)
  - `preset_clean_minimal`: Arial, 58pt, sky cyan highlight, subtle outline.
  - `preset_podcast_highlight`: Trebuchet MS, 64pt, warm orange highlight.
  - `preset_cinematic`: Georgia italic, 56pt, soft gold and amber tones.
  - `preset_gaming`: Impact, 74pt, cyber green pop highlight.
  - `preset_educational`: Segoe UI, 60pt, royal blue highlight.
  - `preset_classic_subtitles`: Standard clean white subtitles, static display.
  - `preset_high_contrast`: Crimson red pop against bright yellow text.
- **Dynamic Style Overrides (`SubtitleStyleOverrides`)**: Allows overriding font family, font size, primary/highlight/outline colors, outline/shadow widths, bold/italic flags, max words per line, and animation styles.
- **Per-Speaker Palettes & Overrides**: Distinguishes speakers by binding distinct accent colors (Speaker 0 = Yellow, Speaker 1 = Sky Cyan, Speaker 2 = Emerald Green, Speaker 3 = Coral Orange) or explicit per-speaker styles defined in `SubtitleCompositionConfig.speaker_styles`.

### B. Dynamic Collision Avoidance Planner (`collision_avoidance.py`)
In vertical video (1080x1920), bottom-anchored subtitles naturally occupy the lower third ($Y \in [1500, 1750]$). If an active speaker leans into the lower portion of the frame or a close-up crop places a face in the lower third, subtitles occluding the face ruin visual presentation:
- **Spatial Overlap Detection**: Evaluates face bounding box intervals $[Y_{\text{top}}, Y_{\text{bottom}}]$ against subtitle bounding box $[Y_{\text{sub\_top}}, Y_{\text{sub\_bottom}}]$ factoring in minimum safety clearance gap (`min_clearance_fraction`, default 2%).
- **Adaptive Upward Shifting**: When collision occurs and the face top is above $Y = 1150$, the planner calculates an adjusted bottom margin `margin_v`, pushing the subtitle box safely above the subject's face.
- **Safe Relocation Fallback**: If the face occupies the lower 60% of the canvas, pushing upward would place captions awkwardly in the middle of the chest/face. The planner relocates the dialogue to `top_safe` (alignment 8, top-center margin).

### C. Word Karaoke Generator (`karaoke_generator.py`)
- **Microsecond Precision**: Ingests `SubtitleWordRef` microsecond boundaries (`start_us`, `end_us`) and converts to centisecond ASS timestamps (`H:MM:SS.cs`).
- **Viral Animation Modes**:
  - `karaoke_pop`: Highlight active word with scale pop (`{\c<highlight>\fscx110\fscy110}<word>{\r}`) while keeping preceding/succeeding words in primary color.
  - `word_by_word`: Progressive word reveal highlighting current word and dimming future words.
  - `phrase_fade`: Smooth alpha fade-in and fade-out per phrase (`{\fad(150,150)}`).
  - `static`: Clean phrase-level text display.
- **V4+ Styles Compilation**: Emits full ASS v4+ headers with separate styles per speaker (`Style: SPEAKER_00`, `Style: SPEAKER_01`) and per-dialogue positioning overrides (`\an`, `MarginV`).

### D. Subtitle Service & Render Graph Integration (`subtitle_service.py` & `graph_builder.py`)
- Emits atomic `.ass` files to the composition's artifact folder.
- Injects `SubtitleBurnNode` into the video pipeline in `CompositionToGraphBuilder`, safely escaping Windows paths for FFmpeg's `ass=filename='...'` filter.

---

## 2. Benchmark & Test Verification

Full test coverage in `backend/tests/test_phase9_stage6.py`:
- 8 tests validating preset registry, style overrides, speaker styles, karaoke pop timing, animation variants, collision avoidance margin shifting, top relocation, and real FFmpeg rendering with burned subtitles.
- Real rendering verified via `OutputValidator` and `ffprobe`.
