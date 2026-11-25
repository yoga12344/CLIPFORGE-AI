# CLIPFORGE AI — PHASE 8, STAGE 4
# MODEL MANIFEST & PROVENANCE RECORD

**Status:** Official & Documented  
**Target Environment:** Windows 11 (Intel Core i7-13620H, ONNX Runtime CPU Execution)  
**Date:** 2026-11-22  
**Standard:** Local-First, Offline, Zero Cloud Telemetry, Permissive Licenses  

---

## 1. Facial Landmark Model: MediaPipe Face Mesh V2 ONNX

### 1.1 Model Identity & Provenance
- **Model Name:** MediaPipe Face Mesh V2 Dense Landmark Detector
- **Originating Framework:** Google MediaPipe (`google-ai-edge/mediapipe`)
- **Source Model Artifact:** `face_landmarks_detector.tflite` inside `face_landmarker.task` (float16 bundle v1)
- **Source Official URL:**  
  `https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task`
- **Source TFLite SHA-256:** `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`
- **Conversion Repository:** `naklitechie/face-landmarks-onnx` on Hugging Face Hub
- **Repository URL:** `https://huggingface.co/naklitechie/face-landmarks-onnx`
- **Conversion Toolchain:** `tf2onnx` (opset 17) directly from Google's official float16 TFLite bundle. Maximum numerical divergence on random test vectors: $< 0.0005$.
- **Artifact Filename:** `face_landmarks.onnx`
- **Target Storage Path:** `backend/storage/clipforge_data/models/vision/face_landmarks.onnx`
- **File Size:** 4,920,995 bytes (~4.92 MB)
- **SHA-256 Checksum:** `f38c3321ceffbc9e95103480ad38cc3f52e7e1bde2bcee7cd9355d0b9138ac0c`

### 1.2 Multi-Tier Licensing & IP Compliance
- **Code License:** Apache-2.0 (Google MediaPipe, tf2onnx)
- **Model Weights License:** Apache-2.0 (Google open-source weights)
- **Dataset Terms & Attribution:**  
  Trained on Google internal diverse face datasets under standard research/commercial permissive terms. Model card specifies: identification and life-critical decisions outside intended use; landmark geometry estimation inside video processing is fully compliant.
- **Commercial Redistribution:** Permitted with Apache-2.0 notice attribution.

### 1.3 Tensor Contract & Specifications
- **Input Tensor:**
  - Name: `input_12` (or first input)
  - Shape: `[Batch, 256, 256, 3]` (NHWC layout)
  - Data Type: `float32`
  - Color Order: **RGB**
  - Normalization: Pixels in range $[0.0, 1.0]$ ($\frac{\text{pixel}}{255.0}$)
- **Output Tensors:**
  - `Identity`: Shape `[Batch, 1, 1, 1434]`. Represents 478 3D landmarks ($478 \times 3 = 1434$).
    - $478$ points: 468 dense facial mesh points + 10 iris keypoints (5 right eye, 5 left eye).
    - Coordinates $(x, y, z)$ are in pixel space $[0.0, 256.0]$ relative to the $256 \times 256$ input crop.
    - $z$ coordinate represents depth relative to the center of the face mesh.
  - `Identity_1`: Shape `[Batch, 1, 1, 1]`. Face-presence logit.
    - Post-processing: $\text{Confidence} = \sigma(\text{Identity\_1}) = \frac{1}{1 + e^{-\text{logit}}}$.
    - Face is deemed valid if $\text{Confidence} \ge 0.50$.
  - `Identity_2`: Shape `[Batch, 1]`. Face activity score.
- **Crucial Landmark Topology Indices:**
  - **13**: Inner upper lip center
  - **14**: Inner lower lip center
  - **61**: Left mouth corner (outer)
  - **291**: Right mouth corner (outer)
  - **78**: Left mouth corner (inner)
  - **308**: Right mouth corner (inner)
  - **0**: Outer upper lip center
  - **17**: Outer lower lip center
- **ONNX Compatibility:** Opset 17, fully compatible with ONNX Runtime CPU (`CPUExecutionProvider`).

---

## 2. Active-Speaker Detection Model: Light-ASD (CVPR 2023)

### 2.1 Model Identity & Provenance
- **Model Name:** Light-ASD (A Light Weight Model for Active Speaker Detection)
- **Primary Publication:** IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR 2023)
- **Authors:** Junhua Liao, Haihan Duan, Kanghui Feng, Wanbing Zhao, Yanbing Yang, Liangyin Chen (Sichuan University)
- **Source Repository:** `Junhua-Liao/Light-ASD` on GitHub
- **Repository URL:** `https://github.com/Junhua-Liao/Light-ASD`
- **Source Commit:** `ed38c232de5efe0261dbd68627c0ade7cdfe14eb` (main)
- **Pretrained Weights Artifact:** `weight/finetuning_TalkSet.model` (and `weight/pretrain_AVA_CVPR.model`)
- **Direct Checkpoint Download URL:**  
  `https://raw.githubusercontent.com/Junhua-Liao/Light-ASD/main/weight/finetuning_TalkSet.model`
