# Phase 9 Stage 8: Audio Mixing & Professional Finishing

## Overview
Phase 9 Stage 8 implements multi-track audio mixing, dynamic voice-activated sidechain ducking, high-pass filtering, and EBU R128 broadcast loudness mastering for ClipForge AI. High quality, balanced audio is critical for short-form retention: background music must never overpower vocal dialogue, low-end rumble must be eliminated, and overall loudness must comply with platform distribution standards (-14 LUFS for YouTube Shorts, TikTok, and Instagram Reels).

---

## 1. Core Architecture & Modules

The audio mixing and mastering system operates through three primary layers:

### A. Audio Mixer Planner & Math (`audio_mixer.py`)
- **Decibel & Linear Converters**: High-precision conversions between human-facing decibels (`gain_db`) and FFmpeg linear amplitude multipliers (`db_to_linear`).
- **Dynamic Ducking Calculation**: Translates `AudioDuckingConfig` into standard FFmpeg `sidechaincompress` filter parameters:
  - Attack: typically 50ms for responsive attenuation when dialogue begins.
  - Release: 300–350ms for natural recovery during speech pauses.
  - Ratio: $4:1$ to $5:1$ sidechain compression ratio.
  - Threshold: linear conversion of user-configured threshold in dB (e.g. -24 dBFS $\rightarrow \approx 0.063$).

### B. Broadcast Loudness Standards (`loudness_master.py`)
- Preconfigured mastering targets conforming to ITU-R BS.1770-4 and EBU R128:
  - `youtube_shorts`: -14.0 LUFS integrated loudness, -1.0 dBTP true-peak, 7.0 LU loudness range (LRA).
  - `tiktok`: -14.0 LUFS, -1.0 dBTP, 7.0 LRA.
  - `instagram_reels`: -14.0 LUFS, -1.0 dBTP, 7.0 LRA.
  - `podcast`: -16.0 LUFS, -1.0 dBTP, 8.0 LRA.
  - `broadcast_tv`: -23.0 LUFS, -1.0 dBTP, 10.0 LRA.

### C. Render Graph Audio Pipeline (`nodes.py`, `filter_compiler.py`, `graph_builder.py`)
- **First-Class Audio Filter Nodes**:
  - `HighPassFilterNode` (`highpass=f=80`): Cleans up low-frequency mechanical rumble below 80 Hz on dialogue.
  - `ASplitNode` (`asplit=2`): Clones dialogue signal into a sidechain trigger stream and a main mix stream without re-encoding or duplicating files.
  - `SidechainCompressNode` (`sidechaincompress=threshold=...:ratio=...:attack=...:release=...`): Dynamically attenuates background music when dialogue energy triggers the compressor.
  - `AudioMixNode` (`amix=inputs=2:duration=first:dropout_transition=2`): Sums dialogue and background music into a single composite stream.
  - `LoudnessNormalizeNode` (`loudnorm=I=-14.0:TP=-1.0:LRA=7.0`): Performs broadcast normalization and peak limiting.

---

## 2. Test Verification Summary

Full test coverage in `backend/tests/test_phase9_stage8.py`:
- `test_decibel_linear_conversions`: Exact dB to linear and linear to dB mathematical checks.
- `test_ducking_parameters_calculation`: Threshold dB mapping and attack/release parameter integrity.
- `test_platform_loudness_presets`: Target loudness definitions for YouTube, TikTok, and podcasts.
- `test_audio_filter_nodes_compilation`: Validates filter syntax for `amix`, `sidechaincompress`, `highpass`, and `loudnorm`.
- `test_real_ffmpeg_rendering_with_voice_and_music_ducking`: Real FFmpeg execution mixing voice dialogue with background music via dynamic sidechain ducking.
- `test_real_ffmpeg_rendering_with_loudness_mastering`: Real FFmpeg execution validating EBU R128 loudness mastering and 48 kHz stereo output via `OutputValidator`.
