# ClipForge AI — Phase 7 Implementation Plan
**Professional Subtitle Styling, Karaoke Highlighting & Final Render Pipeline**

---

## 1. Overview & Architecture Strategy

Phase 7 introduces a local-first, broadcast-quality subtitle styling, word-level karaoke animation, and final video rendering pipeline to ClipForge AI.

The user can take an approved AI highlight or clip, transform source transcript segments into clip-relative subtitle tracks, edit word-level text and timing, choose from 8+ professional styling presets, customize typography/colors/shadows/outlines, preview karaoke highlighting synchronized to video playback, and render the final vertical/social MP4 using hardware-accelerated or CPU libx264 encoding with dynamic smart reframing trajectories.

---

## 2. Component Reuse & New Modules

### Reused Modules
- `backend/app/video/ffmpeg_manager.py`: Safe subprocess execution, PID tracking, live progress parsing.
- `backend/app/video/ffprobe_manager.py`: Technical stream inspection and verification.
- `backend/app/video/clip_generator.py`: Video cutting, scaling, and trajectory filtergraphs.
- `backend/app/video/aspect_ratio.py`: Multi-ratio framing (9:16, 1:1, 4:5, 16:9).
- `backend/app/video/capabilities.py`: Hardware encoder checks (NVENC vs libx264, libass availability).
- `backend/app/workers/job_manager.py` & `job_executor.py`: Persistent background job execution and cancellation.
- `backend/app/workers/job_events.py`: WebSocket progress broadcasting.
- `src/components/video/VideoPlayer.tsx`: Playback and custom overlay container.
- `src/pages/ProjectStudio.tsx`: Tabbed studio host.

### New Modules
- `backend/app/schemas/subtitle_schemas.py`: Pydantic models for subtitle tracks, timed words, editing, presets, and export requests.
- `backend/app/services/subtitle_renderer.py`: ASS file synthesis, style declarations, karaoke tag generation (`{\k...}` / color pops), escaping, line-wrapping, and Windows font fallback.
- `backend/app/services/subtitle_service.py`: Extraction of clip-relative subtitle tracks from source transcripts, validation, word timestamp editing, split/merge, and preset CRUD.
- `backend/app/services/export_service.py`: Coordinated rendering orchestrator (source cut -> crop trajectory -> scale -> burn ASS subtitles -> encode -> verify with ffprobe -> save Export record).
- `backend/app/api/routes/subtitles.py`: FastAPI endpoints for subtitle tracks, segment editing, and presets.
- `backend/app/api/routes/exports.py`: FastAPI endpoints for triggering renders, polling export status, and streaming exported MP4s.
- `src/components/subtitles/`: Reusable React components:
  - `SubtitleEditor.tsx`: Interactive transcript editor with word-level click-to-edit, segment split/merge.
  - `CaptionPresetGallery.tsx`: Visual cards for 8 built-in presets (Clean Minimal, Bold Creator, Podcast Highlight, etc.).
  - `CaptionStyleEditor.tsx`: Font family, font size, primary/highlight/outline/shadow colors, alignment, margins.
  - `SubtitlePreviewOverlay.tsx`: Interactive preview overlay on video player with live karaoke highlighting.
  - `ExportModal.tsx`: Render resolution, quality profile, subtitle burn toggle, and render progress tracking.

---

## 3. Database Schema Extensions

### 1. `CaptionPreset` (Enhanced)
Ensure all required styling attributes exist:
- `id`, `name`, `font_family`, `font_size`
- `primary_color` (ASS hex `&H00FFFFFF`)
- `highlight_color` (ASS hex `&H0000FFFF`)
- `outline_color` (ASS hex `&H00000000`)
- `outline_width`, `shadow_width`
- `alignment` (1–9 numpad alignment: 2 = bottom-center, 5 = middle-center, 8 = top-center)
- `margin_v`, `margin_l`, `margin_r`
- `max_words_per_line` (default: 3–4 for vertical video)
- `max_lines` (default: 2)
- `bold`, `italic`
- `animation_style` (`karaoke_pop`, `word_by_word`, `phrase_fade`, `static`)
- `is_default`, `created_at`

### 2. `SubtitleTrack` (New Model)
1:1 relationship with `Clip`:
- `id`: UUID primary key
- `clip_id`: ForeignKey("clips.id", ondelete="CASCADE"), unique
- `preset_id`: ForeignKey("caption_presets.id", ondelete="SET NULL"), nullable
- `is_enabled`: Boolean (default=True)
- `style_overrides`: JSON (nullable=True, stores custom colors/fonts if modified)
- `segments`: JSON (list of subtitle segments in clip-relative time with word-level timings)
- `created_at`, `updated_at`: DateTime

### 3. `Export` (Updated)
- `preset_id`: ForeignKey("caption_presets.id", ondelete="SET NULL"), nullable
- `duration_seconds`: Float
- `subtitle_settings`: JSON (snapshot of styling applied during render)
- `error_message`: Text

---

## 4. Subtitle Timing & Karaoke Transformation

For clip starting at $s$ and ending at $e$:
1. **Timestamp Normalization:**
   $$\text{clip\_time} = t - s$$
2. **Boundary Filtering:**
   Only words where $s - 0.2 \le w_{\text{start}}$ and $w_{\text{end}} \le e + 0.3$ are included.
3. **Line Chunking:**
   Words are grouped into concise phrases (3–5 words) optimal for vertical mobile reading.
4. **ASS Karaoke Syntax:**
   $$\text{Dialogue: } 0, \text{Start}, \text{End}, \text{Default},, 0, 0, 0,, \{\backslash\text{c}\&\text{H0000FFFF}\& \backslash\text{fscx}110 \backslash\text{fscy}110\}\text{ACTIVE}\{\backslash\text{r}\} \dots$$
   Centisecond duration karaoke tags: `{\k<cs>}`.
5. **Path Escaping in FFmpeg on Windows:**
   `ass=filename='C\:/path/to/sub.ass'` (backslashes to forward slashes, drive colon escaped).

---

## 5. Implementation Stages & Verification Strategy

- **Stage 2**: Subtitle data model, database models, Pydantic schemas.
- **Stage 3**: Subtitle service, transcript-to-clip time conversion, split/merge, validation.
- **Stage 4**: Preset catalog (8 distinctive styles) and typography discovery.
- **Stage 5**: ASS subtitle renderer with karaoke generation and path escaping.
- **Stage 6**: React Subtitle Editor, Preset Gallery, Style Controls, and live Karaoke Preview.
- **Stage 7**: Final Render Pipeline integration with `ClipGenerator`, smart crop trajectories, and `ass` filter.
- **Stage 8**: Export Service, background render jobs, and API routes.
- **Stage 9**: Real-video acceptance test (`backend/acceptance_phase7_real.py`).
- **Stage 10**: Full Phase 1–7 regression suite (`pytest backend/tests/ -v`).