- **Checkpoint Size:** 4,175,289 bytes (~4.18 MB)
- **Checkpoint SHA-256:** `efc375833887eefa9d209dc92810e18519b04c3c73ea35a549f2a7f40b7d94d5`
- **Exported ONNX Artifact:** `light_asd.onnx`
- **Target Storage Path:** `backend/storage/clipforge_data/models/audio_visual/light_asd.onnx`
- **Target ONNX Size:** 4,105,904 bytes (~4.11 MB)
- **Target ONNX SHA-256:** `3ac4cd7810993cdf6ca05243730b6dff104fa20dd572fbbebc1535ac28b453dd`
- **Target ONNX Opset:** 14 (compatible with ONNX Runtime 1.32.0 CPU)

### 2.2 Multi-Tier Licensing & IP Compliance
- **Code License:** MIT License (per `LICENSE` in repository root)
- **Model Weights License:** MIT License (released by authors under MIT in repository)
- **Dataset Terms:** AVA-ActiveSpeaker & TalkSet. Academic and research benchmark dataset. Commercial distribution applies to the trained mathematical parameter matrices only (no raw video media is bundled or redistributed).
- **Attribution Requirement:**
  ```bibtex
  @InProceedings{Liao_2023_CVPR,
      author    = {Liao, Junhua and Duan, Haihan and Feng, Kanghui and Zhao, Wanbing and Yang, Yanbing and Chen, Liangyin},
      title     = {A Light Weight Model for Active Speaker Detection},
      booktitle = {Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)},
      month     = {June},
      year      = {2023},
      pages     = {22932-22941}
  }
  ```

### 2.3 Tensor Contract & Specifications
- **Input Tensors:**
  1. `audio_features`:
     - Shape: `[Batch, Temporal_Audio_Steps, 13]` where $\text{Temporal\_Audio\_Steps} = T_v \times 4$
     - Data Type: `float32`
     - Features: 13-dimensional MFCCs extracted at 16 kHz sample rate, window length 25 ms (400 samples), window step 10 ms (160 samples -> 100 Hz frame rate).
  2. `visual_features`:
     - Shape: `[Batch, Temporal_Frames, 112, 112]` (Grayscale face crops)
     - Data Type: `float32`
     - Preprocessing: BGR face crop converted to grayscale, resized to $224 \times 224$, center-cropped to $112 \times 112$, normalized by:
       $$x_{\text{norm}} = \frac{x / 255.0 - 0.4161}{0.1688}$$
- **Output Tensor:**
  - `scores`:
     - Shape: `[Batch * Temporal_Frames, 2]` (or `[Batch, Temporal_Frames, 2]`)
     - Logits corresponding to `[not_speaking, speaking]`.
     - Raw speaking logit: $L_{\text{speak}} = \text{scores}[:, 1]$.
     - Calibrated speaking probability: $P_{\text{speak}} = \text{Softmax}(\text{scores})[:, 1]$.
     - Classification threshold: $P_{\text{speak}} \ge 0.50$ (or $L_{\text{speak}} \ge 0.0$).
- **Internal Architecture:**
  - Visual Frontend: 2D Spatial Convolutions + 1D Temporal Convolutions (decoupled 2D-3D).
  - Audio Frontend: 2D Convolutions on $(13 \times 4 T_v)$ MFCC map.
  - Cross-Modal Fusion: Summation + Bidirectional GRU (128-dim hidden states) + Linear classification head ($128 \to 2$).
- **Parity & Tolerance Verification:**
  - Expected maximum absolute divergence between PyTorch forward pass and ONNX Runtime CPU: $|\Delta P| < 1.0 \times 10^{-4}$.

---

## 3. Storage Directory Layout

```
backend/storage/clipforge_data/models/
├── audio/
│   └── 3dspeaker_speech_campplus_sv_en_voxceleb_16k.onnx   (Phase 8 Stage 3 - 29.6 MB)
├── audio_visual/
│   └── light_asd.onnx                                      (Phase 8 Stage 4 - 4.2 MB)
└── vision/
    ├── face_detection_yunet_2023mar.onnx                   (Phase 6 - 232 KB)
    └── face_landmarks.onnx                                 (Phase 8 Stage 4 - 4.92 MB)
```
