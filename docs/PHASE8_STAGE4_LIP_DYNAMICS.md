# CLIPFORGE AI — PHASE 8, STAGE 4
# LIP GEOMETRY & TEMPORAL DYNAMICS SPECIFICATION

## 1. Overview & Biomechanical Background

Speech articulation involves rapid, coordinated movements of the lips, tongue, and mandible.
In facial video analysis, vertical mandibular depression (inter-lip distance) provides the primary visible signal of acoustic speech.

Previous approaches relying on 5-point face landmarks (such as OpenCV YuNet) fail because they only output the two horizontal mouth corners and the nose tip. Distance from nose to mouth corner midpoint changes during head nods, smiling, and chewing, producing false positives.

ClipForge AI utilizes **Google MediaPipe Face Mesh V2 ONNX (478 3D keypoints)** and the dedicated **`LipDynamicsExtractor`** (`backend/app/ai/vision/lip_dynamics.py`) to compute anatomical mouth kinematics.

---

## 2. Landmark Topology & Geometric Formulation

```
                 Outer Upper Lip (0)
               ...---"""""""""---...
            .-'   Inner Upper (13)  `-.
    Corner (61) ===================== (291) Corner
            `-.   Inner Lower (14)  .-'
               `---...........---'
                 Outer Lower Lip (17)
```

### 2.1 Landmark Indices
- **Index 13**: Midpoint of the inner upper vermilion border.
- **Index 14**: Midpoint of the inner lower vermilion border.
- **Index 61**: Left oral commissure (outer mouth corner).
- **Index 291**: Right oral commissure (outer mouth corner).
- **Index 78 & 308**: Inner mouth corners.

### 2.2 Inner-Lip Aperture
$$\text{aperture} = \|p_{13} - p_{14}\|_2 = \sqrt{(x_{13} - x_{14})^2 + (y_{13} - y_{14})^2 + (z_{13} - z_{14})^2}$$
Using the inner vermilion borders (13 and 14) measures true vocal aperture. When lips touch (bilabial plosives /p/, /b/, /m/), inner aperture drops to near zero ($< 0.005$), whereas outer borders (0 and 17) still show the thickness of the closed lips.

### 2.3 Mouth Width
$$\text{mouth\_width} = \|p_{61} - p_{291}\|_2 = \sqrt{(x_{61} - x_{291})^2 + (y_{61} - y_{291})^2 + (z_{61} - z_{291})^2}$$

### 2.4 Mouth Aspect Ratio (MAR)
$$\text{MAR} = \frac{\text{aperture}}{\max(\text{mouth\_width}, \epsilon)}, \quad \epsilon = 10^{-6}$$
Normalizing aperture by mouth width ensures scale invariance across camera distances and subject face sizes.

---

## 3. Temporal Dynamics & Signal Processing

### 3.1 Non-Uniform Temporal Velocity ($d\text{MAR}/dt$)
Because video frames may arrive at non-uniform intervals on VFR media:
$$\Delta t_k = t_k - t_{k-1}$$
$$\text{velocity}(t_k) = \frac{|\text{MAR}(t_k) - \text{MAR}(t_{k-1})|}{\max(\Delta t_k, 10^{-4})}$$
- **Speech**: Rapid alternation between open visemes and closed visemes produces sustained velocities in the range of $[2.0, 10.0]\text{ s}^{-1}$.
- **Static Open Mouth**: High MAR ($> 0.40$), but near-zero velocity ($< 0.5\text{ s}^{-1}$).
- **Closed Mouth / Listening**: Low MAR ($< 0.05$) and near-zero velocity.

### 3.2 Exponential Moving Average (EMA) Smoothing
To prevent high-frequency landmark regressor jitter from introducing noise:
$$\text{MAR}_{\text{smooth}}(t_k) = \alpha \cdot \text{MAR}(t_k) + (1 - \alpha) \cdot \text{MAR}_{\text{smooth}}(t_{k-1})$$
Default $\alpha = 0.35$. Raw measurements ($\text{mar\_raw}$) are always preserved alongside smoothed measurements ($\text{mar\_smooth}$).

### 3.3 Short-Window Variance
Computed over a sliding window of duration $W = 0.40\text{s}$:
$$\text{Var}(\text{MAR}) = \frac{1}{|K|} \sum_{u \in K} (\text{MAR}(u) - \mu_K)^2$$
Active speech exhibits high MAR variance ($\ge 0.002$), while smiling or yawns exhibit low variance over short windows.

### 3.4 Robustness Rules:
1. **Occlusion Gap Reset**: If $\Delta t_k > 0.50\text{s}$ (face temporarily turned away or lost), the temporal state is cleared so that the next re-acquisition does not trigger a false velocity spike across the gap.
2. **Jitter Clamping**: If $|\text{MAR}(t_k) - \text{MAR}(t_{k-1})| > 0.45$ in $\Delta t < 0.05\text{s}$, the instantaneous shift is clamped to prevent tracking artifacts.
3. **Plausibility Bounds**: Any raw MAR $> 1.80$ is rejected as non-anatomical.

---

## 4. Fundamental Rule: Why MAR Alone is NOT Proof of Speech

A fundamental principle in Audio-Visual Machine Learning is that **visual lip motion alone cannot confirm speech**:
1. **Chewing & Eating**: Produces large rhythmic vertical openings and closures indistinguishable from speech in pure geometry.
2. **Smiling & Laughter**: Expands mouth width and can cause moderate aperture variation without vocalization.
3. **Yawning**: Generates extreme MAR ($> 0.80$) that stays open for several seconds.
4. **Silent Articulation / Mouth Breathing**: Person moves lips or breathes heavily without phonation.

**Solution**:
Lip dynamics serves as **Kinematic Motion Evidence** within the multimodal fusion engine. It is cross-referenced with:
- **Silero VAD Speech Intervals** (acoustic phonation gating).
- **Light-ASD Audio-Visual Correlation** (cross-modal viseme-phoneme mutual information).

---

## 5. Performance Profile

Measured on Intel Core i7-13620H (CPU):
- **MediaPipe Face Mesh V2 ONNX**: 22.17 ms per face crop.
- **Lip Dynamics Extraction**: 96.59 microseconds per observation.
- **Memory Footprint**: $< 1.0\text{ MB}$ state cache across dozens of tracks.
