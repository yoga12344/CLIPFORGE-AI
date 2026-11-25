# Phase 9 Stage 7: B-Roll & Visual Overlays

## Overview
Phase 9 Stage 7 implements B-roll cutaways and graphic image overlays for ClipForge AI. In professional short-form content, inserting contextual visual cutaways (B-roll) over dialogue maintains audience engagement and visual pacing. Additionally, branding elements such as channel badges, logos, and lower-third graphic watermarks establish creator identity.

---

## 1. Core Architecture & Modules

The overlay system consists of three modules in `backend/app/composition/overlays/`:

### A. Semantic B-Roll Matcher (`broll_matcher.py`)
- **Transcript Token Extraction**: Scans subtitle segments for high-value semantic tokens while filtering out common conversational stopwords.
- **Tag & Keyword Overlap**: Matches spoken keywords against indexed B-roll library tags and descriptions.
- **Pacing & Cadence Controls**: Enforces configurable minimum spacing gaps between successive B-roll cutaways (`min_gap_between_brolls_us`) and bounds cutaway lengths (`min_broll_duration_us` to `max_broll_duration_us`).

### B. Overlay Planner (`overlay_planner.py`)
- **Canvas Geometry Calculation**: Translates `NormalizedRect` bounds (x, y, width, height) into exact pixel values on the delivery canvas (e.g. 1080x1920) while guaranteeing even dimension constraints required by H.264 encoders.
- **Display Modes**:
  - `full_frame_cutaway`: Full canvas dimensions ($1080 \times 1920$) placed at $(0, 0)$.
  - `pip_inset`: Scaled reaction/reference inset placed at configured coordinates.
- **FFmpeg Enable Timing**: Formats microsecond timestamps into second-based filter expressions `between(t, start_s, end_s)` for frame-accurate appearance and disappearance.

### C. Render Graph Integration (`graph_builder.py`)
- Dynamically injects `VideoInputNode`, `VideoTrimNode`, `SetPTSNode`, `FPSNormalizeNode`, `ScaleNode`, and `OverlayNode` into the video pipeline for B-roll cutaways.
- Injects `ImageInputNode`, `ScaleNode`, and `OverlayNode` (`eof_action=repeat`) for still image watermarks and logos.
- Maintains strict visual layer ordering: Base video $\rightarrow$ B-roll cutaways $\rightarrow$ Graphic watermarks $\rightarrow$ Subtitle burning. This guarantees subtitles always render visibly on top of cutaways.

---

## 2. Test Verification Summary

Full test coverage in `backend/tests/test_phase9_stage7.py`:
- `test_broll_matcher_keyword_overlap`: Semantic tag matching and cadence validation.
- `test_overlay_planner_coordinates`: Pixel coordinate transformation and enable expression formatting.
- `test_render_with_broll_cutaway_real_ffmpeg`: Real FFmpeg rendering of full-frame B-roll cutaway into 1080x1920 video.
- `test_render_with_graphic_watermark_real_ffmpeg`: Real FFmpeg rendering of PNG graphic watermark.
- `test_render_composite_broll_watermark_and_subtitles`: End-to-end composite rendering simultaneously combining main video, B-roll cutaway, logo watermark, and burned karaoke subtitles.
