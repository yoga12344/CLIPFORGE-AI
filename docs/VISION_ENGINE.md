# ClipForge AI — Vision Engine Documentation

## 1. Overview

The Vision Engine is ClipForge AI's local-first computer vision and reframing subsystem. It provides automated detection of human faces, multi-face tracking over time, scene density classification, intelligent subject selection, camera trajectory calculation, and dynamic FFmpeg crop rendering.

---

## 2. Architecture & Pipeline

```
Raw Video File (.mp4 / .mov / .mkv)
   │
   ▼
[Video Frame Sampler] (cv2.VideoCapture @ 4.0 fps downscaled to 640px)
   │
   ▼
[Face Detector]
   ├── YuNetFaceDetector (OpenCV DNN ONNX, 232 KB, 5 facial landmarks)
   └── HaarCascadeFaceDetector (Offline built-in fallback)
   │
   ▼
[Spatial-Temporal Face Tracker] (IoU + Centroid distance matching, 1.5s occlusion tolerance)
   │
   ├── Track 1 (Subject A, samples, bbox trajectory)
   └── Track 2 (Subject B, samples, bbox trajectory)
   │
   ▼
[Scene Analyzer]
   ├── Density metrics (frames with faces, max simultaneous)
   └── Classification (single_subject, multi_person, crowd, b_roll)
   │
   ▼
[Subject Selector]
   ├── largest_face (dominant / closest speaker)
   ├── center_face (center-stage subject)
   ├── manual_track (locked to specific track ID)
   └── group (union bounding box encompassing all subjects)
   │
   ▼
[Reframe Engine]
   ├── Aspect ratio geometry (9:16, 1:1, 4:5, 16:9)
   ├── Headroom margin (10-25% space above forehead)
   ├── Exponential Moving Average (EMA) smoothing
   ├── Maximum velocity clamping (e.g. 0.50 normalized shift / sec)
   ├── Hard boundary clamping [0 <= x <= W - crop_w]
   └── Manual keyframe override merge
   │
   ▼
[FFmpeg Filtergraph Builder]
   └── Dynamic piecewise linear crop expression `crop=w:h:'if(...)':scale=1080:1920`
```

---

## 3. Mathematical Specifications

### 3.1 Intersection-over-Union (IoU)
$$\text{IoU}(A, B) = \frac{\text{Area}(A \cap B)}{\text{Area}(A \cup B)}$$
Boxes are matched when $\text{IoU} \ge 0.25$ or normalized centroid Euclidean distance $\le 0.25$.

### 3.2 Target Crop Dimensions
For target aspect ratio $r = \frac{W_t}{H_t}$ and source dimensions $W_s \times H_s$:
If $r \le \frac{W_s}{H_s}$ (e.g. 9:16 in 16:9 landscape):
$$\text{CropHeight} = H_s$$
$$\text{CropWidth} = 2 \times \lfloor \frac{H_s \times r}{2} \rfloor \quad (\text{even pixel guarantee})$$

### 3.3 Temporal Smoothing & Velocity Clamping
For target ideal coordinate $x_{\text{target}}$ and previous smoothed coordinate $x_{t-1}$:
1. **Raw Exponential Moving Average:**
   $$\tilde{x}_t = \alpha \cdot x_{t-1} + (1 - \alpha) \cdot x_{\text{target}}$$
2. **Velocity Clamp:**
   $$\Delta_{\text{max}} = v_{\text{max}} \cdot \Delta t$$
   $$x_t = x_{t-1} + \text{clamp}(\tilde{x}_t - x_{t-1}, -\Delta_{\text{max}}, \Delta_{\text{max}})$$
3. **Hard Frame Clamping:**
   $$x_t = \max(0.0, \min(1.0 - \text{crop\_norm\_w}, x_t))$$

---

## 4. Database Entities

- `VisionAnalysis`: Stores analysis run metadata, sampling rate, total frames, and scene composition JSON.
- `FaceTrack`: Stores individual subject tracks with start/end timestamps, detection count, average bounding box, and temporal samples.
- `ManualCropCorrection`: Stores user keyframe overrides at specific timestamps.
- `ReframePreset`: Stores reusable reframing configurations.

---

## 5. Resource Safety & Concurrency

- **Sequential Lock:** `VisionManager` executes within an `asyncio.Lock()`.
- **Memory Management:** Video frame buffers are freed immediately after detection. Only lightweight normalized coordinates are persisted.
- **Cancellation:** Video capture loop checks `cancel_token.is_cancelled` on every sampled frame and terminates cleanly without leaking file descriptors.
