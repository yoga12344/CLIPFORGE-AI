# CLIPFORGE AI — DEVELOPMENT STATUS & ARCHITECTURE ROADMAP

**Current Build Status:** Green / Production Verified  
**Last Updated:** 2026-11-22  
**Active Milestone:** Phase 9: Complete Intelligent AI Video Composition Platform (Completed & Verified)  
**Total Automated Tests:** 252 Backend Passing + Full Frontend Next.js Suite (100% Pass Rate, 0 Failures, 0 Regressions)  
**Target Architecture:** Windows 11 Desktop (Electron + React + TypeScript + FastAPI + SQLite + ONNX Runtime CPU + FFmpeg)  

---

## 1. Phase Progression & Maturity Matrix

| Phase | Subsystem | Core Capabilities | Status | Test Coverage |
| :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | Foundation & Core Services | FastAPI server, async SQLite, Electron bridge, settings | **Accepted** | Tests 1–3 |
| **Phase 2** | Media Ingestion & Video Pipeline | Video upload, metadata inspection, FFmpeg/FFprobe | **Accepted** | Tests 4–7 |
| **Phase 3** | Job Queue & Background Worker | Persistent job manager, SQLite queue, status tracking | **Accepted** | Tests 8–15 |
| **Phase 4** | Speech Intelligence & ASR | faster-whisper (int8), word-level timestamps | **Accepted** | Tests 16–27 |
| **Phase 5** | AI Highlight Discovery Engine | Local GGUF LLM (Qwen-2.5 via llama.cpp), JSON parsing | **Accepted** | Tests 28–49 |
| **Phase 6** | Computer Vision & Face Tracking | OpenCV YuNet detector, spatial tracker, auto-reframe | **Accepted** | Tests 50–61 |
| **Phase 7** | Subtitle Styling & Final Render | libass subtitle renderer, karaoke animation, 9:16 export | **Accepted** | Tests 62–73 |
| **Phase 8 St. 2** | Audio Preprocessing & VAD | Canonical 16 kHz PCM cache, Silero VAD v4, zero-PTS sync | **Accepted** | Tests 74–92 |
| **Phase 8 St. 3** | Offline Speaker Diarization | 3D-Speaker CAM++ ONNX, cosine spectral clustering, turns | **Accepted** | Tests 93–127 |
| **Phase 8 St. 4** | AV Active Speaker Detection | MediaPipe Face Mesh ONNX, Lip Dynamics, Light-ASD ONNX, Fusion | **Accepted** | Tests 128–187 |
| **Phase 9 St. 1** | Composition Architecture & Audit | Unified CompositionSpec, Render Graph DAG, Data Models, Roadmap | **Accepted** | Architecture Design |
| **Phase 9 St. 2** | CompositionSpec v1.0 & Versioned DB | Pydantic AST, Microsecond Timebase, Version Snapshots, OCC, REST API | **Accepted** | Tests 188–203 |
| **Phase 9 St. 3** | Render Graph Compiler & Execution Harness | Typed DAG, Kahn's Sorter, .ffscript Generator, NVENC/CPU Fallback, Job Queue | **Accepted** | Tests 204–215 |
| **Phase 9 St. 4** | Intelligent Composition Planner & Reframing | Multi-Modal Subject Evaluator, Shot Framing, EMA Smoothing, Auto-Plan REST API | **Accepted** | Tests 216–226 |
| **Phase 9 St. 5** | Multi-Person Layout Engine | Dynamic Layout Selector, SplitScreen (V/H), Blurred-BG, PiP, XStack, Graph Builder | **Accepted** | Tests 227–233 |
| **Phase 9 St. 6** | Professional Subtitle Composition | 8 Broadcast Presets, Speaker Palettes, Dynamic Collision Avoidance, ASS Burn | **Accepted** | Tests 234–241 |
| **Phase 9 St. 7** | B-Roll & Visual Overlays | Semantic B-Roll Matcher, Graphic Watermarks, Cutaway Pipeline, Multi-Layer Compositing | **Accepted** | Tests 242–246 |
| **Phase 9 St. 8** | Audio Mixing & Mastering | Multi-Track Mixing (amix), Sidechain Ducking, Rumble Filter, EBU R128 (loudnorm) | **Accepted** | Tests 247–252 |
| **Phase 9 St. 9** | Interactive Composition Studio | React/TypeScript Desktop UI, 9:16 Canvas Simulation, Multi-Track Inspector, Export | **Accepted** | Production Next.js Build |
| **Phase 9 St. 10**| **Master Acceptance & Hardening** | **Full 252-Test Regression, Performance Benchmarks, Subprocess Hardening, Audit** | **Accepted** | **252/252 Passed (100%)** |

