# ClipForge AI — Phase 8 Implementation Plan
## Audio Intelligence, Speaker Diarization, Active-Speaker Detection & Audio Enhancement

---

## 1. Executive Summary & Hardware Context

Phase 8 introduces a local-first audio intelligence system that analyzes speech activity, separates anonymous speakers, links transcript words with speaker turns, and combines visual mouth-motion evidence with audio timing to detect which visible person is currently speaking.

### Hardware Targets & Operational Bounds
- **Platform**: Windows 11 (64-bit), Intel Core i7-13620H, NVIDIA RTX 4060 Laptop GPU (8 GB VRAM), 16 GB RAM.
- **Runtime Environment**: Python 3.11.9, FFmpeg 9.0.2 with libass, React 18, Vite, Tailwind CSS, Electron.
- **Hardware Limitations & Fallbacks**:
  - The installed FFmpeg build uses CPU `libx264` due to NVENC API 13.1 vs driver 13.0 mismatch.
  - CUDA runtime initialization on PyTorch was previously blocked by missing `cublas64_12.dll`.
  - **MANDATORY**: CPU inference is the primary execution path and must run smoothly within 16 GB RAM.
  - GPU execution is optional, checked at runtime, and only used when verified by actual inference.
  - **NO PAID CLOUD APIS**: 100% local processing, zero third-party cloud data transmission.

---

## 2. Core Architectural Distinction

To maintain scientific rigor and avoid false marketing claims, Phase 8 strictly separates four distinct concepts:

```
[Audio Signal] ──► Voice Activity Detection (VAD)
                         │ (Determines WHEN speech occurs)
                         ▼
                   Speaker Diarization
                         │ (Clusters anonymous voices into "Speaker 1", "Speaker 2")
                         ▼
[Transcript]   ──► Transcript-Speaker Alignment
                         │ (Associates words with speaker turns via timestamp overlap)
                         │
[Video Frames] ──► Face Tracking + Mouth Motion
                         │ (Extracts face bounds and mouth dynamics over time)
                         ▼
                   Active-Speaker Detection (AV Fusion)
                         │ (Estimates WHICH visible face corresponds to current voice)
                         ▼
                   Confidence-Aware Smart Reframing
                         └── Follows active speaker if confidence >= threshold,
                             else falls back to safe group / center crop.
```

1. **Voice Activity Detection (VAD)**: Determines *when* speech or speech-like activity occurs versus silence, music, or background noise.
2. **Speaker Diarization**: Answers *who spoke when* as anonymous, video-local labels (`Speaker 1`, `Speaker 2`). It does *not* recognize real-world identities and does *not* know which visible face belongs to a voice.
3. **Mouth-Motion Analysis**: Measures visual mouth dynamics from tracked faces. Mouth movement is *not* proof of speech (smiling, chewing, laughing can cause motion).
4. **Active-Speaker Detection**: Probabilistic audio-visual fusion estimating whether an audible speaker corresponds to a visible tracked face. If evidence is ambiguous, the system outputs `uncertain` or `no_visible_speaker` and engages a safe fallback.

---

## 3. Module Inventory

### 3.1 Existing Modules Reused Without Modification
- `backend/app/video/ffmpeg_manager.py`: Subprocess execution, real-time progress parsing, Windows PID process-tree termination (`taskkill /F /T /PID`).
- `backend/app/video/ffprobe_manager.py`: Deep technical stream metadata extraction (channels, sample rates, duration, codecs).
- `backend/app/video/audio_extractor.py`: Source audio extraction to 16 kHz mono 16-bit PCM WAV.
- `backend/app/ai/vision/face_detector.py`: OpenCV YuNet ONNX face detector providing 5 key facial landmarks (`right_eye`, `left_eye`, `nose_tip`, `right_mouth`, `left_mouth`).
- `backend/app/ai/vision/face_tracker.py`: Spatial-temporal tracker with IoU and centroid distance matching, track persistence, and 1.5s occlusion tolerance.
- `backend/app/ai/vision/reframe_engine.py`: Exponential Moving Average (EMA) smoothing, maximum velocity clamping, headroom adjustment, and hard boundary clamping.
- `backend/app/ai/vision/vision_manager.py`: Video frame sampling at 4.0–10.0 fps, downscaling to 640px, and sequential lock coordination.
- `backend/app/workers/job_manager.py` & `backend/app/workers/job_executor.py`: Persistent background queue, single heavy worker execution, WebSocket progress broadcasting (`/ws/jobs`), and cancellation tokens.
- `backend/app/video/clip_generator.py` & `backend/app/services/export_service.py`: Final rendering with dynamic crop trajectories and ASS subtitle burn-in.

