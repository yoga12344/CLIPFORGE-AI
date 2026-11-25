# ClipForge AI — Phase 8 Stage 3 Technical Acceptance Report
## Offline Speaker Diarization Engine (3D-Speaker CAM++ ONNX)

### 1. Executive Summary
Phase 8 Stage 3 delivers a production-grade, local-first offline speaker diarization engine for ClipForge AI on Windows 11. Built around the 3D-Speaker CAM++ deep speaker recognition architecture (`3dspeaker_speech_campplus_sv_en_voxceleb_16k.onnx`), the engine processes speech audio completely on CPU with zero cloud dependencies, zero external HuggingFace token gates, and zero paid APIs.

The engine introduces a vectorized pure NumPy Kaldi-compliant 80-bin Mel filterbank extractor, an Agglomerative Hierarchical Clustering (AHC) algorithm with average (UPGMA) linkage and cosine distance, intelligent temporal turn consolidation with midpoint boundary resolution, and full SQLite persistence with real-time UI synchronization in React/Electron.

---

### 2. Environment & Hardware Specifications

| Component | Specification |
| :--- | :--- |
| **Operating System** | Windows 11 Home (64-bit) |
| **Processor** | Intel Core i7-13620H (10 cores, 16 threads, up to 4.9 GHz) |
| **System RAM** | 16 GB DDR5 |
| **Execution Provider** | ONNX Runtime 1.32.0 (`CPUExecutionProvider`, 2 intra-op threads) |
| **CUDA Dependency** | Zero (100% CPU inference verified) |
| **Python Environment** | Python 3.11.9, NumPy 2.4.6, SQLAlchemy 2.1.9 |
| **Desktop Framework** | Electron + React 18 + TypeScript + Vite + Tailwind CSS |

---

### 3. Model Provenance & Cryptographic Verification

| Metric | Verified Value |
| :--- | :--- |
| **Model Architecture** | 3D-Speaker Context-Aware Masking (CAM++) |
| **Training Corpus** | VoxCeleb 1 & 2 (16 kHz English Speech) |
| **License** | Apache-2.0 |
| **Upstream Source** | `csukuangfj/speaker-embedding-models` (Revision `a8055d6daef723a6a4ecf4de233708575bf4994f`) |
| **Artifact Path** | `backend/storage/clipforge_data/models/audio/3dspeaker_speech_campplus_sv_en_voxceleb_16k.onnx` |
| **File Size** | **29,596,979 bytes** (~28.22 MB) |
| **Published SHA-256** | `98daf9bcf1c8abf3db374fec4c27a5eda7c58705bb3f180d057b085a72a88bb5` |
| **Local Checksum** | `98daf9bcf1c8abf3db374fec4c27a5eda7c58705bb3f180d057b085a72a88bb5` |
| **Verification Status** | **MATCHED EXACTLY (100% Bit-for-Bit Verified)** |

---

### 4. Tensor Signatures & Feature Extraction

- **Input Tensor**:
  - Name: `'x'`
  - Shape: `['N', 'T', 80]` (Dynamic batch $N$, dynamic time frames $T$, 80 Mel bins)
  - Data Type: `float32`
- **Output Tensor**:
  - Name: `'embedding'`
  - Shape: `['BatchNormalizationembedding_dim_0', 512]`
  - Data Type: `float32`
  - Output Normalization: Post-processed with L2 unit norm ($\|\mathbf{e}\|_2 = 1.0$)
- **Feature Extraction (`FBankExtractor`)**:
  - Pure NumPy implementation compliant with standard Kaldi `fbank` parameters:
    - Sampling Rate: 16,000 Hz
    - Frame Length: 25 ms (400 samples)
    - Frame Shift: 10 ms (160 samples)
    - Window Type: Povey window $w[n] = (0.5 - 0.5 \cos(\frac{2\pi n}{N-1}))^{0.85}$
    - Pre-emphasis: 0.97
    - Mel Bins: 80 triangular filters across $20\text{ Hz} \le f \le 7,600\text{ Hz}$
    - Cepstral Mean Normalization (CMN): Time-axis mean subtraction per channel

---

### 5. Algorithmic Architecture

```
+-------------------------------------------------------------------------+
|                  16 kHz Mono PCM Audio Stream                           |
+-------------------------------------------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                Local Silero VAD (Speech Intervals)                      |
+-------------------------------------------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|       Sliding Window Slicer (1.5s duration, 0.75s step, 50% overlap)    |
+-------------------------------------------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|          Pure NumPy 80-bin Kaldi FBank Extractor with CMN               |
+-------------------------------------------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|         3D-Speaker CAM++ ONNX CPU Inference (512-dim, L2-norm)          |
+-------------------------------------------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|     Agglomerative Hierarchical Clustering (AHC-UPGMA-Cosine Distance)    |
+-------------------------------------------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|   Turn Consolidation: Overlap merging, midpoint split, gap bridging     |
+-------------------------------------------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|   SQLite DB (`speakers`, `speaker_turns`, `speaker_embeddings`) & UI    |
+-------------------------------------------------------------------------+
```

