# Phase 8 Stage 4: Active Speaker Detection
## Benchmark Reproducibility & Verification Guide

This document provides exact, deterministic instructions to reproduce all benchmarks, evaluations, and test suites conducted during the Phase 8 Stage 4 verification of ClipForge AI.

---

## 1. Environment & Prerequisites

### 1.1 Operating System & Hardware
- **Operating System**: Windows 11 (64-bit)
- **CPU**: x86_64 architecture with AVX2 support (tested on Intel Core i7-13620H)
- **RAM**: Minimum 8 GB available (tested on 16 GB DDR5)
- **Python**: 3.11.9 (64-bit)
- **Node.js**: v20+ / npm

### 1.2 Virtual Environment & Dependencies
Ensure the backend Python virtual environment is activated:
```powershell
# From project root: c:\Users\yogac\Downloads\clipsmaster
.\backend\venv\Scripts\Activate.ps1
```

Verify core package versions:
```powershell
python -c "import onnxruntime, torch, numpy; print(f'ORT: {onnxruntime.__version__}, PyTorch: {torch.__version__}, NumPy: {numpy.__version__}')"
# Expected: ORT: 1.32.0, PyTorch: 2.6.0+cpu, NumPy: 2.4.6
```

### 1.3 ONNX Model Artifact Locations
Verify that the local ONNX weights exist and match expected file sizes:
```powershell
Get-ChildItem -Path "backend\storage\clipforge_data\models\audio", "backend\storage\clipforge_data\models\vision" -Recurse -Filter "*.onnx" | Select-Object FullName, Length
```
- `backend/storage/clipforge_data/models/vision/light_asd_small.onnx`: ~1.8 MB
- `backend/storage/clipforge_data/models/vision/face_mesh_v2.onnx`: ~3.8 MB
- `backend/storage/clipforge_data/models/audio/3dspeaker_speech_campplus_sv_en_voxceleb_16k.onnx`: ~28.6 MB
- `backend/storage/clipforge_data/models/audio/silero_vad.onnx`: ~1.7 MB

---

## 2. Reproducing Benchmark 1: Multimodal Fusion & Association Micro-Benchmark

This micro-benchmark tests the `AVFusionEngine` and `SpeakerFaceAssociator` across 20 synthetic edge-case scenarios (63 seconds total speech).

### Execution Command:
```powershell
python backend/tests/benchmark_phase8_stage4_step3.py
```

### Expected Output:
- **Terminal Summary**:
  ```
  Concept A (Active Speaker Detection):
    Precision: 0.9601
    Recall: 0.9949
    F1 Score: 0.9772
    False Activation Rate: 0.0364
  Concept B (Speaker-Face Association):
    Association Accuracy: 1.0000 (20/20)
    Manual Override Retention: 1.0000
  Performance:
    Total benchmark time: 0.136 s
    Real-Time Factor (RTF): 0.0022x
    Peak RSS: ~72 MB (Incremental RSS: 1.07 MB)
  ```
- **Generated File**: `docs/PHASE8_STAGE4_STEP3_RESULTS.json`

---

## 3. Reproducing Benchmark 2: End-to-End Real Video & Pipeline Memory Audit

This benchmark runs real video decoding, 4 FPS face tracking, 25 FPS linear coordinate interpolation, Face Mesh landmark extraction, Light-ASD ONNX inference, and multimodal fusion on an actual 720p 24 fps test video (`test_multimodal_8s.mp4`) across 1, 2, and 4 visible faces with 3 repetitions.

### Execution Command:
```powershell
python backend/tests/audit_phase8_stage4_production.py
```

### Expected Output:
- **Terminal Summary**:
  - Baseline RSS: ~77.31 MB
  - Post-ONNX Init RSS: ~97.82 MB (+20.51 MB)
  - 1-Face Scenario: RTF ~0.89x, Peak RSS ~195 MB
  - 2-Face Scenario: RTF ~1.67x, Peak RSS ~199 MB
  - 4-Face Scenario: RTF ~3.48x, Peak RSS ~200 MB
  - Temporal Adapter: 3.45x speedup with 100% agreement accuracy
- **Generated File**: `docs/PHASE8_STAGE4_PRODUCTION_AUDIT_RESULTS.json`

---

## 4. Reproducing Benchmark 3: Held-Out Dataset Generalization

This benchmark tests 10 unseen acoustic and visual scenarios with frozen production thresholds ($\tau_{\text{on}}=0.65, \tau_{\text{off}}=0.35$).

### Execution Command:
```powershell
python backend/tests/evaluate_held_out_dataset.py
```

### Expected Output:
- **Terminal Summary**:
  - Precision: **0.9814**
  - Recall: **0.9961**
  - F1 Score: **0.9887**
  - Association Accuracy: **1.0000** (8/8)
- **Generated File**: `docs/PHASE8_STAGE4_HELDOUT_RESULTS.json`

---

## 5. Running the Complete Regression Test Suite

To verify all 187 automated backend unit, integration, and performance tests:
```powershell
pytest backend/tests/ -q
```
- **Expected Result**: `187 passed in ~90s (100%)`

To run active-speaker specific test suites:
```powershell
pytest backend/tests/test_active_speaker_detector.py backend/tests/test_av_fusion_engine.py backend/tests/test_active_speaker_service.py -v
```

---

## 6. Frontend & Electron Build Verification

To verify that all TypeScript types, API service integrations, and renderer bundles build cleanly:
```powershell
npm run compile
```
- **Expected Result**:
  - Vite build completes with zero errors.
  - Electron TypeScript compilation (`tsc -p tsconfig.electron.json`) exits with code `0`.

---

## 7. Python Compilation Verification

To verify that no syntax errors or invalid imports exist across the backend:
```powershell
python -m compileall backend/app -q
```
- **Expected Result**: Exits silently with code `0` (zero compilation warnings or errors).
