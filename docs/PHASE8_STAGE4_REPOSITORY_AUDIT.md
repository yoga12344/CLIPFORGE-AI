# ClipForge AI — Phase 8 Stage 4 Technical Audit
## Repository Subsystem Audit: Computer Vision, Audio Intelligence & Speaker Diarization

**Document Status:** Complete & Verified  
**Date:** 2026-11-22  
**Target:** Phase 8, Stage 4 (Audio-Visual Active Speaker Detection)  
**Author:** Senior Computer Vision Engineer & Audio-Visual ML Researcher  

---

### 1. Executive Summary

Phase 8 Stage 4 introduces **Audio-Visual Active Speaker Detection (AV-ASD)** and **Speaker-to-Face Association** into ClipForge AI. Active speaker detection identifies *which visible face is currently speaking* in video scenes with multiple individuals, and links persistent visual face tracks to offline diarized audio speakers (`SPEAKER_00`, `SPEAKER_01`).

This audit inspects existing production subsystems across Phase 6 (Computer Vision & Smart Reframing), Phase 8 Stage 2 (Audio Preprocessing & Silero VAD), and Phase 8 Stage 3 (3D-Speaker CAM++ Diarization). It identifies reusable modules, exposes architectural gaps, addresses the critical technical question regarding OpenCV YuNet's five landmarks, and defines boundary interfaces for Stage 4.

---

### 2. Phase 6 Computer Vision Subsystem Audit

#### 2.1 Component Inventory & Inspection

| Component | File Path | Existing Capabilities | Stage 4 Reusability |
| :--- | :--- | :--- | :--- |
| **`YuNetFaceDetector`** | `backend/app/ai/vision/face_detector.py` | Local ONNX inference via OpenCV DNN (`face_detection_yunet_2023mar.onnx`, 232 KB). Outputs bounding boxes, detection confidences, and 5 facial landmarks. | **High**: Fast face proposal generator (3–10 ms/frame on CPU). Face crops can be passed directly to the AV-ASD visual pipeline. |
| **`FaceTracker`** | `backend/app/ai/vision/face_tracker.py` | Spatial-temporal tracker combining Intersection-over-Union (IoU) and centroid Euclidean distance matching. Maintains persistent `track_id` over time. | **High**: Provides continuous temporal face trajectories ($T_{\text{start}}$ to $T_{\text{end}}$) needed for multi-frame temporal modeling. |
| **`SubjectSelector`** | `backend/app/ai/vision/subject_selector.py` | Heuristic selection of camera reframing target (`largest_face`, `center_face`, `manual_track`, `group`). | **High**: Needs an additional `active_speaker` strategy that queries Stage 4 association scores. |
| **`ReframeEngine`** | `backend/app/ai/vision/reframe_engine.py` | Aspect-ratio crop calculation (9:16, 1:1, 4:5), headroom preservation, EMA trajectory smoothing, velocity limits, and manual keyframe overrides. | **High**: Core framing engine remains unchanged; will receive target bbox from the active speaker selector. |
| **`FaceTrack` Model** | `backend/app/db/models.py:313` | SQLite table storing `vision_analysis_id`, `track_id`, `start_time`, `end_time`, `detection_count`, `average_bbox`, and sampled detections. | **High**: Database entity representing visual subjects; will be foreign-keyed by Stage 4 speaker-face associations. |
| **`ManualCropCorrection`** | `backend/app/db/models.py:330` | Stores user-defined crop keyframes (`crop_x`, `crop_y`, `crop_width`). | **Mandatory Constraint**: Must have absolute priority over active speaker automated framing. |

#### 2.2 Critical Technical Question: YuNet 5 Landmarks vs. Mouth Motion

```
                     YuNet 5-Landmark Topology
                     
                     (0) [Right Eye]      (1) [Left Eye]
                                \       /
                                 (2) [Nose Tip]
                                /       \
           (3) [Right Mouth Corner]-----(4) [Left Mouth Corner]
```

##### Deep Analysis of YuNet Landmark Array:
In `backend/app/ai/vision/face_detector.py` (lines 153–178), the YuNet ONNX detector outputs a 15-element tensor per detected face:
- `face[0:4]`: Bounding box pixel coordinates $(x, y, w, h)$.
- `face[4:14]`: 5 landmark pairs $(x_k, y_k)$:
  - Landmark 0 (`face[4:6]`): Right eye pupil center.
  - Landmark 1 (`face[6:8]`): Left eye pupil center.
  - Landmark 2 (`face[8:10]`): Nose tip.
  - Landmark 3 (`face[10:12]`): **Right mouth corner (cheilion)**.
  - Landmark 4 (`face[12:14]`): **Left mouth corner (cheilion)**.
- `face[14]`: Detection confidence score.

##### Fundamental Limitation for Speech Detection:
1. **Absence of Vertical Aperture**:
   YuNet outputs *only the two lateral mouth corners*. It does **not** detect the upper lip (labrale superius) or lower lip (labrale inferius).
