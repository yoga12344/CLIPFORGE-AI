# Phase 9 Stage 3: Output Validation Specification

## 1. Multi-Tier Verification Strategy
The `OutputValidator` and `RenderValidator` verify rendered artifacts prior to marking a job completed:

1. **Existence & Non-Zero File Size**: Artifact must exist and size must exceed minimum threshold (e.g. > 10 KB).
2. **FFprobe Stream Probing**:
   - Video stream must exist and decode without container corruption.
   - Dimensions must match target delivery profile (e.g., 1080x1920 for 9:16 portrait).
   - Video codec must match specification (`h264`).
   - Frame rate must match target ($\pm 0.5$ fps tolerance).
   - Duration must match expected composition timeline within $\pm 100\text{ms}$.
   - Pixel format must match `yuv420p` for broad hardware and web compatibility.
3. **Audio Stream Probing**:
   - Sample rate must match delivery profile (e.g. 48,000 Hz).
   - Audio channels must match delivery profile (e.g. 2 channels stereo).
   - Audio duration must match video duration within 100ms.
4. **FastStart Verification**:
   - `moov` atom must precede `mdat` atom (`-movflags +faststart`) to allow immediate progressive web streaming.
