# ClipForge AI — Video Processing Engine Documentation

## Overview

The ClipForge AI Video Processing Engine is a local-first, high-performance media pipeline engineered for Windows desktop hardware (Intel Core i7-13620H + NVIDIA RTX 4060 Laptop GPU). It executes actual FFmpeg and FFprobe subprocesses with strict parameter validation, frame-accurate seeking, hardware-aware fallback, and asynchronous WebSocket progress tracking.

---

## 1. Hardware & Capabilities Architecture

Located in `backend/app/video/capabilities.py`.

### Detection & Safe Fallback
1. **Binary Discovery**: Resolves Gyan.FFmpeg full build binary paths dynamically and verifies executable presence.
2. **Dynamic Encoder Verification**: Runs active 1-second test encodes (`-f lavfi -i testsrc=duration=1...`) rather than relying on banner strings.
   - Diagnosed NVIDIA driver 13.0 API vs required 13.1 for `h264_nvenc`.
   - Automatically designates `libx264` as the functional, recommended video encoder.
3. **Filter Verification**: Assesses presence of `libass`, `subtitles`, `scale`, `crop`, and blur filters.
4. **Endpoint**: `GET /api/system/video-capabilities?force_refresh=false`

---

## 2. Asynchronous Process Execution (`FFmpegManager`)

Located in `backend/app/video/ffmpeg_manager.py`.

- **Security**: Invokes commands strictly with `asyncio.create_subprocess_exec` using structured argument arrays (`List[str]`). Zero `shell=True` execution.
- **Progress Parsing**: Appends `-progress pipe:1 -nostats` to command arguments. Continuously reads stdout line-by-line, parsing:
  - `out_time_us`: Converted to seconds.
  - `progress_percent`: Calculated from `(out_time_sec / total_duration) * 100`.
  - `fps`, `frame`, `speed`.
  - Fires async callback `on_progress(FFmpegProgress)`.
- **Windows Process Tree Termination**: Tracks active process IDs. When cancellation is requested, terminates the full child process hierarchy cleanly via `taskkill /F /T /PID {pid}`.

---

## 3. Deep Media Inspection (`FFprobeManager`)

Located in `backend/app/video/ffprobe_manager.py`.

- Executes `ffprobe -v quiet -print_format json -show_format -show_streams`.
- Produces a strongly-typed `DetailedVideoMetadata` object containing:
  - Container format, duration, bitrate, tags.
  - Primary video stream: codec, profile, width, height, aspect ratio, frame rate (`fps`), pixel format, rotation angle (from stream tags or side data).
  - Primary audio stream: codec, sample rate, channels, channel layout, bit rate.
  - Subtitle streams: index, codec, language, title.

---

## 4. Video Processing Modules

### 4.1. Thumbnail Generator (`ThumbnailGenerator`)
Located in `backend/app/video/thumbnail_generator.py`.
- **Poster Thumbnail**: Extracted at 10% into video duration (or specified timestamp) to avoid initial black frames. Scaled to max width 640px, JPEG quality 2.
- **Timeline Thumbnail Strip**: Calculates $N$ evenly-spaced intervals across the duration, generating a sequence of frame previews for the interactive timeline.

### 4.2. Audio Extractor (`AudioExtractor`)
Located in `backend/app/video/audio_extractor.py`.
- Extracts source audio into 16kHz 16-bit mono PCM WAV:
  ```bash
  ffmpeg -y -i source.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 output.wav
  ```
- Complies directly with Whisper AI speech recognition input requirements.
- Validates sample rate and channels with FFprobe post-extraction.

### 4.3. Proxy Preview Generator (`PreviewGenerator`)
Located in `backend/app/video/preview_generator.py`.
- Creates 720p H.264 faststart MP4 optimized for instant browser/Electron playback:
  ```bash
  ffmpeg -y -i source.mp4 -vf "scale=-2:'min(720,ih)':flags=bicubic" \
    -c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p \
    -c:a aac -b:a 128k -ar 44100 -ac 2 -movflags +faststart preview.mp4
  ```
- Places the MP4 `moov` atom at the start of the file to support immediate seeking without full file buffering.

### 4.4. Frame-Accurate Clip Generator (`ClipGenerator`)
Located in `backend/app/video/clip_generator.py`.
- Uses fast input seeking `-ss {start}` and exact duration `-t {duration}` to produce frame-accurate cuts without frozen lead-in frames.
- Re-encodes audio and video tracks to maintain strict A/V synchronization.
- Automatically generates a companion poster thumbnail for each rendered clip.
- Verifies output duration within a 1.5s tolerance using FFprobe.

### 4.5. Multi-Ratio Reframing (`AspectRatioProcessor`)
Located in `backend/app/video/aspect_ratio.py`.
- **Target Dimensions**:
  - `9:16`: 1080 × 1920 (Shorts, Reels, TikTok)
  - `1:1`: 1080 × 1080 (Instagram Feed, LinkedIn)
  - `4:5`: 1080 × 1350 (Instagram Portrait)
  - `16:9`: 1920 × 1080 (Landscape)
- **Reframing Filtergraphs**:
  - `center_crop`: Zooms and crops centered on aspect ratio.
  - `fit_pad`: Scales to fit and adds black letterbox/pillarbox borders.
  - `blur_background`: Splits video stream into two branches. Bottom branch scales, crops, and applies `boxblur=25:5`. Top branch scales to fit and overlays centered:
    ```
    split=2[bg_in][fg_in];
    [bg_in]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[bg];
    [fg_in]scale=1080:1920:force_original_aspect_ratio=decrease[fg];
    [bg][fg]overlay=(W-w)/2:(H-h)/2
    ```

---

## 5. Background Job & Worker Queue (`JobManager`)

Located in `backend/app/workers/job_manager.py` and `job_executor.py`.

- **Bounded Concurrency**: Uses an `asyncio.Queue` with a single active worker task to execute heavy video rendering jobs sequentially, preventing VRAM exhaustion on the RTX 4060.
- **SQLite Persistence**: All jobs are tracked in the `jobs` database table with real-time `status` (`queued`, `running`, `completed`, `failed`, `cancelled`), `progress_percent`, `stage_description`, and parameter/result JSON blobs.
- **Startup Recovery**: On backend boot, any jobs left in `running` status due to a process termination or power loss are cleanly transitioned to `failed` ("Interrupted by application restart") to prevent queue deadlocks.
- **WebSocket Streaming**: Broadcasts live `JobEvent` records across `/ws/jobs`.

---

## 6. HTTP 206 Partial Content Media Streaming

Located in `backend/app/core/streaming.py`.

- Implements standard `Range: bytes=start-end` header parsing.
- Streams requested chunks with HTTP `206 Partial Content` and `Content-Range: bytes {start}-{end}/{file_size}` headers.
- Allows the HTML5 `<video>` element and Electron renderer to seek arbitrarily across source and preview files without downloading the entire video.
