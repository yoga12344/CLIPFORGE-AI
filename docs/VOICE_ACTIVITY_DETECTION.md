# ClipForge AI — Voice Activity Detection (VAD) Engine

## 1. Overview
The Voice Activity Detection Engine (`backend/app/ai/audio/voice_activity_detector.py`) provides millisecond-accurate detection of human speech activity in video and audio files. Built entirely for local, privacy-first desktop operation, it runs without requiring network access, paid cloud APIs, or specialized GPU acceleration.

---

## 2. Core Architecture & Local Model
- **Model**: Silero VAD v4 (`faster_whisper.vad.SileroVADModel`).
- **Engine**: ONNX Runtime (CPU-optimized with thread pooling).
- **Format Requirement**: 16,000 Hz, single channel (mono), 16-bit PCM / float32 $[-1.0, 1.0]$.
- **Execution Speed**: Real-Time Factor (RTF) $\approx 0.013\times$ (approx. $78\times$ faster than real-time playback on an Intel Core i7-13620H CPU).

---

## 3. Configuration & Tuning Parameters

Configured via `VADConfigSchema`:
- `threshold`: Speech probability threshold ($0.1$ to $0.95$, default $0.5$).
- `min_speech_duration_ms`: Minimum speech burst duration to be considered valid speech (default $250\text{ ms}$). Filters out coughs, microphone thuds, and clicks.
- `min_silence_duration_ms`: Minimum silence gap to register an utterance boundary (default $350\text{ ms}$).
- `speech_pad_ms`: Temporal padding added before start and after end of speech bursts (default $100\text{ ms}$). Prevents cutting off plosives and breath release.
- `max_merge_gap_ms`: Silence duration threshold under which consecutive speech bursts are merged into a continuous conversational interval (default $250\text{ ms}$).
- `chunk_duration_sec`: Window size for chunked streaming analysis (default $30.0\text{ s}$).
- `chunk_overlap_sec`: Boundary overlap between consecutive chunks (default $1.0\text{ s}$) to prevent speech clipping at chunk boundaries.

---

## 4. Post-Processing Pipeline
1. **Raw Timestamps**: Silero VAD returns sample index intervals $[s_i, e_i]$.
2. **Time Offset Shifting**: For streamed chunks, timestamps are shifted by chunk start time.
3. **Boundary Gap Merging**: Utterances separated by less than `max_merge_gap_ms` are joined.
4. **Speech Padding**: Padded by `speech_pad_ms` (bounded by $0.0$ and media duration).
5. **Duration Filtering**: Utterances shorter than `min_speech_duration_ms` are pruned.
6. **Persistence**: Saved as `SpeechInterval` records linked to parent `AudioAnalysis`.
