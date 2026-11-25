# ClipForge AI — Architecture Blueprint

## System Overview
**ClipForge AI** is a production-oriented, local-first Windows desktop application for automated long-form video repurposing into vertical short-form content (TikTok, Shorts, Reels). It is engineered for local execution on constrained hardware (specifically target: NVIDIA RTX 4060 Laptop GPU, 8 GB VRAM, 16 GB RAM).

---

## The Four Architecture Layers

```
+-------------------------------------------------------------------------+
|                        ELECTRON DESKTOP LAYER                           |
|  - BrowserWindow (frameless, titleBarOverlay)                           |
|  - Subprocess Lifecycle Manager (spawns & terminates local Python backend) |
|  - Cryptographic Session Token Generator (inter-process security)       |
|  - Context-Isolated Secure Preload Bridge (window.electronAPI)          |
+-------------------------------------------------------------------------+
                                    |
            IPC (Native Dialogs)    |   HTTP / WebSockets (localhost:8000)
                                    v
+-------------------------------------------------------------------------+
|                        REACT FRONTEND LAYER                             |
|  - React 18 + TypeScript + Vite + Tailwind CSS                          |
|  - Zustand System & Project Stores                                      |
|  - Real-Time Hardware Telemetry (GPU VRAM, CPU load, RAM, Disk)         |
|  - Interactive VideoPlayer & Frame ThumbnailStrip                       |
|  - Live Background Job Queue Widget & Management Screen                 |
+-------------------------------------------------------------------------+
                                    |
                                    v  REST API / WebSockets
+-------------------------------------------------------------------------+
|                        PYTHON BACKEND LAYER                             |
|  - FastAPI (Python 3.11) with strict Local-CORS & Session Token Auth    |
|  - SQLite (async via aiosqlite + SQLAlchemy 2.0 ORM)                    |
|  - Bounded Concurrency Job Queue (asyncio.Queue single heavy worker)    |
|  - Real-time Hardware Monitor (psutil + nvidia-smi CSV query)          |
|  - HTTP 206 Partial Content Range Streaming Helper                      |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                      INDEPENDENT PROCESSING ENGINES                     |
|  1. Video/Audio Ingestion & Probe (FFprobe JSON metadata extraction)   |
|  2. Video Capabilities & Dynamic Encoders (NVENC vs libx264 detection)  |
|  3. Safe Process Subprocess Manager (asyncio exec, progress, kill PID)  |
|  4. Poster & Timeline Strip Thumbnail Generator (ThumbnailGenerator)   |
|  5. Audio Extraction for AI (16kHz mono 16-bit PCM WAV for Whisper)   |
|  6. 720p H.264 Faststart Proxy Preview Generator (PreviewGenerator)    |
|  7. Frame-Accurate Video Clip Cutting & Verification (ClipGenerator)   |
|  8. Multi-Ratio Aspect Ratio Reframing (9:16, 1:1, 4:5, 16:9)          |
|  9. Speech Transcription Engine (faster-whisper, CTranslate2, Silero VAD)  |
|  10. AI Highlight Selection Engine (llama.cpp, 2-Stage Discovery, Scorer)|
|  11. Face Tracking & Smart Center Re-framing (Phase 6)                  |
|  12. Professional Subtitle Styler, Viral Karaoke Engine & Final Render Pipeline (Phase 7) |
|  13. Production Export & Loudness Normalization (Phase 8)               |
+-------------------------------------------------------------------------+
```

---

## Security Model

1. **Context Isolation**: `contextIsolation: true` and `nodeIntegration: false` in Electron `webPreferences`.
2. **Session Authentication Token**: On boot, the Electron main process generates an unguessable UUID (`crypto.randomUUID()`), injects it into the backend environment (`CLIPFORGE_SESSION_TOKEN`), and passes it through the secure preload script to the frontend API client. Requests to the backend require the `x-session-token` header or query token.
3. **Restricted CORS**: The FastAPI server strictly permits `localhost:5173`, `127.0.0.1:5173`, and Electron origins.
4. **No Raw Shell Concatenation**: All FFmpeg, FFprobe, and system subprocess invocations pass structured argument arrays (`list[str]`), mitigating shell injection vulnerabilities.
5. **Safe Windows Child Termination**: Process trees are explicitly tracked and terminated cleanly with `taskkill /F /T /PID` to prevent zombie rendering processes on Windows.

---

## Local Storage Layout

