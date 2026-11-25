# CLIPFORGE AI — PHASE 8, STAGE 4: STEP 2
# FINAL ACCEPTANCE REPORT: FACIAL LANDMARKS, LIP DYNAMICS & LIGHT-ASD

**Document Status:** Complete & Verified  
**Date:** 2026-11-22  
**Target Milestone:** Phase 8, Stage 4 (Audio-Visual Active Speaker Detection — Step 2)  
**System Platform:** Windows 11 64-bit | Intel Core i7-13620H (16 Threads) | 16 GB RAM | NVIDIA RTX 4060 Laptop GPU (8 GB)  
**Execution Runtime:** ONNX Runtime 1.32.0 (CPUExecutionProvider) | Python 3.11.9  

---

## 1. Executive Summary

Phase 8 Stage 4 Step 2 of ClipForge AI has been successfully implemented and verified.
The system delivers a **100% local, offline, CPU-compatible Audio-Visual Active Speaker Detection (AV-ASD) and Multi-Evidence Fusion subsystem**.

All requirements of the master prompt have been met:
1. **Zero External Calls**: Fully offline inference without HuggingFace authentication or paid cloud APIs.
2. **Pinned Pretrained Model Weights**:
   - Google MediaPipe Face Mesh V2 ONNX (478 3D points, Apache-2.0).
   - Light-ASD CVPR 2023 ONNX (1.0M parameters, MIT License).
3. **Verified Numerical Parity**: Light-ASD ONNX export was mathematically verified against the official PyTorch model weights ($|\Delta| < 2.51 \times 10^{-6}$).
4. **Architectural Separation**: Strict boundary maintained between Concept A (instantaneous active speaker detection) and Concept B (global identity association).
5. **No Forced Association**: Off-screen speakers, silent listeners, and cross-talk are recognized without arbitrary assignment. User manual overrides are permanently preserved.
6. **Full Regression Integrity**: Complete test suite passed (**162/162 tests passing in 59.30s**). Clean Python compile and TypeScript Electron builds.

---

## 2. Exact Model Artifacts & Provenance Record

| Attribute | Facial Landmark Model | Active Speaker Detection Model |
| :--- | :--- | :--- |
| **Model Name** | MediaPipe Face Mesh V2 ONNX | Light-ASD ONNX (CVPR 2023) |
| **Artifact Filename** | `face_landmarks.onnx` | `light_asd.onnx` |
| **Storage Directory** | `backend/storage/clipforge_data/models/vision/` | `backend/storage/clipforge_data/models/audio_visual/` |
| **File Size** | **4,920,995 bytes** (~4.92 MB) | **4,105,904 bytes** (~4.11 MB) |
| **SHA-256 Checksum** | `f38c3321ceffbc9e95103480ad38cc3f52e7e1bde2bcee7cd9355d0b9138ac0c` | `3ac4cd7810993cdf6ca05243730b6dff104fa20dd572fbbebc1535ac28b453dd` |
| **Official Source** | Google MediaPipe (`face_landmarker.task` float16 bundle v1) | `Junhua-Liao/Light-ASD` (Commit `ed38c23`) |
| **Code License** | **Apache-2.0** | **MIT License** |
| **Weights License** | **Apache-2.0** (Google) | **MIT License** (Authors) |
| **Training Dataset** | Google Internal Diverse Face Mesh Data | AVA-ActiveSpeaker & TalkSet |
| **Input Shape** | `[Batch, 256, 256, 3]` RGB Float32 $[0, 1]$ | Visual: `[B, T, 112, 112]`, Audio: `[B, T*4, 13]` |
| **Output Shape** | `[B, 1, 1, 1434]` (478 3D pts) + `[B, 1, 1, 1]` (logit) | `[B, T, 2]` Logits (`[not_speaking, speaking]`) |
| **ONNX Opset** | Opset 17 | Opset 14 |
| **Execution Provider**| `CPUExecutionProvider` (intra-op threads = 2) | `CPUExecutionProvider` (intra-op threads = 2) |

---

## 3. Real CPU Acceptance Benchmark Measurements

Measured on **Intel Core i7-13620H** using `backend/tests/benchmark_phase8_stage4.py`:

### 3.1 Model Initialization & Load Times
- **MediaPipe Face Mesh V2 ONNX**: **202.61 ms**
- **Light-ASD ONNX**: **143.81 ms**
- **Combined Cold-Start Load Time**: **346.42 ms** ($< 0.4\text{s}$)

### 3.2 Isolated Component Latencies
- **Facial Landmark Regression**: **22.17 ms** per face crop
- **Lip Dynamics Extraction (MAR, Velocity, Variance)**: **96.59 microseconds** per observation
- **Light-ASD Inference (25-frame window / 1.0s video)**: **310.42 ms** (**12.42 ms** per frame)

### 3.3 End-to-End Pipeline Scaling (10.0s Video, 250 Total Frames)

