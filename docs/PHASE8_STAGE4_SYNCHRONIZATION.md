# CLIPFORGE AI — PHASE 8, STAGE 4
# AUDIO-VISUAL TEMPORAL SYNCHRONIZATION SPECIFICATION

## 1. Overview & Problem Definition

In desktop video processing, synchronization between video frames and audio samples is subject to several timing challenges:
1. **Variable Frame Rate (VFR)**: Mobile recordings (iOS/Android), screen captures (OBS), and video conferencing tools (Zoom, Teams) often record frames with non-uniform intervals. Calculating time as $t = \frac{\text{frame\_index}}{\text{nominal\_fps}}$ causes cumulative temporal drift of up to several hundred milliseconds over a few minutes.
2. **Audio/Video Stream Offsets**: Containers (MP4, MKV) frequently define non-zero stream start times (`start_time`), or the audio stream starts slightly before or after the first video keyframe.
3. **Cross-Modal Windowing**: Deep active speaker models (such as Light-ASD) correlate lip articulation visemes with acoustic phonemes over temporal contexts of 0.4s to 1.0s. Any temporal misalignment exceeding 40 ms ($1\text{ frame}$ at 25 FPS) degrades cross-modal correlation accuracy.

ClipForge AI implements an explicit, drift-free synchronization engine in `backend/app/ai/audio_visual/av_synchronizer.py`.

---

## 2. Synchronization Architecture

```mermaid
flowchart TD
    VideoFile[Source Video Container] -->|Container PTS Decoding| FramePTS[Decoded Video PTS t_pts]
    VideoFile -->|FFmpeg async=1:first_pts=0| Audio16k[Canonical 16 kHz Mono PCM]

    StreamInfo[StreamSyncInfo: relative_offset] --> SyncEngine[AudioVisualSynchronizer]
    FramePTS --> SyncEngine
    Audio16k --> SyncEngine

    SyncEngine -->|Audio time = t_pts - relative_offset| CenterAudio[Aligned Audio Center]
    CenterAudio -->|Window [t - W/2, t + W/2]| SlicedAudio[Synchronized 6,400-Sample Audio Buffer]
    
    SlicedAudio --> Model[Light-ASD Cross-Modal Model]
```

### 2.1 The Canonical Audio Timeline
During Phase 8 Stage 2, `AudioPreprocessor` extracts a single persistent 16 kHz mono WAV cache aligned strictly to video presentation start time via FFmpeg:
```bash
ffmpeg -y -i <source> -vn -ac 1 -ar 16000 -c:a pcm_s16le \
  -af "aresample=async=1:first_pts=0" <canonical_output.wav>
```
- `aresample=async=1:first_pts=0`: Stretches, squeezes, or pads initial audio packets to guarantee that audio sample index $0$ corresponds exactly to container presentation timestamp $t = 0.000\text{s}$.
- Every audio sample $n$ maps directly to timestamp $t = \frac{n}{16000.0}$ seconds.

### 2.2 Relative Stream Start Offsets
If container inspection reveals that the audio stream starts with an offset relative to video:
$$\Delta t_{\text{offset}} = t_{\text{audio\_start}} - t_{\text{video\_start}}$$
The mapping from video frame timestamp $t_{\text{video}}$ to audio sample time $t_{\text{audio}}$ is:
$$t_{\text{audio}} = t_{\text{video}} - \Delta t_{\text{offset}}$$

- **Positive Offset ($\Delta t_{\text{offset}} > 0$)**: Audio begins after video starts. Video frames prior to the audio start are zero-padded on the left side of the temporal window.
- **Negative Offset ($\Delta t_{\text{offset}} < 0$)**: Audio begins before video starts.

---

## 3. Audio Window Extraction Contract

Given:
- Center video presentation timestamp $t_{\text{video}}$ (seconds)
- Window duration $W = 0.40\text{s}$ (default)
- Sample rate $F_s = 16000\text{ Hz}$
- Target sample count $N = \text{round}(W \times F_s) = 6400\text{ samples}$

### 3.1 Window Boundaries
$$t_{\text{start}} = t_{\text{audio}} - \frac{W}{2}$$
$$i_{\text{start}} = \text{round}(t_{\text{start}} \times F_s)$$
$$i_{\text{end}} = i_{\text{start}} + N$$

### 3.2 Boundary Padding Algorithm
Let $L$ be the total length of the available audio buffer:
1. `buf_start = max(0, i_start)`
2. `buf_end = min(L, i_end)`
3. `pad_left = max(0, -i_start)`
4. `pad_right = max(0, i_end - L)`

If `pad_left > 0` or `pad_right > 0`:
$$\text{Window} = \left[ \mathbf{0}_{\text{pad\_left}} \,\|\, \text{Audio}[\text{buf\_start}:\text{buf\_end}] \,\|\, \mathbf{0}_{\text{pad\_right}} \right]$$

### 3.3 Synchronization Confidence Metric
The synchronizer outputs a confidence score based on the fraction of unpadded audio samples in the requested window:
$$C_{\text{sync}} = \frac{\text{buf\_end} - \text{buf\_start}}{N} \in [0.0, 1.0]$$
- $C_{\text{sync}} = 1.0$: Fully valid, unpadded audio.
- $C_{\text{sync}} < 0.50$: Window lies mostly outside the audio stream (e.g. extreme start or end of video). Downstream fusion down-weights active speaker confidence proportionally.

---

## 4. Automated Test Verification

The synchronization engine is covered by automated unit tests in `backend/tests/test_phase8_stage4.py`:
1. `test_av_sync_constant_frame_rate`: Validates symmetric center alignment on CFR video ($C_{\text{sync}} = 1.0$).
2. `test_av_sync_variable_frame_rate`: Validates extraction across non-uniform VFR timestamp sequences.
3. `test_av_sync_positive_audio_offset`: Confirms left-padding when audio stream begins after video start.
4. `test_av_sync_negative_audio_offset`: Confirms correct advance into audio buffer when audio precedes video.
5. `test_av_sync_boundary_padding`: Verifies zero-padding at $t=0.0\text{s}$ and $t=T_{\text{end}}$.
6. `test_av_sync_missing_audio`: Verifies graceful zero-waveform output and $C_{\text{sync}} = 0.0$ when audio is absent.
