# Phase 9 Stage 2: Canonical Timeline and Timebase Specification

## 1. The Microsecond Principle

In multi-track video editing systems, representing timestamps and durations as floating-point seconds (e.g. `12.345678`) introduces IEEE 754 floating-point rounding errors. Over long videos (e.g. 60+ minutes) and multi-clip concatenations, these tiny rounding errors compound into audio-video desynchronization, dropped frames, or sub-frame jitter.

To guarantee zero drift and deterministic reproducibility across platforms and rendering backends, ClipForge AI adheres to the **Canonical Microsecond Standard**:
- **Base Unit**: All timeline boundaries, clip in/out points, keyframes, transitions, and subtitle word timings are stored as **integer microseconds** (`us`, $\mu\text{s}$).
- **Precision**: 1 microsecond = $10^{-6}$ seconds ($1 \text{ s} = 1,000,000\ \mu\text{s}$).
- **Integer Range**: A standard 64-bit integer microsecond can represent over 292,000 years without overflow.
- **Conversion**: Floating-point seconds are only exposed as derived read-only helper properties (`start_seconds`, `end_seconds`, `duration_seconds`) for user-facing UI displays.

---

## 2. Rational Timebase Representation

Broadcast and digital video formats frequently use non-integer frame rates:
- NTSC Color: $29.97002997\dots \text{ fps} = \frac{30000}{1001}$
- NTSC Film: $23.97602397\dots \text{ fps} = \frac{24000}{1001}$
- NTSC High Frame Rate: $59.94005994\dots \text{ fps} = \frac{60000}{1001}$

Approximating $\frac{30000}{1001}$ as `29.97` leads to an error of 1 frame every ~1000 frames (~33.3 seconds).

`CompositionSpec` implements exact fractional math via `RationalTimebase`:
```python
class RationalTimebase(BaseModel):
    numerator: int = Field(..., gt=0)
    denominator: int = Field(default=1, gt=0)

    @property
    def fps(self) -> float:
        return self.numerator / self.denominator

    @property
    def frame_duration_us(self) -> int:
        return round(1_000_000 * self.denominator / self.numerator)
```

### Predefined Standard Timebases
| Preset Name | Numerator | Denominator | Nominal FPS | Microseconds per Frame |
| :--- | :--- | :--- | :--- | :--- |
| **23.976 fps** | 24000 | 1001 | 23.976 | 41,708 $\mu\text{s}$ |
| **24.0 fps** | 24 | 1 | 24.000 | 41,667 $\mu\text{s}$ |
| **25.0 fps (PAL)** | 25 | 1 | 25.000 | 40,000 $\mu\text{s}$ |
| **29.97 fps (NTSC)**| 30000 | 1001 | 29.970 | 33,367 $\mu\text{s}$ |
| **30.0 fps** | 30 | 1 | 30.000 | 33,333 $\mu\text{s}$ |
| **50.0 fps** | 50 | 1 | 50.000 | 20,000 $\mu\text{s}$ |
| **59.94 fps** | 60000 | 1001 | 59.940 | 16,683 $\mu\text{s}$ |
| **60.0 fps** | 60 | 1 | 60.000 | 16,667 $\mu\text{s}$ |

---

## 3. Coordinate System Spaces & Conversions

`TimelineSpec` manages three distinct coordinate spaces:

```
[Source Media Coordinates: 0 to Source Duration]
      |
      v  ClipBoundary(in_point_us, out_point_us)
[Composition Timeline Coordinates: 0 to Composition Duration]
      |
      v  Speed Factor (e.g. 1.0x, 1.2x)
[Rendered Output Coordinates: 0 to Output Duration]
```

### 3.1 Mathematical Conversion Formulas

#### Source to Composition
Given a timestamp in source media coordinates $t_{\text{source}}$, its position in the composition timeline $t_{\text{comp}}$ is:
$$t_{\text{comp}} = t_{\text{source}} - t_{\text{in\_point}}$$

Clamped to the valid composition range:
$$0 \le t_{\text{comp}} \le (t_{\text{out\_point}} - t_{\text{in\_point}})$$

#### Composition to Source
Given a timestamp in composition coordinates $t_{\text{comp}}$, its position in source media $t_{\text{source}}$ is:
$$t_{\text{source}} = t_{\text{in\_point}} + t_{\text{comp}}$$

#### Composition to Rendered Output (Speed Alterations)
When playback speed adjustment factor $S$ is applied ($S > 0$):
$$t_{\text{output}} = \text{round}\left(\frac{t_{\text{comp}}}{S}\right)$$

---

## 4. Clip Boundaries and Transitions

### 4.1 Boundary Invariants
For any `ClipBoundary(in_point_us, out_point_us)`:
1. $t_{\text{in\_point}} \ge 0$
2. $t_{\text{out\_point}} > t_{\text{in\_point}}$
3. $D_{\text{duration}} = t_{\text{out\_point}} - t_{\text{in\_point}}$

### 4.2 Scene Boundaries & Transition Overlaps
A composition may define multi-scene segments (`TimelineSceneBoundary`) connected by `TimelineTransition`:
- Transition types: `cut`, `crossfade`, `dissolve`, `wipe_left`, `wipe_right`, `dip_to_black`.
- Transition duration: `duration_us` (typically 250,000 to 500,000 $\mu\text{s}$).
- The transition center point (`center_timestamp_us`) aligns the outgoing scene fade-out with incoming scene fade-in.