---

---

## 2. Phase 9 Stage 9: Interactive Composition Studio Highlights

Phase 9 Stage 9 implements the React/TypeScript desktop composition studio interface:
1. **Interactive 9:16 Portrait Canvas Viewport (`CompositionStudio.tsx`)**:
   - Visual simulation of vertical framing across single speaker reframing, vertical split-screen, horizontal split, blurred background, and picture-in-picture.
2. **Multi-Track Inspector Panel**:
   - Video track controls: layout mode switcher, EMA pan smoothing display, hold duration parameters.
   - Subtitle track controls: preset dropdown (8 broadcast presets), live styling preview, dynamic collision avoidance toggle.
   - Audio & mastering track controls: voice dialogue gain slider, 80 Hz high-pass filter toggle, BGM volume slider, voice sidechain ducking toggle, EBU R128 loudness target selector (-14.0 LUFS YouTube/TikTok, -16.0 LUFS Podcast).
   - Overlays track controls: logo watermark and B-roll cutaway toggles.
3. **Execution & Real-Time Progress**:
   - AI Auto-Plan button invoking `POST /api/compositions/auto-plan`.
   - Render & Export button with real-time multi-stage progress reporting and output playback.
4. **Desktop Navigation Integration**:
   - Sidebar navigation button and "Edit in Studio" shortcut on clip cards in `frontend/src/app/page.tsx`.
   - Verified via `next build` (zero TypeScript errors, clean production bundle).

---

---

## 2. Phase 9 Stage 8: Audio Mixing & Professional Finishing Highlights

Phase 9 Stage 8 implements multi-track audio mixing, voice-activated sidechain ducking, high-pass filtering, and EBU R128 broadcast loudness mastering:
1. **Audio Mixing & Decibel Math (`AudioMixPlanner`, `db_to_linear`)**:
   - High-precision conversion between dB volume adjustments and linear multiplier coefficients.
   - Dynamic ducking parameter computation for FFmpeg `sidechaincompress`.
2. **Broadcast Loudness Standards (`LoudnessMaster`)**:
   - Standard platform presets for YouTube Shorts (-14 LUFS, -1.0 dBTP, 7.0 LRA), TikTok, and Podcasts (-16 LUFS).
3. **DAG Audio Pipeline Extensions**:
   - `HighPassFilterNode` (`highpass=f=80`): Cleans up low-frequency microphone/environment rumble.
   - `ASplitNode` (`asplit=2`): Splits voice audio signal between sidechain compressor and main mix without duplicate files.
   - `SidechainCompressNode` (`sidechaincompress`): Attenuates music bed during active voice dialogue.
   - `AudioMixNode` (`amix`): Composites dialogue and ducked music seamlessly.
   - `LoudnessNormalizeNode` (`loudnorm`): Normalizes final mix to broadcast specs.
4. **Automated Verification**:
   - 6 automated unit and real FFmpeg rendering tests in `backend/tests/test_phase9_stage8.py` (100% pass).
   - Cumulative regression suite: **252/252 tests passing**.

---

---

## 2. Phase 9 Stage 7: B-Roll & Visual Overlays Highlights

Phase 9 Stage 7 implements professional B-roll cutaway scheduling, image watermark positioning, and multi-layer compositing:
1. **Semantic B-Roll Matcher (`BRollMatcher`)**:
   - Matches transcript dialogue tokens against indexed B-roll library tags and descriptions.
   - Automatically schedules cutaways with cadence protection (`min_gap_between_brolls_us`).
2. **Overlay Planner (`OverlayPlanner`)**:
   - Converts `NormalizedRect` definitions to pixel coordinates enforcing H.264 even-dimension requirements.
   - Generates second-accurate enable expressions `between(t, start_s, end_s)` for FFmpeg overlays.
3. **Multi-Layer Render Graph Compositing**:
   - Injects B-roll cutaway nodes and graphic watermark nodes into `CompositionToGraphBuilder`.
   - Maintains layer ordering: Base video $\rightarrow$ B-roll cutaways $\rightarrow$ Watermarks $\rightarrow$ Subtitles.
4. **Automated Verification**:
   - 5 automated unit and real FFmpeg rendering tests in `backend/tests/test_phase9_stage7.py` (100% pass).
   - Cumulative regression suite: **246/246 tests passing**.