2. **Kinematics of Speech**:
   Speech articulation is predominantly driven by vertical mandibular lowering and inter-lip separation (opening for vowels such as /ɑː/, /oʊ/, /æ/, closing for bilabial plosives /p/, /b/, /m/). The horizontal distance between mouth corners changes negligibly during conversational speech, and in phonemes with lip rounding (/uː/, /w/), the corners actually move *inward*.
3. **Mouth Aspect Ratio (MAR) Impossibility**:
   Standard Mouth Aspect Ratio requires:
   $$\text{MAR} = \frac{\|p_{\text{upper\_lip}} - p_{\text{lower\_lip}}\|_2}{\|p_{\text{left\_corner}} - p_{\text{right\_corner}}\|_2}$$
   Because YuNet lacks upper and lower lip points, it cannot compute MAR.
4. **Distance to Nose Tip as a Fallback**:
   Approximating mouth opening by measuring vertical distance between nose tip $(x_2, y_2)$ and the mouth corner midpoint $\frac{p_3 + p_4}{2}$ is deeply confounded by head pitch (nodding, tilting up/down) and facial expressions (smiling lifts mouth corners toward the nose).
5. **Conclusion**:
   **YuNet's five landmarks cannot provide an accurate lip opening metric or definitive speech detection.** Attempting to use mouth-corner displacement produces intolerable false-positive rates on smiling/nodding and false-negative rates on subtle speech.
   **A dedicated visual speech representation is mandatory.** This must either be:
   - A dedicated 2D/3D dense facial landmark model (such as MediaPipe Face Mesh ONNX predicting lip contour points 13 and 14 for true MAR), OR
   - A learned audio-visual active speaker detection neural network (such as Light-ASD or TalkNet) that ingests raw face crops ($112 \times 112$) and raw audio spectrograms.

---

### 3. Phase 8 Stage 2 Audio Intelligence Subsystem Audit

#### 3.1 Component Inventory & Inspection

| Component | File Path | Existing Capabilities | Stage 4 Reusability |
| :--- | :--- | :--- | :--- |
| **`AudioPreprocessor`** | `backend/app/ai/audio/audio_preprocessor.py` | Extracts canonical 16kHz mono 16-bit linear PCM (`pcm_s16le`) without `shell=True`. Preserves project audio cache at `storage/clipforge_data/projects/{project_id}/audio/{video_id}_16k.wav`. | **High**: Zero duplicate audio extraction required. Stage 4 can read the already cached canonical 16kHz WAV file directly via memory mapping or `wave`. |
| **`VoiceActivityDetector`** | `backend/app/ai/audio/voice_activity_detector.py` | Local Silero VAD v4 (ONNX Runtime on CPU). Produces non-overlapping `SpeechInterval` records with millisecond accuracy. RTF $\approx 0.013\times$. | **High**: Pre-filters non-speech segments. Visual ASD inference can be skipped entirely during silence, saving up to 60% CPU cycles. |
| **`SpeechInterval` Model** | `backend/app/db/models.py:383` | SQLite table storing `analysis_id`, `start_time`, `end_time`, `duration`, `speech_probability`, `confidence`. | **High**: Provides the ground-truth temporal regions where speech is acoustically present. |
| **Stream Timestamp Preservation** | `backend/app/video/ffmpeg_manager.py` | Uses FFmpeg audio filter `aresample=async=1:first_pts=0` to guarantee that audio sample index 0 maps exactly to presentation timestamp $t = 0.000\text{ s}$. | **Critical**: Eliminates audio-to-video drift caused by non-zero audio stream start PTS. |

#### 3.2 Slicing Synchronized Audio Windows:
Because `AudioPreprocessor` writes a persistent 16kHz mono WAV file for every video:
- Any arbitrary video time interval $[t_{\text{start}}, t_{\text{end}}]$ maps directly to sample slice:
  $$\text{sample}_{\text{start}} = \lfloor t_{\text{start}} \times 16000 \rfloor, \quad \text{sample}_{\text{end}} = \lceil t_{\text{end}} \times 16000 \rceil$$
- No FFmpeg re-invocation is needed for Stage 4 audio feature extraction.

---

### 4. Phase 8 Stage 3 Speaker Diarization Subsystem Audit

#### 4.1 Component Inventory & Inspection

