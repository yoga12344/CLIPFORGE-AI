# Phase 9: Composition Engine & Rendering Pipeline
## Document 1: Repository Audit & Subsystem Assessment

**Audit Date**: 2026-11-22  
**Auditor**: Principal Video Systems Architect & Senior Computer Vision Engineer  
**Workspace**: `c:\Users\yogac\Downloads\clipsmaster`  
**Test Suite Status**: 187 / 187 tests passing (100%), Clean TypeScript/Electron compile, Clean Python compile.

---

## 1. Executive Summary

A comprehensive architectural audit was conducted across all existing subsystems of ClipForge AI (Phases 1 through 8). The objective is to establish the foundation for **Phase 9: Unified Composition Engine & Multi-Track Rendering Pipeline**.

Phase 9 bridges the gap between approved highlight candidates (Phase 5), visual intelligence (Phase 6), broadcast-grade subtitles (Phase 7), and audio-visual speaker intelligence (Phase 8), compiling them into an editable, multi-track, professional composition rendered through a robust FFmpeg filtergraph.

---

## 2. Detailed Audit of Existing Phases (1 to 8)

### Phase 1 — Application Foundation & Architecture

| Component | Repository Path | Existing Functionality | Phase 9 Architectural Constraints & Reusability |
| :--- | :--- | :--- | :--- |
| **Electron Main** | `electron/main.ts` | Process lifecycle, window management, secure FastAPI child process spawning, port discovery (`BACKEND_PORT = 8000`), session token generation (`crypto.randomUUID()`). | Context isolation (`contextIsolation: true`, `nodeIntegration: false`) must be preserved. Renderer must never receive raw host filesystem write permissions. |
| **Preload Bridge** | `electron/preload.ts` | Context bridge exposing `window.electronAPI`: file dialogs (`openVideoDialog`, `openFolderDialog`), session query (`getBackendSession`), window controls. | All composition asset selection (B-roll, music, logos) must route through secure dialog IPC and return sanitized paths to the backend. |
| **FastAPI Lifecycle** | `backend/app/main.py` | Lifespan context manager initializing SQLite schema via `init_db()` and starting background `JobManager.get_instance().start()`. CORS middleware, static file mounts (`/storage/clips`, `/storage/thumbnails`, `/storage/projects`). | Composition rendering endpoints must integrate cleanly into FastAPI router under `/api/v1/composition`. |
| **Job Infrastructure** | `backend/app/workers/job_manager.py` | Asynchronous single-worker queue (`asyncio.Queue`), startup recovery of interrupted jobs, cooperative cancellation (`CancellationToken`), progress broadcasting. | Phase 9 composition rendering must execute as a persistent background `Job` with cooperative cancellation every frame/chunk. |
| **Job Event System** | `backend/app/workers/job_events.py` | PubSub WebSocket broadcaster (`/ws/jobs`) notifying Electron frontend of `progress_percent`, `stage_description`, `started`, `completed`, and `failed` events. | Reused directly for composition render progress updates. |
| **Hardware Monitor** | `backend/app/services/hardware.py` | CPU utilization, physical/virtual RAM monitoring via `psutil`, NVIDIA GPU VRAM and driver queries via `pynvml`. | Enables dynamic pre-flight render checks (RAM availability, GPU encoder capability). |

---

### Phase 2 — Dashboard, Projects & Media Management

