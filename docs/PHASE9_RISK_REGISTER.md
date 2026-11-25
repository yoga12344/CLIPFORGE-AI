# Phase 9: Composition Engine & Rendering Pipeline
## Document 9: Comprehensive Risk Register & Mitigation Matrix

**Document Version**: 1.0.0  
**Status**: APPROVED RISK REGISTER  
**Author**: Principal Video Systems Architect & Security Specialist  

---

## 1. Risk Matrix Overview

| Risk ID | Category | Risk Description | Severity | Likelihood | Impact Level | Primary Mitigation Strategy |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **R-01** | Platform / OS | Windows command line length limit (32,767 chars) exceeded by complex filtergraphs | **CRITICAL** | High | Fatal process failure | Automatic offloading to temporary `-filter_complex_script` files |
| **R-02** | Media / Sync | Audio-video drift caused by variable frame rate (VFR) sources or non-zero PTS | **HIGH** | High | Desynchronized audio | Mandatory pre-trim PTS normalization (`setpts=PTS-STARTPTS`, `fps=30`) |
| **R-03** | Hardware | NVIDIA NVENC out-of-memory (OOM) or driver session exhaustion | **HIGH** | Medium | Render crash | Pre-render `CapabilityDetector` probe + automatic seamless CPU `libx264` fallback |
| **R-04** | Memory | System memory exhaustion from decoding multiple 4K/1080p video streams concurrently | **HIGH** | Medium | OOM crash | Pre-scale input streams before stacking; enforce 25-frame generator chunks |
| **R-05** | Visual Quality | Subtitle text overlapping subject faces or falling behind platform UI buttons | **MEDIUM** | High | Degraded viewer retention | Face-aware collision avoidance algorithm + platform safe-area margin offsets |
| **R-06** | Security | Filtergraph argument injection or path traversal from user-supplied titles/filenames | **CRITICAL** | Low | Arbitrary code / disk exploit | Strictly no `shell=True`; sanitize text escaping for ASS/FFmpeg; validate paths |
| **R-07** | Data Integrity | Loss of manual crop overrides or inadvertent overwrite of previous composition edits | **HIGH** | Medium | User work loss | Non-destructive `CompositionVersion` snapshots; immutable version storage |
| **R-08** | UX / Performance| UI freezing, stuttering, or thread starvation during background render jobs | **MEDIUM** | Medium | Poor user experience | Process priority capping (`BELOW_NORMAL_PRIORITY_CLASS`) + thread budgeting |

---

## 2. In-Depth Risk Analyses & Architectural Mitigations

### R-01: Windows Win32 Command Line Length Limitation
- **Root Cause**: The Windows `CreateProcess` API enforces a hard maximum command-line buffer limit of **32,767 characters**. In a 60-second composition with piecewise linear crop equations, multi-layer overlays, and audio ducking chains, a generated `-filter_complex` argument string can easily reach 45,000 characters.
- **Architectural Mitigation**:
  1. `RenderGraphCompiler` monitors total character count.
  2. If the filtergraph string exceeds 2,048 characters or contains $> 1$ input stream, the compiler automatically writes the entire filtergraph body to a deterministic temporary script file:
     `storage/clipforge_data/cache/render_scripts/filtergraph_{composition_id}.ffscript`
  3. The subprocess is invoked using the standard `-filter_complex_script` argument:
     ```python
     cmd = [ffmpeg_path, "-y", "-i", source_path, "-filter_complex_script", script_path, ...]
     ```
  4. The command line remains short ($< 300$ characters) regardless of composition complexity.

---

### R-02: Audio-Video Desynchronization from Variable Frame Rates (VFR)
- **Root Cause**: Smartphone, screen recording, and web video files frequently use Variable Frame Rates (e.g. fluctuating between 23.4 and 29.8 fps) and non-zero container start times (e.g. audio stream starting at $+0.045$s relative to video). Naive trimming (`-ss` and `-t`) causes progressive audio drift over a 60-second clip.
- **Architectural Mitigation**:
  1. `FFprobeManager` extracts `start_time` for both video and audio streams.
  2. The input normalization stage inserts:
     ```ffmpeg
     [0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS,fps=fps=30.000:round=near[v_norm];
     [0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[a_norm]
     ```
  3. This resets presentation timestamps to zero simultaneously for both audio and video, locking lipsync tightly across the entire clip.