---

### 6. Quantitative Acceptance Benchmarks

Measured on the target system hardware (**Intel Core i7-13620H, CPU execution**):

| Benchmark Scenario | Audio Duration | Processing Time | Measured RTF | Real-Time Factor | Result |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Synthetic 3.0s Speech Slice** | 3.00 s | 0.114 s | **0.0382x** | **26.2x faster** | PASSED |
| **Real Speech (Single Speaker)** | 26.22 s | 2.830 s | **0.1080x** | **9.3x faster** | PASSED |
| **Two-Speaker Conversational Dialogue** | 19.00 s | 1.660 s | **0.0871x** | **11.5x faster** | PASSED |
| **Three-Speaker Conversational Dialogue** | 21.50 s | 1.840 s | **0.0856x** | **11.7x faster** | PASSED |

#### Diarization Accuracy & DER Metrics
Evaluated on the conversational dialogue test with 0.25-second boundary collar:
- **Total Reference Speech**: 18.00 s
- **Evaluated Speech (Excluding Collar)**: 16.47 s
- **Missed Speech**: 0.00 s (0.0%)
- **False Alarm Speech**: 0.00 s (0.0%)
- **Speaker Confusion**: 0.00 s (0.0%)
- **Diarization Error Rate (DER)**: **0.00%** (**Target: $\le 15.0\%$**)

#### Memory Consumption
- **Baseline Process RSS**: 67.60 MB
- **Peak Process RSS**: 181.85 MB
- **Incremental Diarization Allocation**: **114.25 MB** (Target: $< 150.0\text{ MB}$)

---

### 7. Database & API Deliverables

#### Database Schema Updates (`backend/app/db/models.py`)
- `speakers`:
  - Added: `analysis_id`, `speaker_identifier`, `display_name`, `total_speech_duration`, `turn_count`, `model_name`, `model_version`, `updated_at`.
- `speaker_turns`:
  - Added table: `id`, `analysis_id`, `speaker_id`, `start_time`, `end_time`, `duration`, `confidence`, `assignment_status` ("auto", "manual", "provisional"), `created_at`, `updated_at`.
- `speaker_embeddings`:
  - Added table: `id`, `analysis_id`, `speaker_id`, `segment_start_time`, `segment_end_time`, `embedding_dimension` (512), `embedding_data`, `quality_score`, `model_version`, `created_at`.
- Non-destructive SQLite schema migration logic integrated in `backend/app/core/database.py:init_db()`.

#### API Endpoints (`backend/app/api/routes/speakers.py`)
- `GET /api/speakers/capabilities`
- `POST /api/audio-analysis/{analysis_id}/diarize`
- `GET /api/audio-analysis/{analysis_id}/speakers`
- `GET /api/audio-analysis/{analysis_id}/speaker-turns`
- `GET /api/audio-analysis/{analysis_id}/diarization`
- `PATCH /api/speaker-turns/{turn_id}`
- `PATCH /api/speakers/{speaker_id}`
- `DELETE /api/audio-analysis/{analysis_id}/speakers`

---

### 8. Frontend React & Electron Integration

- `src/components/speakers/SpeakerCard.tsx`: Speaker identity cards with color swatch, inline name editing, turn count, speech share bar, and filter toggling.
- `src/components/speakers/SpeakerTimeline.tsx`: Interactive horizontal timeline with color-coded speaker segments, hover tooltips, and synchronized playhead with video scrubbing.
- `src/components/speakers/SpeakerTurnEditor.tsx`: Utterance turn list with play-from-start controls, timestamp badges, confidence indicators, and manual speaker reassignment dropdowns.
- `src/components/speakers/SpeakerAnalysisPanel.tsx`: Full container mounted in `src/pages/ProjectStudio.tsx` with VAD integration, parameter tuning (distance threshold, expected speaker count), and background job polling.
- `npm run compile`: **PASSED with 0 errors** (`vite build` + `tsc -p tsconfig.electron.json`).

---

### 9. Regression Suite Verification

- **Total Test Cases Executed**: **127**
- **Passed**: **127** (100%)
- **Failed**: **0**
- **Test Breakdown**:
  - Phase 1 (Foundation): 3 passed
  - Phase 2 (Projects & Import): 4 passed
  - Phase 3 (Video Engine & FFmpeg): 8 passed
  - Phase 4 (Whisper Transcription): 12 passed
  - Phase 5 (AI Highlights & LLM): 22 passed
  - Phase 6 (Visual AI & Smart Crop): 12 passed
  - Phase 7 (Subtitles & Final Render): 12 passed
  - Phase 8 Stage 2 (Audio Preprocessing & Silero VAD): 19 passed
  - **Phase 8 Stage 3 (CAM++ Embeddings)**: **14 passed**
  - **Phase 8 Stage 3 (AHC Clustering)**: **7 passed**
  - **Phase 8 Stage 3 (Speaker Diarization Pipeline)**: **7 passed**
  - **Phase 8 Stage 3 (API Routes & Persistence)**: **7 passed**