All files are stored in a dedicated, isolated application directory:
```text
storage/clipforge_data/
├── database/         # SQLite database file (clipforge.db)
├── projects/         # Project metadata, audio, previews, and thumbnails
│   └── {project_id}/
│       ├── audio/       # 16kHz mono WAV extraction for Whisper AI
│       ├── previews/    # 720p H.264 faststart MP4 proxy videos
│       ├── thumbnails/  # Poster JPEG and timeline thumbnail strip
│       └── clips/       # Rendered 9:16 / 1:1 / 4:5 short clips
├── uploads/          # Original video files (never mutated or overwritten)
├── clips/            # Rendered video segments
├── exports/          # Final rendered 1080x1920 MP4 files
├── thumbnails/       # Lightweight JPG thumbnails & proxies
├── cache/            # Temporary render files and ASS subtitle files
└── models/           # Downloaded local AI model weights (Whisper, LLMs)
```

---

## Speech Transcription Engine (Phase 4)

Located in `backend/app/ai/`.
* **Inference Engine**: `faster-whisper` backed by `CTranslate2` for quantized 8-bit/16-bit local execution.
* **Model Catalog**: Pinned CTranslate2 models (`tiny`, `base`, `small`, `medium`) with on-demand download and verification.
* **Dynamic Hardware Detection**: Detects CUDA availability; actively verifies `cublas64_12.dll` loadability and falls back to CPU `int8` with AVX2/AVX-512 optimization when cuBLAS is unavailable.
* **Resource Conservation**: Sequential inference lock enforcing single-model execution; models are loaded lazily and unloaded immediately after job completion.
* **Voice Activity Detection**: Silero VAD filters non-speech audio and pauses, returning precise word-level timestamps.
* **Synchronization**: Bidirectional seek between `<TranscriptPanel />` and `<VideoPlayer />` in React.

---

## AI Highlight Selection Engine (Phase 5)

Located in `backend/app/ai/llm/` and `backend/app/ai/highlights/`.
* **Inference Engine**: Native Windows standalone `llama.cpp` runtime (`b12532` Clang AVX2/AVX-512 CPU build) executed as an isolated child process (`llama-cli.exe`), eliminating Python GIL bottlenecks and ensuring instant memory reclamation and clean process tree termination (`taskkill /F /T /PID`).
* **Model Catalog**: Pinned GGUF quantized models (`qwen-2.5-3b` default, `llama-3.2-3b`, `qwen-2.5-1.5b`, `qwen-2.5-0.5b`) with on-demand download, SHA256 integrity validation, and deletion.
* **Two-Stage Discovery Pipeline**:
  - **Stage A (Deterministic Windowing)**: Fast, non-destructive sliding windowing over sentence-bounded word groups to discover candidate boundaries based on conversational pauses and density without requiring GPU inference.
  - **Stage B (Local LLM Semantic Extraction)**: High-precision semantic reasoning via local instruct GGUF LLMs prompted with content-type awareness (`podcast`, `interview`, `educational`, `gaming`, etc.) to find viral hooks, self-contained narratives, and memorable conclusions.
* **Ground-Truth Boundary Refiner & Quote Verifier**:
  - Snaps raw timestamps to sentence and word start/end timings to prevent mid-sentence cuts.
  - Pre-roll boundary extension ensures hook completeness.
  - Strict n-gram quote verification checks that purported highlight quotes actually exist within the source transcript text.
* **Explainable Multi-Dimensional Scorer (0–100)**:
  - Transparent mathematical breakdown across 7 dimensions: Hook Strength (20), Content Value (20), Narrative Flow (20), Context Independence (15), Emotional Engagement (10), Structural Conciseness (10), Call to Action / Ending (5).
  - Explicit penalties applied for excessive silence, mid-thought truncation, or weak opening lines.
* **Duplicate Detector**:
  - Temporal Intersection-over-Union (IoU > 0.60) and textual Jaccard similarity filtering to remove redundant overlapping candidate clips.
* **User-Driven Workflow**:
  - Candidates are saved with state machine (`discovered` -> `approved` / `rejected` -> `edited` -> `ready_for_render`).
  - No clips are rendered automatically without user inspection, editing, and approval.

---

## Visual AI & Smart Reframing Subsystem (Phase 6)

* **Local Neural Face Detector (OpenCV DNN YuNet)**:
  - 232 KB ONNX model (`face_detection_yunet_2023mar.onnx`) running on CPU with ~20ms inference latency.
  - Extracts normalized bounding boxes `[0.0, 1.0]` and 5 facial landmarks (eyes, nose, mouth corners).
  - Offline fallback to built-in Haar Cascade detector.