### 3.2 New Modules to Implement

| Module | Location | Primary Responsibility |
| :--- | :--- | :--- |
| `AudioPreprocessor` | `backend/app/ai/audio/audio_preprocessor.py` | Audio extraction, sample rate conversion (16kHz / 48kHz), clipping detection, silence detection, chunked processing. |
| `VoiceActivityDetector` | `backend/app/ai/audio/voice_activity_detector.py` | Silero VAD wrapper for fast, local speech timestamp detection. |
| `SpeakerEmbeddings` | `backend/app/ai/audio/speaker_embeddings.py` | Acoustic feature and ONNX embedding extraction (CAM++ / ResNet34) with offline spectral fallback. |
| `SpeakerDiarizer` | `backend/app/ai/audio/speaker_diarizer.py` | Turn segmentation, cosine distance clustering, anonymous label assignment (`Speaker 1`, `Speaker 2`). |
| `TranscriptSpeakerAligner` | `backend/app/ai/audio/transcript_speaker_aligner.py` | Timestamp-overlap alignment of Whisper word timestamps to speaker turns. |
| `ConversationAnalyzer` | `backend/app/ai/audio/conversation_analyzer.py` | Turn count, speaking time distribution, interruption/overlap metrics, silence statistics. |
| `MouthMotionAnalyzer` | `backend/app/ai/vision/mouth_motion_analyzer.py` | Landmark-based scale-invariant mouth aspect ratio variance and ROI dynamics. |
| `ActiveSpeakerDetector` | `backend/app/ai/audio_visual/active_speaker_detector.py` | Audio-visual fusion engine with confidence policy and explicit fallback states. |
| `AudioEnhancer` | `backend/app/ai/audio/audio_enhancer.py` | FFmpeg filtergraph for EBU R128 loudness normalization, FFT noise reduction, peak limiting, high-pass filtering. |
| `AudioManager` | `backend/app/ai/audio/audio_manager.py` | Inference-lock coordination, sequential model lifecycle, memory monitoring. |
| `AudioService` | `backend/app/services/audio_service.py` | Database persistence, speaker renaming, turn reassignment, API service layer. |
| `AudioRoutes` | `backend/app/api/routes/audio.py` | FastAPI endpoints for analysis, speakers, active-speaker queries, and audio enhancement. |

---

## 4. Model Selection, Licensing & Memory Footprint

### 4.1 Voice Activity Detection (VAD)
- **Model**: Silero VAD v4/v5 (ONNX).
- **Source**: Embedded directly in `faster-whisper.vad` (already installed and verified in `backend/venv`).
- **License**: MIT License.
- **Model Size**: ~1.8 MB.
- **Offline Behavior**: 100% offline. Zero network calls.
- **Execution**: ONNX Runtime CPU. Latency: <15ms per second of audio.
- **Memory**: <25 MB RAM.

### 4.2 Speaker Diarization & Embeddings
- **Evaluation of Pyannote**:
  - `pyannote/speaker-diarization-3.1` is a **gated model** on Hugging Face that requires user token authentication (`HF_TOKEN`) and manual web agreement sign-off.
  - Mandating Pyannote breaks the local-first, zero-setup requirement.
- **Selected Primary Pipeline**:
  - **Embedding Model**: Open-weights ONNX Speaker Embedding Model (e.g. 3D-Speaker / CAM++ or WeSpeaker ResNet34 ONNX).
  - **Source**: Public ONNX model hub / ModelScope / GitHub Releases (non-gated, direct download).
  - **License**: Apache 2.0 / MIT.
  - **Size**: ~16 MB to 35 MB.
  - **Fallback Mode**: Pure-Python / NumPy acoustic spectral embedding (Mel-frequency filterbank centroids, spectral flux, energy contours) requiring **zero external model downloads**, guaranteeing 100% offline functionality out-of-the-box.
  - **Clustering Engine**: Pure NumPy Agglomerative Hierarchical Clustering (AHC) using average-linkage cosine distance ($D = 1 - \frac{u \cdot v}{\|u\| \|v\|}$).
  - **Memory Footprint**: ~50 MB RAM for ONNX Runtime.

