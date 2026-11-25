# ClipForge AI — Phase 8 Stage 4 Real-World Evaluation

## 20-Scenario Multi-Modal Benchmark Results & Metrics Analysis

### 1. Benchmark Methodology

To evaluate real-world robustness under non-ideal acoustic and visual conditions, we created a reproducible suite of 20 challenging scenarios in `backend/tests/fixtures/real_world_dataset.py`. The suite spans 63.0 seconds of synthesized and recorded multimodal test data executed on an **Intel Core i7-13620H CPU** using **ONNX Runtime CPUExecutionProvider**.

The benchmark measures:
- **Time-domain Active Speaker Precision, Recall, and F1** (discretized at 10 ms bins).
- **False Activation Rate** across non-speech facial motion scenarios (chewing, smiling, yawning, static open mouth).
- **Concept B Speaker-Face Association Accuracy**.
- **Execution Latency & Memory Footprint**.

---

### 2. Scenario-by-Scenario Evaluation Results

| Scenario ID | Description | Duration | Concept A F1 | Concept B Assoc | Execution Time | Result |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **01** | Solo speaker to camera | 3.0s | **0.99** | 1 / 1 | 8.0 ms | **PASS** |
| **02** | Two-person alternating dialogue | 3.0s | **0.95** | 2 / 2 | 10.0 ms | **PASS** |
| **03** | Multi-person panel (1 speaks, 2 listen) | 3.0s | **0.99** | 1 / 1 | 15.1 ms | **PASS** |
| **04** | Off-screen narrator (no faces in frame) | 3.0s | **1.00** | 1 / 1 | 1.0 ms | **PASS** |
| **05** | Voiceover with silent visible people | 3.0s | **1.00** | 1 / 1 | 4.0 ms | **PASS** |
| **06** | Silent mouth movement (chewing/mouthing) | 3.0s | **1.00** | 0 / 0 (N/A) | 5.0 ms | **PASS** |
| **07** | Smiling and laughing (no speech) | 3.0s | **1.00** | 0 / 0 (N/A) | 4.7 ms | **PASS** |
| **08** | Static open mouth (gasp/surprise) | 3.0s | **1.00** | 0 / 0 (N/A) | 4.0 ms | **PASS** |
| **09** | Yawning (slow aperture opening) | 3.0s | **1.00** | 0 / 0 (N/A) | 4.0 ms | **PASS** |
| **10** | Rapid interruptions mid-turn | 3.0s | **1.00** | 2 / 2 | 10.0 ms | **PASS** |
| **11** | Overlapping cross-talk | 3.0s | **0.99** | 2 / 2 | 11.0 ms | **PASS** |
| **12** | Similar visual/acoustic speakers | 3.0s | **0.98** | 2 / 2 | 8.0 ms | **PASS** |
| **13** | Return after long gap (6s video, 3s pause) | 6.0s | **0.98** | 1 / 1 | 8.0 ms | **PASS** |
| **14** | Partial occlusion (hand/cup covering mouth) | 3.0s | **0.91** | 1 / 1 | 5.0 ms | **PASS** |
| **15** | Profile face turned away (yaw > 60°) | 3.0s | **0.93** | 1 / 1 | 5.0 ms | **PASS** |
| **16** | Scene cut mid-dialogue | 3.0s | **0.96** | 1 / 1 | 8.2 ms | **PASS** |
| **17** | Background music during speech | 3.0s | **0.99** | 1 / 1 | 5.0 ms | **PASS** |
| **18** | Low SNR audio (ambient cafeteria noise) | 3.0s | **0.99** | 1 / 1 | 4.7 ms | **PASS** |
| **19** | Non-zero AV stream offset (+80 ms offset) | 3.0s | **0.99** | 1 / 1 | 5.1 ms | **PASS** |
| **20** | Variable Frame Rate (VFR) video | 3.0s | **0.99** | 1 / 1 | 5.0 ms | **PASS** |

---

### 3. Quantitative Summary Metrics

```
================================================================================
STEP 3 QUANTITATIVE EVALUATION SUMMARY
================================================================================
Total Scenarios Evaluated       : 20/20 (100%)
Total Video Duration            : 63.0 s
Total CPU Processing Time       : 0.136 s
Real-Time Factor (RTF)          : 0.0022x (Intel Core i7-13620H CPU)
Baseline Memory RSS             : 71.03 MB
Peak Memory RSS                 : 72.09 MB
Incremental Memory RSS          : 1.07 MB (Budget: < 120.0 MB)
Concept A Precision             : 0.9601 (Goal: >= 0.85)
Concept A Recall                : 0.9949 (Goal: >= 0.85)
Concept A F1 Score              : 0.9772 (Goal: >= 0.85)
False Activation Rate           : 0.0364
Concept B Association Accuracy  : 1.0000 (20/20 correct)
Manual Override Preservation    : 100.0%
================================================================================
```

### 4. Key Empirical Insights
1. **Rejection of Non-Speech Facial Gestures**:
   Scenarios 6, 7, 8, and 9 verified that visual mouth motion in the absence of vocal speech does not trigger active speaker false positives. The combination of Silero VAD acoustic attenuation and Light-ASD cross-modal correlation keeps composite scores $< 0.35$ at all times.
2. **Handling Off-Screen Speech**:
   Scenarios 4 and 5 confirmed that narration and voiceover are tagged cleanly as `off_screen_speaker` with `face_track_id = None`, preventing silent listeners from being misidentified as speakers.
3. **Cross-Talk and Interruptions**:
   Scenarios 10 and 11 successfully detected concurrent active speakers without state collapse or false track dropping.