| Component | File Path | Existing Capabilities | Stage 4 Reusability |
| :--- | :--- | :--- | :--- |
| **`SpeakerEmbeddingExtractor`** | `backend/app/ai/audio/speaker_embeddings.py` | 3D-Speaker CAM++ ONNX model (`3dspeaker_speech_campplus_sv_en_voxceleb_16k.onnx`). Pure NumPy 80-bin Kaldi FBank with CMN. Produces 512-dim L2-normalized embeddings. RTF $\approx 0.038\times$. | **Protected Subsystem**: Model and feature extraction will remain untouched. Provides global vocal identities. |
| **`SpeakerClusterer`** | `backend/app/ai/audio/speaker_clustering.py` | Pure NumPy Agglomerative Hierarchical Clustering (AHC) with average (UPGMA) linkage and cosine distance. | **Protected Subsystem**: Clusters acoustic embeddings into discrete speakers (`SPEAKER_00`, `SPEAKER_01`). |
| **`SpeakerDiarizer`** | `backend/app/ai/audio/speaker_diarizer.py` | Sliding window segmentation (1.5s window, 0.75s step), turn consolidation with midpoint boundary resolution, silence gap bridging. | **High**: Provides consolidated `SpeakerTurn` records representing *who spoke when*. |
| **`Speaker` Model** | `backend/app/db/models.py:93` | Stores recognized speaker identity (`analysis_id`, `speaker_identifier`, `display_name`, `color`, `total_speech_duration`, `turn_count`). | **High**: Target entity for face track binding. |
| **`SpeakerTurn` Model** | `backend/app/db/models.py:421` | Stores continuous turns (`analysis_id`, `speaker_id`, `start_time`, `end_time`, `confidence`, `assignment_status`). | **High**: Time intervals during which acoustic speaker identity is known. |
| **`SpeakerEmbedding` Model** | `backend/app/db/models.py:402` | Stores window embeddings (`analysis_id`, `speaker_id`, `segment_start_time`, `segment_end_time`, 512-dim vector in JSON). | **Medium**: Can be used for cross-modal similarity or acoustic confidence re-weighting. |

#### 4.2 Preserving Manual User Corrections:
`SpeakerTurn` includes `assignment_status` ("auto", "manual", "provisional"):
- If a user manually renames a speaker or reassigns a speaker turn in the Stage 3 UI, `assignment_status` is marked `"manual"`.
- Stage 4 audio-visual fusion must treat `"manual"` speaker turns as immutable ground truth for the audio identity, adjusting the face association rather than overriding the turn assignment.

---

### 5. Reusable Components vs. Missing Components Summary

```
+-----------------------------------------------------------------------------------------+
|                                REUSABLE FOUNDATION                                      |
+-----------------------------------------------------------------------------------------+
| [Phase 6]  OpenCV YuNet Face Detector (ONNX, CPU, BBox proposals)                       |
| [Phase 6]  Spatial-Temporal Face Tracker (Multi-frame TrackedFace continuity)           |
| [Phase 6]  SubjectSelector & ReframeEngine (Headroom, EMA, Clamp, Keyframe Overrides)   |
| [Phase 8]  AudioPreprocessor (Canonical 16kHz mono WAV cache, zero-PTS aligned)        |
| [Phase 8]  VoiceActivityDetector (Silero VAD v4, SpeechInterval boundaries)             |
| [Phase 8]  SpeakerDiarizer & Models (Speaker, SpeakerTurn, CAM++ 512-dim clusters)     |
+-----------------------------------------------------------------------------------------+
                                            |
                                            v
+-----------------------------------------------------------------------------------------+
|                               MISSING STAGE 4 MODULES                                   |
+-----------------------------------------------------------------------------------------+
| [Missing 1] High-resolution facial landmark / lip contour extractor (MediaPipe Mesh)    |
| [Missing 2] Synchronized audio-visual window tensor builder (25 FPS video + 16kHz audio)|
| [Missing 3] Active Speaker Detection ONNX neural model (Light-ASD / LR-ASD)             |
| [Missing 4] Audio-Visual Fusion Engine (Active Speaker probabilities + Diarization bind)|
| [Missing 5] Database Models (`ActiveSpeakerInterval`, `SpeakerFaceAssociation`)          |
| [Missing 6] Active Speaker Strategy in `SubjectSelector` with hysteresis smoothing      |
| [Missing 7] REST Endpoints (`/api/active-speakers/`) & Frontend UI Visualizers          |
+-----------------------------------------------------------------------------------------+
```

---

### 6. Risk Analysis & Verification Checklist

1. **Risk: Video/Audio Frame Rate Desynchronization**:
   - Consumer MP4 files frequently use Variable Frame Rate (VFR). Calculating frame timestamp as $\frac{\text{frame\_index}}{\text{nominal\_fps}}$ causes progressive temporal drift.
   - *Mitigation*: Use container Presentation Timestamps (PTS) extracted via FFprobe/OpenCV `CAP_PROP_POS_MSEC` or sample video frames to match exact audio timestamps.
2. **Risk: False Speaker Swapping during Rapid Cuts**:
   - Shot transitions or rapid camera cuts cause face tracker IDs to reset or jump.
   - *Mitigation*: Integrate shot boundary detection (`SceneAnalyzer`) to flush face tracker histories and audio-visual association buffers across scene cuts.
3. **Risk: Memory Exhaustion on Long Videos**:
   - Loading all video frame crops for a 1-hour video into RAM would consume several gigabytes.
   - *Mitigation*: Stream processing in temporal blocks (e.g., 10-second chunks), identical to Phase 8 Stage 2 chunked streaming.