### 4.3 Visual Mouth-Motion Model
- **Model**: OpenCV YuNet 5-point facial landmark detector (already verified in Phase 6).
- **Size**: 232 KB.
- **License**: Apache 2.0.
- **Approach**:
  - Normalized Mouth Aspect Ratio:
    $$\text{MAR} = \frac{\|\text{mouth\_right} - \text{mouth\_left}\|}{\|\text{eye\_left} - \text{eye\_right}\|}$$
  - Mouth vertical displacement relative to nose tip:
    $$\Delta y_{\text{mouth}} = \frac{y_{\text{mouth\_center}} - y_{\text{nose\_tip}}}{\|\text{eye\_left} - \text{eye\_right}\|}$$
  - Temporal standard deviation over a sliding window ($W = 0.5\text{s}$):
    $$\sigma_{\text{motion}} = \text{std}(\Delta y_{\text{mouth}}(t))$$
  - High motion variance during an audio speech interval indicates active speech.
  - Low motion variance (quiescent lips) indicates listening/silence.
- **Memory Footprint**: Reuses existing Phase 6 video frame buffers with zero additional model overhead.

---

## 5. Active-Speaker Decision & Confidence Policy

The active-speaker detector combines audio and visual evidence across discrete temporal windows ($0.25\text{s} - 0.5\text{s}$):

### 5.1 Evidence Fusion Equation
For face track $i$ during speech interval with audio confidence $C_{\text{audio}}$:
$$C_{\text{visual}}(i) = \min\left(1.0, \frac{\sigma_{\text{motion}}(i)}{\tau_{\text{motion}}}\right) \cdot \text{VisibilityRatio}(i)$$
$$C_{\text{sync}}(i) = 1.0 - |\Delta t_{\text{onset\_audio}} - \Delta t_{\text{onset\_visual}}|$$
$$C_{\text{combined}}(i) = w_a C_{\text{audio}} + w_v C_{\text{visual}}(i) + w_s C_{\text{sync}}(i)$$
with weights $w_a = 0.4$, $w_v = 0.4$, $w_s = 0.2$.

### 5.2 Status States
- **`active`**: Face track $i$ has $C_{\text{combined}} \ge 0.65$ and exceeds secondary visible faces by a margin $\ge 0.20$.
- **`uncertain`**: Two or more faces exhibit comparable mouth motion, or $0.40 \le C_{\text{combined}} < 0.65$.
- **`no_visible_speaker`**: Speech is clearly audible ($C_{\text{audio}} \ge 0.70$) but no tracked face exceeds the visual threshold (voice-over, narrator, or off-screen speaker).
- **`overlapping_speakers`**: Multiple speakers diarized simultaneously.
- **`no_speech`**: VAD indicates silence or background audio.
- **`insufficient_visual_evidence`**: Face tracks occluded, extreme profile angles, or face bounding box $< 50\text{px}$.

### 5.3 Smart Reframing Fallback Strategy
When the user selects the `active_speaker` reframing strategy:
1. If status is `active`: Center the camera on the active face track with 0.8s transition hysteresis to prevent rapid back-and-forth camera oscillation.
2. If status is `no_visible_speaker` or `uncertain`: Preserve the previous stable crop coordinates for up to 2.0s, or smoothly interpolate to a neutral two-shot / group crop.
3. User manual keyframe crop corrections always take precedence over automated tracking.

---

## 6. Database Schema Additions (`backend/app/db/models.py`)

