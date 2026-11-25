# ClipForge AI — Audio Preprocessing Engine Architecture

## 1. Overview
The Audio Preprocessing Engine (`backend/app/ai/audio/audio_preprocessor.py`) is a core component of ClipForge AI's local audio intelligence pipeline. It ensures that input video and audio files are safely inspected, measured for acoustic health, and resampled into the standardized canonical audio format required by speech understanding engines (Whisper, Silero VAD, PyAnnote diarization, and multimodal active-speaker detectors).

---

## 2. Audio Standards & Canonical Formats

### Speech Inference Canonical Format
All downstream speech and voice models require uniform input:
- **Sample Rate**: `16,000 Hz` (16 kHz).
- **Channels**: `1` (Mono channel, downmixed from stereo/multi-channel using arithmetic mean).
- **Format**: `pcm_s16le` (16-bit uncompressed linear PCM).
- **In-Memory Representation**: 1D `numpy.float32` array normalized strictly to $[-1.0, 1.0]$.

### Master Audio Preservation
- The user's original imported media files are **never modified, re-encoded, or overwritten**.
- All extracted and preprocessed audio tracks are saved inside isolated, project-scoped cache directories:
  `storage/clipforge_data/projects/{project_id}/audio/{video_id}_16k.wav`

---

## 3. Signal Health & Quality Metrics

Before and during processing, the engine computes key audio quality metrics:

1. **Peak Amplitude**: $\max(|x|)$ over the signal window.
2. **RMS Level (Root Mean Square)**: $\sqrt{\frac{1}{N}\sum_{i=1}^{N} x_i^2}$, representing perceived audio power.
3. **Silence Detection**:
   $$\text{RMS} < 10^{-4} \quad \text{or} \quad \text{Peak} < 10^{-5}$$
   Triggering early rejection for silent tracks or missing microphones.
4. **Clipping Detection**:
   $$\text{Peak} \ge 0.999$$
   Flags digital distortion and potential acoustic saturation.

---

## 4. Chunked Streaming & Memory Boundedness

To support long multi-hour videos without out-of-memory (OOM) failures or excessive RAM footprint:
- **Chunk Duration**: Default 30.0 seconds.
- **Overlap**: Default 1.0 second.
- **Streaming Implementation**: `AudioPreprocessor.stream_wav_chunks` streams audio frames directly from disk using standard `wave` seek pointers without loading the entire multi-gigabyte recording into memory.
- **Peak RAM Usage**: Bounded to $< 60\text{ MB}$ regardless of audio file duration.

---

## 5. Security & Isolation
- All FFmpeg subprocess operations use sanitized argument lists without `shell=True`.
- Strict path validation ensures files reside within recognized system or project storage boundaries.