| Component | Repository Path | Existing Functionality | Phase 9 Architectural Constraints & Reusability |
| :--- | :--- | :--- | :--- |
| **Project Model** | `backend/app/db/models.py` (`Project`) | Top-level workspace entity with cascading delete to `videos`, `clips`, `jobs`, `highlight_candidates`. | Composition entities (`Composition`, `CompositionVersion`) must belong to a `Project` with cascading deletion. |
| **Video Model** | `backend/app/db/models.py` (`Video`) | Source video metadata: `file_path`, `duration_seconds`, `width`, `height`, `fps`, `video_codec`, `audio_codec`, `has_audio`, `audio_channels`. | Source media is immutable. Compositions reference `Video` via foreign key without altering or moving original files. |
| **Video Service** | `backend/app/services/video_service.py` | Secure media import, unique file naming under `storage/clipforge_data/projects/{id}/`, path traversal defense. | Reused for importing external B-roll and audio assets into project asset folders. |
| **Storage Structure** | `backend/storage/clipforge_data/` | Structured local storage: `models/`, `projects/{id}/exports/`, `projects/{id}/thumbnails/`, `cache/`. | Phase 9 will introduce `projects/{id}/compositions/` and `projects/{id}/assets/`. |

---

### Phase 3 — Video Processing Engine

| Component | Repository Path | Existing Functionality | Phase 9 Architectural Constraints & Reusability |
| :--- | :--- | :--- | :--- |
| **FFmpegManager** | `backend/app/video/ffmpeg_manager.py` | Safe subprocess execution via `asyncio.create_subprocess_exec` (strictly **no `shell=True`**), clean Windows process tree cancellation (`taskkill /F /T /PID`), `-progress pipe:1` parsing. | **Core rendering backbone**. Reused directly for executing compiled composition filtergraphs. |
| **FFprobeManager** | `backend/app/video/ffprobe_manager.py` | Frame-accurate stream probe, PTS start time extraction, duration, color space, SAR/DAR, audio channels, variable frame rate detection. | **Critical for export validation** and source stream time-base normalization. |
| **AspectRatioProcessor** | `backend/app/video/aspect_ratio.py` | Generates static crop, fit-pad, and blur-background filter strings (`crop`, `scale`, `boxblur`, `overlay`). Dynamic piecewise linear crop interpolation. | *Limitation identified*: Employs deeply nested `if(lt(t,...))` strings in FFmpeg `-vf`. For multi-person layouts and complex transitions, a modular graph compiler is required. |
| **ClipGenerator** | `backend/app/video/clip_generator.py` | Slices source video with fast `-ss` seeking, audio copy or AAC re-encode. | Reusable for proxy extraction and preliminary trimming. |
| **CapabilityDetector** | `backend/app/video/capabilities.py` | Real hardware capability test: verifies NVENC (`h264_nvenc`) functionality with probe encoding; falls back to CPU `libx264`. | Mandatory pre-render check before committing to GPU rendering. |

---

### Phase 4 — Transcription & Alignment

| Component | Repository Path | Existing Functionality | Phase 9 Architectural Constraints & Reusability |
| :--- | :--- | :--- | :--- |
| **Transcript & Segments** | `backend/app/db/models.py` (`Transcript`, `TranscriptSegment`) | Stores full transcript text, language, model name, and segments with word-level JSON: `[{"word": str, "start": float, "end": float, "prob": float}]`. | **Word-level timestamps** provide the exact timing source for subtitle track compilation and B-roll alignment. |
| **TranscriptRepository** | `backend/app/services/transcript_repository.py` | Querying, segment editing, and time-range extraction. | Reused to slice transcript data relative to composition clip boundaries. |

---

### Phase 5 — AI Clip Intelligence & Highlight Discovery

| Component | Repository Path | Existing Functionality | Phase 9 Architectural Constraints & Reusability |
| :--- | :--- | :--- | :--- |
| **HighlightCandidate** | `backend/app/db/models.py` | Discovered clip candidate with `start_time`, `end_time`, `duration_seconds`, `hook`, `title`, `overall_score`, `category`, `status` (`discovered`, `approved`, `rejected`, `edited`, `ready_for_render`). | **Primary input to Phase 9**. An approved highlight candidate serves as the seed from which a default `CompositionSpec` is automatically initialized. |
| **HighlightService** | `backend/app/services/highlight_service.py` | State machine transitions, manual timestamp editing, quote verification, conversion of candidates to `Clip` records. | Extended in Phase 9 to support `create_composition_from_candidate()`. |