* **Spatial-Temporal Face Tracking**:
  - Associates bounding boxes using IoU and centroid distance matching.
  - Maintains track longevity with 1.5s (5 frames @ 4fps) occlusion tolerance.
* **Scene Composition & Structure**:
  - Classifies scenes into `single_subject`, `multi_person`, `crowd`, and `b_roll`.
  - Computes face presence percentage and max concurrent subjects.
* **Subject Focus Selection**:
  - `largest_face`: Dominant / closest speaker.
  - `center_face`: Center-stage speaker.
  - `manual_track`: Lock camera to specific subject ID.
  - `group`: Dynamic union framing encompassing all subjects.
* **Smart Camera Motion & Boundary Clamping**:
  - Computes aspect-ratio-accurate crops (9:16, 1:1, 4:5, 16:9) with headroom margins (10-25%).
  - Exponential Moving Average (EMA) smoothing prevents camera jitter.
  - Maximum velocity clamping (e.g. 0.50/s) eliminates unnatural camera snap.
  - 100% hard boundary clamping guarantees crops never sample outside the frame or exceed source boundaries.
  - Generates piecewise linear FFmpeg filter expressions for dynamic crop rendering.
* **Interactive React Studio UI**:
  - `FaceDetectionOverlay`: Bounding box and crop window overlay on video player.
  - `CropPreview`: Live phone simulator previewing vertical view.
  - `VisionAnalysisPanel`: Scan triggers, scene badges, reframe sliders, and keyframe crop editor.

---

## Subtitle Engine & Final Render Pipeline (Phase 7)

Located in `backend/app/services/subtitle_renderer.py`, `backend/app/services/subtitle_service.py`, and `backend/app/services/export_service.py`.
* **SubStation Alpha (ASS) Generator**:
  - High-precision word-level ASS v4.00+ script generator.
  - Hex color translation with alpha channel (`&HAABBGGRR`).
  - Strict injection prevention escaping curly braces, backslashes, and newlines.
  - Windows path sanitization for FFmpeg's `ass` filter (`C\:/...`).
* **8 Distinctive Presets**:
  - **Bold Creator** (default): Arial Black, 72pt, `#FFFFFF` text, `#FACC15` vibrant yellow highlight, 7px stroke, 3px shadow, viral karaoke active word pop (`\fscx110\fscy110`), safe 280px vertical margin.
  - **Clean Minimal**: Arial, 58pt, `#FFFFFF` text, `#38BDF8` sky cyan highlight, word-by-word cumulative reveal.
  - **Podcast Highlight**: Trebuchet MS, 64pt, `#F8FAFC` text, `#FB923C` warm orange highlight, karaoke pop.
  - **Cinematic**: Georgia, 56pt, `#FEF08A` soft gold text, `#F59E0B` deep amber, phrase fade (`\fad(150,150)`).
  - **Gaming**: Impact, 74pt, `#F0FDF4` text, `#22C55E` cyber green highlight, 8px dark outline, karaoke pop.
  - **Educational**: Segoe UI, 60pt, `#F1F5F9` text, `#3B82F6` royal blue highlight, word-by-word reveal.
  - **Classic Subtitles**: Arial, 52pt, standard `#FFFFFF` static broadcast styling.
  - **High Contrast**: Arial Black, 66pt, `#FEF08A` yellow text, `#EF4444` crimson highlight, 9px stroke.
* **Clip-Relative Normalization & Editing**:
  - Automatic dialogue extraction from parent video transcript with relative timestamp translation: $t_{\text{rel}} = t - t_{\text{clip\_start}}$.
  - In-place word correction, segment boundary shifting, word-index splitting, and adjacent segment merging.
* **Single-Pass Final Render Pipeline**:
  - Fuses dynamic crop trajectories, bicubic resolution scaling (to 1080x1920 9:16), and burned ASS subtitles in a single FFmpeg filtergraph pass.
  - GPU NVENC / CPU libx264 execution with full multi-channel AAC audio preservation.
  - Asynchronous background rendering with live WebSocket progress reporting and cancellation cleanup.