---

---

## 2. Phase 9 Stage 6: Professional Subtitle Composition Highlights

Phase 9 Stage 6 implements the broadcast-grade subtitle composition and collision avoidance system:
1. **8 Broadcast Presets & Custom Overrides (`SubtitlePresetRegistry`)**:
   - `preset_bold_creator`, `preset_clean_minimal`, `preset_podcast_highlight`, `preset_cinematic`, `preset_gaming`, `preset_educational`, `preset_classic_subtitles`, `preset_high_contrast`.
   - Granular override support via `SubtitleStyleOverrides` (fonts, sizes, colors, outlines, shadows, animation styles).
2. **Per-Speaker Visual Differentiation**:
   - Automatic speaker color accenting (Yellow, Sky Cyan, Emerald Green, Coral Orange) and custom per-speaker style overrides.
3. **Dynamic Face Collision Avoidance (`CollisionAvoidancePlanner`)**:
   - Evaluates face bounding box intervals against subtitle bounds.
   - Dynamically shifts vertical margin upward to stay above faces, or relocates to `top_safe` (alignment 8) for large subjects.
4. **Viral Karaoke Generation (`SubtitleKaraokeGenerator`)**:
   - Microsecond precision timing with `karaoke_pop` active word scaling (`\fscx110\fscy110`), `word_by_word` reveal, `phrase_fade`, and `static` modes.
5. **Real FFmpeg Render Verification**:
   - 8 automated unit and real FFmpeg rendering tests in `backend/tests/test_phase9_stage6.py` (100% pass).
   - Cumulative regression suite: **241/241 tests passing**.

---

---

## 2. Phase 9 Stage 5: Multi-Person Layout Engine Highlights

Phase 9 Stage 5 implements the multi-subject spatial composition and complex filtergraph compilation:
1. **Dynamic Layout Selector (`LayoutSelector`)**:
   - Analyzes active face tracks, diarization turns, and spatial positions over temporal windows.
   - Intelligently recommends layouts: `single_speaker_reframed`, `split_vertical`, `split_horizontal`, `picture_in_picture`, `grid_2x2`, or `blurred_background`.
2. **Filter Graph Expansion (`nodes.py` & `filter_compiler.py`)**:
   - Added first-class node types: `SplitNode`, `OverlayNode`, `VStackNode`, `HStackNode`, `XStackNode`, and `BoxBlurNode`.
   - Compiles deterministic complex filter graphs with stream tagging and port validation.
3. **Graph Builder Layout Support (`CompositionToGraphBuilder`)**:
   - Auto-constructs multi-stream filter DAGs for vertical split-screen (stacked 1080x960), blurred background canvas, and picture-in-picture.
4. **Automated Verification**:
   - 7 automated tests in `backend/tests/test_phase9_stage5.py`, including real FFmpeg rendering executions.
   - Cumulative regression suite: **233/233 tests passing**.

---

---

## 2. Phase 9 Stage 4: Intelligent Composition Planner & Speaker-Aware Reframing Highlights

Phase 9 Stage 4 delivers the autonomous composition planning and camera reframing engine:
1. **Multi-Modal Subject Evaluation (`SubjectEvaluator`)**:
   - Integrates Phase 8 Stage 4 active speaker probabilities, Phase 8 Stage 3 acoustic diarization turns, Phase 6 YuNet face bounding boxes, and frame centrality.
   - Evaluates composite subject importance scores across arbitrary timeline timestamps.
2. **Shot Selector & Cinematic Pacing (`ShotSelector`)**:
   - Classifies framing into Close-Up, Medium Shot, or Wide Shot based on subject confidence and dialogue dynamics.
   - Enforces a 1.2s minimum hold duration preventing rapid jittery camera flips during short pauses or secondary laughs.
3. **Transition Planner & Aspect Ratio Geometry (`TransitionPlanner`)**:
   - Translates bounding boxes into exact 9:16 vertical crop windows ($0.5625$ aspect ratio in source pixels).
   - Enforces headroom positioning (~35% from top of crop).
   - Bounds pan velocity ($\le 0.40$ screen widths/s) and applies Exponential Moving Average smoothing ($\alpha = 0.15$).
   - Respects user-authored locked `ManualOverride` crops.