---

### Phase 6 — Visual Intelligence & Smart Reframing

| Component | Repository Path | Existing Functionality | Phase 9 Architectural Constraints & Reusability |
| :--- | :--- | :--- | :--- |
| **YuNetFaceDetector** | `backend/app/ai/vision/face_detector.py` | Fast ONNX face detector running at 4 FPS keyframes on CPU/GPU. | Provides raw face bounding boxes across the timeline. |
| **FaceTracker** | `backend/app/ai/vision/face_tracker.py` | Bipartite IoU matching + centroid distance tracking, generating stable `FaceTrack` entities across occlusions. | Tracks individual participant identities across time. |
| **SubjectSelector** | `backend/app/ai/vision/subject_selector.py` | Selection strategies: `largest_face`, `active_speaker`, `centroid`, `manual`. | Determines primary subject for single-speaker framing. |
| **ReframeEngine** | `backend/app/ai/vision/reframe_engine.py` | Computes aspect-ratio-accurate crop dimensions (9:16, 1:1, 4:5, 16:9), exponential moving average (EMA) smoothing, velocity limits, boundary clamping. | *Limitation identified*: Only supports a single rectangular crop window. Cannot render two-person split-screens, picture-in-picture, or speaker-switched multi-camera layouts. Phase 9 will wrap and expand this into a multi-camera layout planner. |
| **ManualCropCorrection** | `backend/app/db/models.py` | Keyframed manual bounding-box overrides by user. | **Must be strictly preserved** in Phase 9 composition specifications. |

---

### Phase 7 — Broadcast Subtitles & Final Export

| Component | Repository Path | Existing Functionality | Phase 9 Architectural Constraints & Reusability |
| :--- | :--- | :--- | :--- |
| **SubtitleRenderer** | `backend/app/services/subtitle_renderer.py` | Broadcast-grade Advanced SubStation Alpha (`.ass`) file generator. Supports 8 presets, karaoke word-by-word animation (`\k` tags), text escaping, Windows path escaping. | **Directly reused in Phase 9**. Phase 9 will generate the `.ass` script and burn it in as a dedicated render graph node. |
| **SubtitleTrack** | `backend/app/db/models.py` | Clip-relative subtitle segments, preset reference, style overrides. | Directly ingested into the composition's subtitle track. |
| **ExportService** | `backend/app/services/export_service.py` | Existing Phase 7 export coordinator: trims source video, constructs trajectory filter, burns ASS subtitles, encodes with `libx264` or `h264_nvenc`, validates with FFprobe. | *Limitation identified*: Monolithic single-command architecture tightly couples cropping, subtitles, and export into one hardcoded filter string. Phase 9 will replace this with the modular **Render Graph Compiler**. |

---

### Phase 8 — Audio-Visual Intelligence & Active Speaker Detection

| Component | Repository Path | Existing Functionality | Phase 9 Architectural Constraints & Reusability |
| :--- | :--- | :--- | :--- |
| **VoiceActivityDetector** | `backend/app/ai/audio/voice_activity_detector.py` | Silero VAD v4 ONNX streaming voice activity detection at 16 kHz. | Ingested for speech vs non-speech intervals. |
| **SpeakerDiarizer** | `backend/app/ai/audio/speaker_diarizer.py` | 3D-Speaker CAM++ ONNX embeddings + Spectral / Agglomerative clustering. | Identifies acoustic speaker identities (`SPEAKER_00`, `SPEAKER_01`). |
| **ActiveSpeakerService** | `backend/app/ai/audio_visual/active_speaker_service.py` | MediaPipe Face Mesh V2, lip dynamics (MAR), Light-ASD ONNX inference, audio-visual synchronization, and multi-evidence fusion. | **Foundational for intelligent camera framing**. Provides `ActiveSpeakerInterval` records and `get_primary_active_speaker_at(timestamp)`. |
| **SpeakerFaceAssociator** | `backend/app/ai/audio_visual/av_fusion_engine.py` | Global bipartite matching associating acoustic speakers with visual face tracks (`SpeakerFaceAssociation`), with manual override preservation. | Allows the composition engine to know: "When Speaker A speaks, show Face Track 1". |

