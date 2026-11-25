# Phase 9 Stage 4: Speaker-Aware Reframing Specification

## 1. Geometric Aspect Ratio Normalization
When cropping a 16:9 widescreen video (e.g., $1920 \times 1080$) to vertical 9:16 ($1080 \times 1920$):
$$\frac{w_{px}}{h_{px}} = \frac{w_{norm} \cdot W_{src}}{h_{norm} \cdot H_{src}} = \frac{9}{16}$$
$$w_{norm} = h_{norm} \cdot \frac{9}{16} \cdot \frac{H_{src}}{W_{src}}$$
For $1920 \times 1080$:
$$w_{norm} = h_{norm} \cdot \frac{9}{16} \cdot \frac{1080}{1920} = h_{norm} \cdot \frac{81}{256} \approx 0.316406 \cdot h_{norm}$$

### Headroom Positioning
Face center $(c_x, c_y)$ is placed around 35% from the top of the crop rectangle:
- $x = \text{clamp}(c_x - w_{norm} / 2.0, 0.0, 1.0 - w_{norm})$
- $y = \text{clamp}(c_y - 0.35 \cdot h_{norm}, 0.0, 1.0 - h_{norm})$

---

## 2. Temporal Smoothing & Hold Durations
- **Velocity Clamping**: Maximum shift per second is bounded at $v_{max} = 0.40$ normalized screen widths per second, preventing rapid, motion-sickness-inducing camera pans.
- **Exponential Moving Average**: Coordinates are filtered with $\alpha = 0.15$ smoothing.
- **Cut Transitions**: When speaker identity changes or a dialogue turn occurs, an instant cut (`interpolation_mode="cut"`) is emitted instead of a continuous pan.
- **Hold Duration**: If speaker turns alternate rapidly ($< 1.2\text{s}$), the shot selector holds framing on the current subject unless an explicit dialogue turn occurs.
