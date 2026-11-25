# ClipForge AI — Final Known Limitations & Edge Cases
**Release:** 1.0.0-GA  
**Date:** November 23, 2026  

---

## 1. Documented Operational Boundaries

ClipForge AI is engineered as an offline-first, local workstation tool. The following documented boundaries and behaviors apply to Release 1.0:

### 1.1 Local Hardware Requirements
* **Minimum RAM:** 8 GB RAM (16 GB strongly recommended for concurrent AI diarization and 4K video transcoding).
* **GPU Acceleration:** NVIDIA NVENC requires an NVIDIA GPU with driver version 522.25 or newer. Systems without NVIDIA hardware automatically fall back to CPU encoding (`libx264`) with CRF 21, which produces visually identical output at lower rendering speed.
* **Disk Space:** High-speed SSD recommended. Rendering 1080p60 clips requires temporary scratch space roughly 2x the source video size during multi-pass loudness mastering.

### 1.2 Video Source Constraints
* **Extreme Low-Light / Severe Motion Blur:** In extreme low-light environments (lux < 5) or violent camera shake, facial landmark confidence may drop below 0.35. The system automatically falls back to centered conversational reframing with smoothed trajectory interpolation.
* **Multi-Speaker Crosstalk:** When two speakers talk simultaneously at identical volumes for longer than 3 seconds, the diarization confidence is tagged as `overlapping`. The multi-person layout engine automatically selects `split_vertical` to keep both visible rather than toggling erratically.
* **Corrupted or Truncated MP4s:** Source videos missing the `moov` atom or corrupted by interrupted camera recording must be repaired before import.

### 1.3 Offline AI Models
* **Initial Model Cache:** Faster-Whisper base and speech models are cached locally. If higher parameter models (e.g., Whisper Large-v3 or 7B LLMs) are desired by the user, they can be placed into `backend/models/` or fetched through the AI Models page.

---

## 2. Mitigations & Defensive Architecture

* All limitations fail safely: when an advanced feature encounters edge conditions, the engine degrades gracefully to standard reframing or stereo pass-through rather than crashing the rendering pipeline.