---

## 3. Architecture Gaps & Limitations in Current Codebase

```
Current State (Phase 7):
  Approved Clip ───► ExportService ───► Single Monolithic Filtergraph ───► Output MP4
                                         (Fixed crop + ASS burn-in)

Proposed State (Phase 9):
  Approved Clip ───► CompositionPlanner ───► CompositionSpec (v1.0.0) ───► RenderGraphCompiler ───► Modular FFmpeg DAG ───► Output MP4
                           ▲                         │                                                     ▲
                           │                         ▼                                                     │
                     AI Recommendations     Frontend Studio Editor                                Hardware Auto-Fallback
                     (VAD, ASD, Diarization)  (Tracks, Layers, Canvas)
```

The audit revealed the following specific architectural gaps:

1. **Lack of a Unified Composition Model**:
   - Currently, a `Clip` contains only `start_time`, `end_time`, and `aspect_ratio`. Subtitles live in `SubtitleTrack`, while crop trajectories live in `VisionAnalysis`. There is no single serializable document that encapsulates camera layouts, multi-speaker framing, B-roll overlays, and audio mix settings.
2. **Monolithic Filtergraph Construction**:
   - `ExportService` constructs a single video filter string: `vf_base = AspectRatioProcessor.build_trajectory_filtergraph(...); vf_full = f"{vf_base},ass='...'"`
   - This approach cannot scale to:
     - Multi-person split screens (`xstack`, multiple crops from one input).
     - Picture-in-picture or B-roll overlays (`overlay=enable='between(t,...)'`).
     - Background music ducking against voice (`sidechaincompress`, `amix`).
     - EBU R128 loudness normalization (`loudnorm`).
3. **No Multi-Person Layout Capabilities**:
   - Current reframing assumes a single rectangular crop window (`crop=w:h:x:y`). Split-screen podcast framing (Speaker 1 on top, Speaker 2 on bottom) cannot be generated.
4. **No Layering or B-roll Placement**:
   - No data models or rendering filters exist for inserting supplemental video/image overlays on top of the main camera feed.
5. **No Audio Mixing & Ducking**:
   - The current export pipeline copies original audio or re-encodes a single stereo track without background music, sound effects, or automated voice ducking.
6. **No Non-Destructive Versioning**:
   - Once a clip is exported or edited, previous parameters are overwritten. There is no concept of composition versions (v1, v2, draft vs approved).

---

## 4. Reusability Matrix

| Existing Subsystem | Reuse Strategy for Phase 9 | Modification Required? |
| :--- | :--- | :--- |
| **FFmpegManager** | Reused directly as execution engine | No (100% reusable) |
| **FFprobeManager** | Reused directly for stream inspection and export verification | No (100% reusable) |
| **CapabilityDetector** | Reused directly for GPU NVENC capability testing | No (100% reusable) |
| **JobManager & JobEvents** | Reused directly for background job queue and WebSocket progress | No (100% reusable) |
| **SubtitleRenderer** | Reused directly for broadcast ASS script rendering | No (100% reusable) |
| **ActiveSpeakerService** | Ingested by Composition Planner for speaker-aware camera switches | No (Stable consumer API) |
| **SpeakerFaceAssociator** | Ingested to link speaker audio turns to visual camera slots | No (Stable consumer API) |
| **ReframeEngine** | Ingested by Layout Engine to compute individual face crop bounds | Extended via layout adapters |
| **ExportService** | Superseded by RenderGraphCompiler and CompositionRenderService | Maintained for legacy clips; Phase 9 adds new engine |