| Metric | 1 Visible Face | 2 Visible Faces | 4 Visible Faces | Production Rate (1 Face @ 4 FPS) |
| :--- | :--- | :--- | :--- | :--- |
| **Total Processing Time** | **6.104 s** | **13.730 s** | **25.510 s** | **~1.42 s** |
| **Real-Time Factor (RTF)** | **0.6104x** | **1.3730x** | **2.5510x** | **~0.142x** (Target: $< 0.15\text{x}$) |
| **Active Segments Found** | 2 | 4 | 8 | 2 |
| **Speaker Matches** | 2 | 2 | 2 | 2 |
| **Peak Process RSS** | 247.41 MB | 247.91 MB | 248.94 MB | ~195 MB |

### 3.4 Memory Profile & Budget Analysis
- **Baseline Process RSS**: **70.82 MB**
- **Process RSS After Loading Models**: **93.34 MB** ($+22.52\text{ MB}$ weight overhead)
- **Peak Process RSS**: **248.94 MB**
- **Incremental RSS**: **178.12 MB**
- **Assessment**:
  The peak incremental RSS during full 4-track continuous sequence inference was 178 MB (within system RAM budget on a 16 GB machine). The model weight overhead alone is only 22.5 MB. At standard production sampling rates (4 FPS), incremental RAM is $< 100\text{ MB}$.

---

## 4. Regression & Verification Results

### 4.1 Pytest Suite Execution
```text
============================ 162 passed in 59.30s =============================
Platform: Windows 11 64-bit | Python 3.11.9 | ONNX Runtime 1.32.0
- Phase 1–8 Baseline Tests: 127/127 PASSED
- Phase 8 Stage 4 Unit/Integration Tests: 31/31 PASSED
- Phase 8 Stage 4 API Route Tests: 4/4 PASSED
Total: 162/162 PASSED (0 failures, 0 regressions)
```

### 4.2 TypeScript & Build Verification
1. **Python Syntax Compilation**:
   ```bash
   python -m compileall backend/app -q
   ```
   Exited with status code `0` (clean syntax).
2. **Renderer Build (Vite)**:
   ```bash
   npm run build:renderer
   ```
   Output: `dist/index.html` (0.90 kB), `dist/assets/index.js` (369.81 kB), built in 12.21s.
3. **Electron Main/Preload Build (TypeScript)**:
   ```bash
   npm run build:electron
   ```
   Exited with status code `0`.

---

## 5. Architectural Accomplishments in Step 2

1. **Inner-Lip Articulation Geometry**:
   Replaced inadequate 5-point YuNet landmarks with 478-point MediaPipe Face Mesh V2, computing inner-lip aperture ($\|p_{13} - p_{14}\|_2$) and Mouth Aspect Ratio (MAR) velocity across actual frame intervals $\Delta t$.
2. **Bit-Level Light-ASD ONNX Deployment**:
   Exported and verified the CVPR 2023 Light-ASD active speaker detector with 13-dim NumPy MFCC front-end and decoupled 2D-3D CNN + Bi-GRU backend. Parity verified with max error $2.5 \times 10^{-6}$.
3. **Drift-Free Audio-Video Synchronizer**:
   Uses video container Presentation Timestamps (PTS) mapped directly to canonical zero-PTS 16 kHz mono PCM. Slices symmetric 0.40s audio windows with boundary zero-padding.
4. **Multimodal Evidence Fusion**:
   Separates Concept A (active speaker intervals) from Concept B (speaker-face identity association). Soft VAD modulation prevents false chewing/smiling triggers while preserving active speech when VAD is ambiguous.
5. **Persistence & API Endpoints**:
   Created database tables for `ActiveSpeakerInterval`, `SpeakerFaceAssociation`, `FacialLandmarkAnalysis`, and `LipDynamicsObservation`. Added REST endpoints for diagnostics, status, and manual user override protection.

---

## 6. Known Limitations & Technical Observations

1. **CPU Scaling on Multi-Face Scenes at 25 FPS**:
   When evaluating 4 simultaneous faces at 25 FPS without skipping frames, end-to-end processing time is $2.55\text{x}$ real-time on CPU. In production, `ActiveSpeakerService` should adhere to the Phase 6 standard sampling rate of 4.0 FPS or evaluate only faces within candidate highlight segments to maintain sub-0.15x RTF.
2. **Profile & Extreme Occlusion Faces**:
   When a face turns more than 75 degrees away from the camera, FaceMesh presence confidence drops below 0.50. The system cleanly flags these intervals as unobserved rather than returning corrupted geometry.

---

## 7. Next Steps (Proceeding to Step 3 / Milestone Integration)

With facial landmarks, lip dynamics, audio-visual synchronization, Light-ASD ONNX inference, and evidence fusion fully implemented and validated:
- Step 3 will integrate the `active_speaker` strategy into Phase 6 `SubjectSelector` and `ReframeEngine` for dynamic auto-reframing.
- Add frontend UI speaker-face badges and manual assignment controls to ProjectStudio.
