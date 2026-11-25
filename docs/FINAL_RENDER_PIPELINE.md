# ClipForge AI — Final Video Render Pipeline

## 1. Overview

The Final Render Pipeline generates production-ready, broadcast-quality short videos (e.g. 9:16 vertical $1080 \times 1920$, 1:1 square $1080 \times 1080$, 4:5 portrait $1080 \times 1350$). It fuses camera reframing trajectories (from Phase 6 Visual AI) and burned-in karaoke subtitles (from Phase 7 Subtitle Engine) in a single-pass hardware-accelerated or CPU FFmpeg filtergraph.

## 2. Pipeline Architecture

```
Source MP4 Video
      │
      ├───────────────────────┐
      ▼                       ▼
Video Stream             Audio Stream
      │                       │
      ▼                       │
Dynamic Crop Trajectory       │
(Piecewise Linear Interp)     │
      │                       │
      ▼                       │
High-Quality Scaling          │
(Bicubic to 1080x1920)        │
      │                       │
      ▼                       │
ASS Subtitle Burn-in          │
(libass with Karaoke Pop)     │
      │                       │
      ▼                       ▼
H.264 Encoder            AAC Encoder
(NVENC / libx264)        (192 kbps, 48kHz)
      │                       │
      └───────────┬───────────┘
                  ▼
          Exported MP4 Video
                  │
                  ▼
          FFprobe Validation
```

## 3. Filtergraph Assembly

The single-pass FFmpeg video filtergraph combines:
1. **Dynamic Crop**: `crop=w:h:'if(...)':'if(...)'` tracking the primary subject smoothly across time.
2. **Resolution Scale**: `scale=1080:1920:flags=bicubic`.
3. **Subtitle Burn**: `ass=filename='C\:/path/to/subtitles.ass'`.

Combined filter string:
```
-vf "crop=1080:1080:'if(...)':'if(...)',scale=1080:1920:flags=bicubic,ass=filename='C\:/Users/user/subtitles.ass'"
```

## 4. Hardware Acceleration & Encoder Selection

Capability detection evaluates GPU availability:
- **NVIDIA GPU NVENC (`h264_nvenc`)**: Selected when NVENC API requirements are met. Preset `p4`, `b:v 6000k`.
- **CPU Fallback (`libx264`)**: High quality software encoding using `-preset medium -crf 20 -pix_fmt yuv420p`.

Audio encoding strictly preserves multi-channel audio using `-c:a aac -b:a 192k -ar 48000`.

## 5. Background Job & Real-time Progress Tracking

Exports are executed asynchronously in the persistent background job queue:
- `JobExecutor` processes `render_export` tasks.
- FFmpeg output lines are parsed in real time (`time=00:00:02.40`) to compute percent completion.
- Real-time progress is broadcast over WebSockets to React UI subscribers.
- Job cancellation sends a SIGTERM / process terminate command to FFmpeg and cleans up partial files.
- Completed exports are inspected via `FFprobeManager` and stored in the `exports` database table.