---

### R-03: NVIDIA NVENC Hardware Session Exhaustion & OOM
- **Root Cause**: The NVIDIA RTX 4060 Laptop GPU has an 8 GB VRAM pool shared with the OS display manager, desktop compositing, and other apps. Consumer GeForce drivers restrict concurrent NVENC sessions. If NVENC fails, unhandled exceptions cause complete job failure.
- **Architectural Mitigation**:
  1. **Pre-flight Probe**: `CapabilityDetector.detect()` runs a micro-encode test (1 frame) using `h264_nvenc`.
  2. **VRAM Headroom Check**: If free VRAM is $< 1.5$ GB, NVENC is skipped and `libx264` is selected automatically.
  3. **Automatic Fallback Recovery**: If NVENC encoding fails midway with return code $\ne 0$, `CompositionRenderService` catches the failure, logs a detailed warning, switches the encoder to `libx264` (CPU), and re-executes the render without failing the user's export.

---

### R-04: System Memory Exhaustion During Multi-Stream Decoding
- **Root Cause**: In a 3-person grid layout, FFmpeg must decode the source video into 3 separate branches simultaneously. If each branch scales a 4K frame to 1080x1920 independently, memory consumption can spike past 4 GB.
- **Architectural Mitigation**:
  1. The Render Graph Compiler places a downscale node immediately after the input trim:
     `[v_in]scale=1920:1080[v_scaled]; [v_scaled]split=3...`
  2. This ensures all subsequent crop and blur operations run on bounded 1080p buffers rather than 4K rasters.

---

### R-05: Subtitle Text Overlapping Face Bounding Boxes
- **Root Cause**: Fixed bottom-aligned subtitles frequently collide with a subject's chin or mouth in vertical 9:16 crops, obstructing facial expressions.
- **Architectural Mitigation**:
  1. `SubtitleCompositionEngine` queries the `FaceTrack` bounding boxes corresponding to the active speech interval.
  2. If the face rectangle intersects the subtitle vertical region ($y \in [0.70, 0.88]$), the engine dynamically adjusts the ASS margin:
     $$\text{margin\_v}_{\text{adjusted}} = \text{margin\_v}_{\text{default}} + \text{offset\_to\_clear\_face}$$
  3. The subtitles float gracefully above the subject's chest/chin while remaining inside the safe viewing area.

---

### R-06: Subprocess Argument Injection & Path Security
- **Root Cause**: User-provided clip titles, custom fonts, or B-roll filenames could contain shell metacharacters (`&`, `;`, `|`, `"`, `'`) or directory traversal tokens (`../`).
- **Architectural Mitigation**:
  1. **No `shell=True`**: All subprocess calls across the entire codebase strictly use `asyncio.create_subprocess_exec` with explicit argument arrays.
  2. **Filename Sanitization**: Asset references are resolved against a project root folder using strict `Path.resolve()` checks; paths resolving outside the project directory are rejected with a 403 error.
  3. **ASS Text Escaping**: Subtitle strings are sanitized using `escape_ass_text()`, stripping curly braces and backslashes to prevent ASS override tag injection.

---

### R-07: Inadvertent Overwriting of User Keyframes & Edits
- **Root Cause**: Re-running AI reframing or changing an aspect ratio could wipe out carefully positioned manual crop adjustments made by the user.
- **Architectural Mitigation**:
  1. `ManualCropOverride` objects are explicitly flagged with `is_locked = True`.
  2. The `CameraReframePlanner` treats manual keyframes as fixed boundary constraints, interpolating AI trajectories *between* manual keyframes without moving them.
  3. Every manual save creates a new `CompositionVersion` record in SQLite, allowing one-click rollback at any time.

---

### R-08: UI Freezing During Export Rendering
- **Root Cause**: FFmpeg encoding saturated all CPU cores, starving the Electron main process and React UI of execution cycles.
- **Architectural Mitigation**:
  1. On Windows, FFmpeg is spawned with `creationflags = subprocess.BELOW_NORMAL_PRIORITY_CLASS`.
  2. FFmpeg thread count is explicitly constrained with `-threads 8` (leaving 8 logical threads entirely free for OS and UI).
  3. The Electron renderer remains fluid at 60 FPS throughout long multi-minute renders.