4. **End-to-End Orchestrator (`CompositionPlannerService`)**:
   - Fully automates `CompositionSpec` v1.0.0 generation from `HighlightCandidate` records or custom video ranges.
   - Generates microsecond-accurate word-level subtitle streams offset to clip timeline, default video/audio tracks, and delivery profiles.
   - Atomically persists `Composition` and initial `CompositionVersion` (version 1) in database.
5. **REST API Interface**:
   - `POST /api/compositions/auto-plan`: Autonomously plans compositions from candidate ID or custom video time spans.
6. **Automated Verification**:
   - 11 new automated unit and integration tests in `backend/tests/test_phase9_stage4.py` (100% pass).
   - Full regression suite: **226/226 tests passing**.

---

## 2. Phase 9 Stage 3: Render Graph Compiler & Execution Harness Highlights

Phase 9 Stage 3 implements deterministic FFmpeg rendering for compositions:
1. **Typed Render Graph DAG**:
   - `BaseNode`, port-level type safety (`StreamType.VIDEO`, `AUDIO`, `IMAGE`, `SUBTITLE`, `ENCODED_OUTPUT`), cycle detection via Kahn's algorithm with deterministic tie-breaking.
   - Comprehensive 12-rule validation checking connectivity, stream types, single-sink containment.
2. **Deterministic Filter Compiler & Script Generator**:
   - Compiles complex filter trees into `-filter_complex` expressions or writes `.ffscript` filter script files to bypass Windows 32,767 character command limits.
   - Robust Windows path formatting and colon escaping for libass subtitle filters (`C\\:/...`).
3. **Execution Harness & Resilience**:
   - Automatic hardware acceleration detection with seamless fallback from `h264_nvenc` to `libx264`.
   - Real-time progress monitoring parsing `-progress pipe:1` events into percentage updates.
   - Robust process cancellation with Windows process tree termination (`taskkill /F /T /PID`).
   - Crash recovery (`RenderRecoveryService`) reconciling interrupted renders on server start.
   - Post-flight output validation verifying stream parameters, duration, faststart, and A/V sync via FFprobe.
4. **REST API Endpoints**:
   - `/api/compositions/{id}/versions/{version_id}/compile`: Dry-run execution plan compilation.
   - `/api/compositions/{id}/versions/{version_id}/renders`: Submit rendering job to persistent queue.
   - `/api/compositions/{id}/renders`: Query render history.
   - `/api/compositions/{id}/renders/{render_id}`: Query status and metrics.
   - `/api/compositions/{id}/renders/{render_id}/cancel`: Cancel active rendering job.
   - `/api/compositions/{id}/renders/{render_id}/artifacts`: Retrieve output video artifacts.
5. **Automated Verification**:
   - 12 new automated unit and real FFmpeg rendering tests in `backend/tests/test_phase9_stage3.py` (100% pass).
   - Zero regressions across existing suite: **215/215 total tests passing**.

---

## 2. Phase 9 Stage 2: CompositionSpec v1.0 & Versioned Database Highlights

Phase 9 Stage 2 implements the production data modeling foundation for ClipForge AI:
1. **Canonical CompositionSpec v1.0.0**:
   - Pydantic V2 models for metadata, source media, rational timebase, clip boundaries, multi-track definitions, layout topologies, camera reframing plans, subtitle styling, B-roll overlays, audio mixing/ducking, and delivery profiles.
   - Microsecond integer precision (`us`) preventing IEEE 754 rounding drift across complex edits.
   - Project-scoped logical asset URI parser (`asset://<type>/<id>`) strictly enforcing sandbox boundaries and path traversal rejection.
   - Deterministic canonical JSON serialization and SHA-256 content hashing for cache keys and change detection.
2. **Persistent Versioned Database Architecture**:
   - 5 new SQLite tables: `compositions`, `composition_versions`, `composition_assets`, `composition_renders`, `render_artifacts`.
   - Non-destructive append-only versioning with optimistic concurrency control (`expected_version_number`) preventing dirty writes.
   - Non-destructive rollback restoring any historical version as a new linear snapshot.
   - Full SQLite cascading delete integrity (`PRAGMA foreign_keys = ON`).
3. **Composition REST API**:
   - Endpoints under `/api/compositions`: CRUD, version creation, OCC conflict detection (HTTP 409), version rollback, dry-run semantic validation (`/validate`), and project asset queries.
4. **Automated Verification**:
   - 16 new automated tests in `backend/tests/test_phase9_stage2.py` (100% pass).
   - Zero regressions across existing Phase 1–8 test suite: **203/203 total tests passing**.