* **Interactive React Studio UI**:
  - `CaptionPresetGallery`: Visual cards for all presets with one-click styling switch.
  - `CaptionStyleEditor`: Fine-tuning typography, colors, strokes, drop shadows, and safe mobile margins.
  - `SubtitleEditor`: Word-by-word click-to-edit transcript editor with split/merge actions.
  - `SubtitlePreviewOverlay`: Real-time synchronized subtitle preview directly on the HTML5 video player matching chosen preset styles before rendering.
  - `ExportModal`: Render configuration dialog with encoder settings and live progress tracking.
  - `SubtitlePanel`: Subtitle workspace tab mounted in `ProjectStudio.tsx`.

---

## Database Schema (SQLAlchemy / SQLite)

* **`projects`**: Top-level project entities with title, description, and status.
* **`videos`**: Imported source video files, technical stream metadata (codec, fps, duration, dimensions, preview path).
* **`transcripts`**: Parent transcript records linked 1:1 to source videos.
* **`transcript_segments`**: Individual timestamped dialogue lines with nested word-level JSON timings.
* **`speakers`**: Speaker identities for diarization.
* **`clips`**: Generated short-form video clip entities with non-destructive EDL settings and aspect ratio.
* **`subtitle_tracks`**: Clip-relative subtitle tracks with word-level JSON segments, linked preset, and style overrides.
* **`clip_scores`**: Multi-dimensional virality and engagement metrics (overall, hook, flow, value).
* **`highlight_candidates`**: Discovered AI highlight proposals with detailed score breakdown, reasons, hook text, state machine status, and approved clip link.
* **`vision_analyses`**: Visual analysis results with sampling rate, face count, scene type, and composition metrics.
* **`face_tracks`**: Tracked subjects across video frames with average bounding box and temporal samples.
* **`manual_crop_corrections`**: User keyframe crop adjustments overriding automated tracking at specific timestamps.
* **`reframe_presets`**: Reusable aspect ratio and motion smoothing configuration presets.
* **`jobs`**: Background job queue records with status, progress %, stage description, parameters, and results.
* **`exports`**: Rendered export history with encoder bitrate, resolution, duration, file size, and output file path.
* **`caption_presets`**: Subtitle typography, animation style, and styling presets.
* **`audio_analyses`**: Audio preprocessing and Voice Activity Detection (VAD) analysis records with technical metadata, speech duration, and silence flags.
* **`speech_intervals`**: Detected voice activity intervals with start/end timestamps, confidence, and detection source.
* **`app_settings`**: Key-value application configurations and acceleration profiles.

---

## Audio Intelligence Engine (Phase 8 — Stage 2 Implemented)

Located in `backend/app/ai/audio/audio_preprocessor.py`, `backend/app/ai/audio/voice_activity_detector.py`, `backend/app/services/audio_analysis_service.py`, and `backend/app/api/routes/audio.py`.

* **Audio Preprocessing Engine**:
  - Canonical 16,000 Hz, mono, 16-bit PCM (`pcm_s16le`) extraction and resampling via FFmpeg.
  - Signal metrics calculation: Peak amplitude, RMS level, silence detection ($\text{RMS} < 10^{-4}$), clipping detection ($\text{Peak} \ge 0.999$).
  - Bounded memory windowed streaming: 30-second chunks with 1-second overlap, enabling multi-hour audio processing without OOM.
  - Safe immutable source media handling: extracted audio is cached in project-scoped directories (`storage/clipforge_data/projects/{project_id}/audio/{video_id}_16k.wav`).
* **Local Voice Activity Detection (Silero VAD)**:
  - Powered by Silero VAD v4 via ONNX Runtime on CPU (0 CUDA dependencies, 0 paid APIs).
  - High performance: Real-Time Factor (RTF) $\approx 0.013\times$ (approx. 78x faster than real-time playback).
  - Robust post-processing: Boundary deduplication, temporal speech padding (`speech_pad_ms`), utterance gap merging (`max_merge_gap_ms`), and short noise filtering (`min_speech_duration_ms`).
  - Strict rejection: 0 false positives on non-speech ambient noise; 100% rejection on silent audio.
* **REST & Worker Integration**:
  - `GET /api/audio/capabilities`: VAD engine capabilities and default configuration.
  - `POST /api/videos/{video_id}/audio-analysis`: Asynchronous 8-stage background job dispatch via `JobManager`.
  - `GET /api/videos/{video_id}/audio-analysis`: Retrieve latest analysis with computed speech percentage.
  - `GET /api/audio-analysis/{analysis_id}/intervals`: Retrieve timestamped speech intervals.
  - `POST /api/audio-analysis/{analysis_id}/cancel`: Cancel active/queued analysis jobs.