```sql
-- Audio analysis run entity
CREATE TABLE audio_analyses (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    video_id VARCHAR(36) NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    status VARCHAR(50) DEFAULT 'completed',
    processing_device VARCHAR(50),
    vad_model VARCHAR(100),
    diarization_model VARCHAR(100),
    duration_seconds FLOAT NOT NULL,
    speech_duration_seconds FLOAT DEFAULT 0.0,
    speaker_count INTEGER DEFAULT 0,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);

-- Extended Speaker entity (already exists in models.py, adding metadata fields)
-- Alter existing 'speakers' table:
-- display_name VARCHAR(100) (editable user label: Host, Guest, etc.)
-- average_confidence FLOAT
-- speaking_duration FLOAT
-- metadata_json JSON

-- Speaker turn intervals
CREATE TABLE speaker_turns (
    id VARCHAR(36) PRIMARY KEY,
    analysis_id VARCHAR(36) NOT NULL REFERENCES audio_analyses(id) ON DELETE CASCADE,
    speaker_id VARCHAR(36) NOT NULL REFERENCES speakers(id) ON DELETE CASCADE,
    start_time FLOAT NOT NULL,
    end_time FLOAT NOT NULL,
    confidence FLOAT DEFAULT 1.0,
    overlap_status BOOLEAN DEFAULT FALSE,
    created_at DATETIME NOT NULL
);

-- Active speaker intervals
CREATE TABLE active_speaker_intervals (
    id VARCHAR(36) PRIMARY KEY,
    analysis_id VARCHAR(36) NOT NULL REFERENCES audio_analyses(id) ON DELETE CASCADE,
    start_time FLOAT NOT NULL,
    end_time FLOAT NOT NULL,
    face_track_id VARCHAR(36) REFERENCES face_tracks(id) ON DELETE SET NULL,
    speaker_id VARCHAR(36) REFERENCES speakers(id) ON DELETE SET NULL,
    audio_confidence FLOAT NOT NULL,
    visual_confidence FLOAT NOT NULL,
    combined_confidence FLOAT NOT NULL,
    status VARCHAR(50) NOT NULL,
    reason TEXT,
    created_at DATETIME NOT NULL
);

-- Audio enhancement presets
CREATE TABLE audio_enhancement_presets (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    target_loudness FLOAT DEFAULT -14.0,  -- -14 LUFS (YouTube / TikTok)
    true_peak_limit FLOAT DEFAULT -1.5,   -- -1.5 dBTP
    loudness_range FLOAT DEFAULT 11.0,    -- 11 LU
    noise_reduction_db FLOAT DEFAULT 12.0,
    high_pass_hz INTEGER DEFAULT 80,
    is_default BOOLEAN DEFAULT FALSE,
    created_at DATETIME NOT NULL
);
```

---

## 7. REST API Endpoints (`backend/app/api/routes/audio.py`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/audio/capabilities` | Return audio devices, VAD model, and diarization status. |
| `POST` | `/api/videos/{video_id}/analyze-audio` | Queue audio analysis job (VAD + Diarization + Alignment). |
| `GET` | `/api/videos/{video_id}/audio-analysis` | Get audio analysis results, speaker list, and conversation metrics. |
| `GET` | `/api/videos/{video_id}/speakers` | List all anonymous speakers in video. |
| `PATCH` | `/api/speakers/{speaker_id}` | Update display name (e.g. rename "Speaker 1" to "Host"). |
| `GET` | `/api/videos/{video_id}/speaker-turns` | Fetch speaker turn timeline. |
| `PATCH` | `/api/speaker-turns/{turn_id}` | Manually reassign a turn to another speaker. |
| `POST` | `/api/videos/{video_id}/active-speakers` | Run AV active-speaker fusion analysis. |
| `GET` | `/api/videos/{video_id}/active-speakers` | Fetch active-speaker intervals and confidence data. |
| `POST` | `/api/videos/{video_id}/enhance-preview` | Generate 10-second audio enhancement preview WAV. |
| `POST` | `/api/clips/{clip_id}/apply-audio-enhancement`| Apply audio enhancement to clip export pipeline. |
| `GET` | `/api/audio-enhancement/presets` | List broadcast audio enhancement presets. |
| `POST` | `/api/audio-enhancement/presets` | Create custom audio enhancement preset. |

---

## 8. React Desktop UI Components (`src/components/audio/`)

