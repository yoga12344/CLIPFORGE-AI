# Phase 9 Stage 3: Timeline Synchronization Specification

## 1. Timeline Synchronization & PTS Management
When reframing, cutting, or burning subtitles across multiple clips:
- Audio and video timestamps must maintain strict alignment to avoid audio-video drift.
- `VideoTrimNode` pairs `trim=start=X:end=Y` with `setpts=PTS-STARTPTS` to reset presentation timestamps to 0.
- `AudioTrimNode` pairs `atrim=start=X:end=Y` with `asetpts=PTS-STARTPTS` to reset audio presentation timestamps synchronously.

---

## 2. Quantization & Cadence
- Video frames are normalized to 30.0 fps (or delivery target) via `fps=fps=30.0` or CFR mode.
- Subtitle ASS events are quantized to 10ms (centisecond resolution) matching ASS format specifications.
- `SynchronizationValidator` inspects generated files using FFprobe packet streams to ensure audio/video delta $|t_{video} - t_{audio}| < 40\text{ms}$ (less than 1.2 video frames at 30fps).
