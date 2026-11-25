# ClipForge AI — Phase 7 & Active Speaker Detection Roadmap

## 1. Overview

With Phase 6 providing multi-face tracking and smooth camera reframing, this roadmap outlines how Active Speaker Detection, Animated Subtitles (Karaoke word-level styling), and Non-Destructive Video Composition (EDL) integrate in Phase 7.

---

## 2. Active Speaker Detection Architecture

In multi-person interview or podcast footage, camera reframing should dynamically cut or pan to whoever is speaking at any given moment.

### 2.1 Multi-Modal Fusion Strategy
1. **Audio Energy & Voice Activity (Phase 4 Whisper timestamps):**
   - Align segment and word timestamps to temporal intervals.
2. **Visual Lip Motion & Landmark Dynamics (Phase 6 YuNet landmarks):**
   - YuNet outputs 5 landmarks: right mouth corner, left mouth corner, nose, eyes.
   - Compute vertical mouth opening distance:
     $$D_{\text{mouth}}(t) = |y_{\text{mouth\_bottom}} - y_{\text{mouth\_top}}|$$
   - Cross-correlate mouth movement frequency with audio speech energy peaks.
3. **Active Speaker Confidence:**
   $$S_{\text{active}}(t) = w_a \cdot \text{VAD}(t) + w_v \cdot \Delta D_{\text{mouth}}(t)$$
4. **Dynamic Cut Decisions:**
   - Add a hysteresis delay (e.g. 1.2 seconds) to avoid rapid ping-pong switching between speakers during brief interjections.

---

## 3. Phase 7 Scope: Subtitles, Styling & EDL Composition

1. **SubRip & Advanced SubStation Alpha (ASS) Engine:**
   - Word-level karaoke animation tags (`{\k...}`).
   - Custom styling presets: Yellow pop, bold stroke, TikTok bounce, gradient fills.
2. **Interactive Subtitle Editor in React:**
   - Click-to-edit word text and timings.
   - Splitting and merging caption lines.
3. **Final Rendering Pipeline:**
   - FFmpeg `subtitles` / `ass` filter integration with hardware-accelerated or libx264 encoding.
   - Non-destructive EDL persistence in SQLite.