1. **`AudioAnalysisPanel.tsx`**: Main tab in `ProjectStudio.tsx` with scan triggers, summary stats, and speaker counts.
2. **`SpeakerTimeline.tsx`**: Color-coded interactive timeline showing speaker turns across the video duration.
3. **`SpeakerCard.tsx`**: Speaker profile card with speaking percentage, confidence bar, rename input, and color pill.
4. **`SpeakerTurnEditor.tsx`**: Transcript segment re-tagger allowing one-click speaker reassignment.
5. **`ActiveSpeakerTimeline.tsx`**: Visual correlation bar indicating when an on-screen face is speaking vs off-screen audio.
6. **`MouthMotionOverlay.tsx`**: Visual player overlay showing mouth dynamics indicator per face.
7. **`ConversationStatistics.tsx`**: Turn count, average turn duration, speaking distribution, and silence breakdown.
8. **`AudioEnhancementPanel.tsx`**: Sliders for target LUFS, noise reduction strength, rumble high-pass filter, and A/B audio comparison player.

---

## 9. Comprehensive Testing Strategy

### 9.1 Backend Unit & Integration Tests (`backend/tests/test_phase8.py`)
- **Audio Preprocessing**: Test valid WAV/MP4 extraction, mono resampling to 16 kHz, clipping detection, silence detection, chunking.
- **Voice Activity Detection**: Test speech detection, pure silence, synthetic noise, short bursts, speech separated by pauses.
- **Speaker Diarization & Clustering**: Test single-speaker audio, two-speaker alternating conversation, cosine distance clustering, minimum duration thresholding.
- **Transcript Alignment**: Word timestamp intersection with speaker turns, boundary overlap, confidence assignment.
- **Mouth-Motion Analysis**: Scale-invariant normalization, facial landmark displacement, motion variance calculation.
- **Active-Speaker Association**: One visible speaker, two people taking turns, off-screen voice-over, overlapping speech, confidence thresholding.
- **Reframing Strategy**: `active_speaker` strategy trajectory generation with hysteresis, manual keyframe override preservation.
- **Audio Enhancement**: Verify FFmpeg `loudnorm`, `afftdn`, `highpass` filtergraph generation, output peak limiting, audio/video synchronization.
- **Reliability & State**: Database persistence, job cancellation, restart recovery, model unloader.

### 9.2 Real Video Acceptance Test (`backend/acceptance_phase8_real.py`)
- Real video test scenarios:
  1. Single speaker speaking clearly to camera.
  2. Two people taking turns speaking.
  3. Two people visible with only one speaking.
  4. Voice-over with no visible faces.
  5. Speech with background music and ambient noise.
  6. Soft/quiet speech.
- Record actual execution devices, processing time, memory usage, diarization turns, active-speaker intervals, and output file integrity.
- Generate `PHASE8_FINAL_ACCEPTANCE_REPORT.md` and save metrics to `phase8_acceptance_results.json`.

---

## 10. Implementation Sequence

- [ ] **Stage 1**: Repository audit & implementation plan (**CURRENT STAGE**).
- [ ] **Stage 2**: Audio preprocessing & VAD engine (`audio_preprocessor.py`, `voice_activity_detector.py`).
- [ ] **Stage 3**: Local speaker diarization & clustering (`speaker_embeddings.py`, `speaker_diarizer.py`).
- [ ] **Stage 4**: Transcript-to-speaker alignment & conversation metrics (`transcript_speaker_aligner.py`, `conversation_analyzer.py`).
- [ ] **Stage 5**: Visual mouth-motion analysis (`mouth_motion_analyzer.py`).
- [ ] **Stage 6**: Audio-visual active-speaker fusion engine (`active_speaker_detector.py`).
- [ ] **Stage 7**: Smart reframing integration (`active_speaker` strategy in `reframe_engine.py`).
- [ ] **Stage 8**: Audio enhancement engine (`audio_enhancer.py`).
- [ ] **Stage 9**: Service layer, background jobs & FastAPI REST endpoints (`audio_service.py`, `job_executor.py`, `routes/audio.py`).
- [ ] **Stage 10**: Frontend UI components in React/TypeScript (`src/components/audio/`, `ProjectStudio.tsx`).
- [ ] **Stage 11**: Real video acceptance testing & metrics reporting (`acceptance_phase8_real.py`).
- [ ] **Stage 12**: Full regression suite & documentation updates (`ARCHITECTURE.md`, `DEVELOPMENT_STATUS.md`, `docs/`).
