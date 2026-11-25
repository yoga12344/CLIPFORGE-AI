# Phase 9 Stage 2: CompositionSpec v1.0.0 Specification

## 1. Executive Summary

`CompositionSpec` v1.0.0 represents the unified, canonical, non-destructive editing model for ClipForge AI. It formalizes all video, audio, visual asset, subtitle, camera reframe, and delivery requirements into a strictly validated, deterministic JSON-serializable abstract syntax tree (AST).

Prior to Phase 9 Stage 2, clip generation relied on direct parameter passing to FFmpeg render scripts, coupling timeline definitions to raw output formats and rendering implementations. `CompositionSpec` decouples creative intent from the rendering engine, providing:
- **Canonical Microsecond Timebase**: Zero-drift time coordinates using integer microseconds (`us`).
- **Logical Asset Addressing**: Project-scoped URI references (`asset://<type>/<id>`) preventing path traversal and external filesystem leakage.
- **Strict Pydantic V2 Validation**: Validated bounds for normalized coordinates, bounding boxes, safe margins, and audio gain limits.
- **Deterministic Content Hashing**: Canonical JSON serialization paired with SHA-256 content hashing for snapshot integrity and caching.
- **Decoupled Delivery Formats**: Independent layout topologies and delivery aspect ratios allowing multi-platform export without timeline restructuring.

---

## 2. Specification Architecture

### 2.1 Schema Hierarchy
```
CompositionSpec (v1.0.0)
├── metadata (id, project_id, title, version, created_at, updated_at)
├── source_media (SourceMediaMetadata)
├── timeline (TimelineSpec)
│   ├── timebase (RationalTimebase)
│   ├── source_boundary (ClipBoundary)
│   ├── composition_boundary (ClipBoundary)
│   ├── scenes (List[TimelineSceneBoundary])
│   └── transitions (List[TimelineTransition])
├── tracks (List[CompositionTrack])
│   ├── VideoTrack
│   ├── AudioTrack
│   ├── SubtitleTrackSpec
│   ├── BrollTrackSpec
│   └── OverlayTrackSpec
├── layout (LayoutConfig)
│   ├── topology (LayoutTopology Enum)
│   ├── aspect_ratio (AspectRatioPreset Enum)
│   ├── safe_area (SafeAreaConfig)
│   ├── background (BackgroundTreatment)
│   └── slots (List[LayoutSlot])
├── camera_plan (CameraPlan)
│   ├── default_subject (SubjectReference)
│   ├── keyframes (List[CameraKeyframe])
│   ├── overrides (List[ManualOverride])
│   └── smoothing_strength, hold_duration, max_velocity
├── subtitles (SubtitleCompositionConfig)
│   ├── style_preset, font_family, font_size, primary_color, outline_color
│   ├── word_level_timing, max_words_per_line, max_lines
│   ├── collision (SubtitleCollisionConfig)
│   └── segments (List[SubtitleSegmentRef])
├── overlays (OverlayCompositionConfig)
│   ├── broll_items (List[BRollItemSpec])
│   ├── graphic_overlays (List[GraphicOverlaySpec])
│   └── global_safe_area
├── audio (AudioCompositionConfig)
│   ├── dialogue (VoiceDialogueConfig)
│   ├── background_music (BackgroundMusicConfig)
│   ├── ducking (AudioDuckingConfig)
│   ├── sound_effects (List[SoundEffectItem])
│   └── loudness (LoudnessMasteringConfig: -14 LUFS, -1.0 dBTP)
└── delivery (DeliveryProfile)
    ├── aspect_ratio, width, height, fps (RationalTimebase)
    ├── video_bitrate_kbps, audio_bitrate_kbps, sample_rate, channels
    ├── video_codec, audio_codec, pix_fmt
    └── max_file_size_mb
```

---

## 3. Subsystem Specifications

### 3.1 Timeline & Timebase (`timeline.py`)
- **Canonical Unit**: Integer microsecond (`us`, $1 \text{ s} = 1,000,000\ \mu\text{s}$). Floating-point seconds are derived only.
- **Rational Timebase**: `RationalTimebase(numerator, denominator)`.
  - Common presets: `24 fps` (24/1), `25 fps` (25/1), `29.97 fps` (30000/1001), `30 fps` (30/1), `59.94 fps` (60000/1001), `60 fps` (60/1).
- **Coordinate Conversion**:
  - `source_to_composition_us(source_us, boundary)`
  - `composition_to_source_us(comp_us, boundary)`
  - `composition_to_output_us(comp_us, speed_factor)`

### 3.2 Asset URI Specification (`assets.py`)
- **Format**: `asset://<type>/<id>`
- **Allowed Types**: `videos`, `audio`, `images`, `broll`, `overlays`, `subtitles`, `fonts`.
- **Validation Rules**:
  - Exactly two components following `asset://`.
  - Allowed characters: alphanumeric, hyphens, underscores (`^[a-zA-Z0-9_\-]+$`).
  - Strict rejection of Windows drive letters (`C:`, `D:`), backslashes, path traversal sequences (`..`), and absolute paths.

### 3.3 Layout & Framing (`layout.py`)
- **Topologies**:
  - `single_full_frame`: Single main subject auto-cropped or scaled to canvas.
  - `split_vertical`: Dual 50/50 vertical division (e.g., speaker + screen/react).
  - `split_horizontal`: Horizontal stacked panels.
  - `pip_corner`: Picture-in-picture floating overlay in specified corner.
  - `screen_above_speaker`: Landscape screen share on top, vertical portrait speaker on bottom.
  - `grid_2x2`: 4-quadrant layout for multi-speaker or multi-view setups.
  - `freeform`: Custom user-defined absolute or normalized slots.
- **Normalized Coordinates (`NormalizedRect`)**:
  - $x, y, w, h \in [0.0, 1.0]$ with $(x + w \le 1.0001)$ and $(y + h \le 1.0001)$.
- **Background Treatments**: `blur` (configurable $\sigma \in [1, 100]$), `solid_color` (hex color `#RRGGBB`), `gradient`, `blurred_dimmed`, `transparent`.
- **Safe Area Margins**: Configurable top, bottom, left, and right safe zones avoiding UI overlay clipping on TikTok, Instagram Reels, and YouTube Shorts.

### 3.4 Camera Plan & Smoothing (`camera.py`)
- **Keyframe Anchors**: Normalized viewport bounding box with source timestamp (`timestamp_us`), easing curve (`linear`, `ease_in`, `ease_out`, `ease_in_out`, `hold`), and tracking target identity (`tracking_target_id`).
- **Hold Duration**: Minimum hold time (`min_hold_duration_us = 1_200_000` $\mu\text{s}$ / 1.2s) preventing jarring, hyper-frequent camera shifts during multi-speaker dialogue.
- **Smoothing Filter**: Exponential Moving Average (EMA) parameter `smoothing_strength = 0.85`.
- **Velocity Clamping**: Maximum velocity clamp (`max_velocity_per_sec = 0.40` screen widths per second).
- **Manual Overrides**: Explicit `is_locked = True` segments where algorithmic reframing is strictly overridden by manual user keyframes.

### 3.5 Subtitles & Styling (`subtitles.py`)
- **Word-Level Timing**: Microsecond timestamps (`start_us`, `end_us`) for active word karaoke highlighting.
- **Presets**: `clean_modern`, `bold_impact`, `cinematic_minimal`, `karaoke_highlight`, `retro_typewriter`.
- **Collision Avoidance**: Automatic clearance checks against bottom safe area margins, active speaker face bounding boxes, and lower-third graphics.

### 3.6 Overlays & B-Roll (`overlays.py`)
- **B-Roll Placements**: `cutaway` (full-frame cover), `pip` (partial overlay), `split` (co-displayed alongside primary video).
- **Audio Routing**: Presets for `mute`, `background_low`, `duck_main`, `full_audio`.
- **Transitions**: `cut`, `crossfade`, `wipe_left`, `wipe_right`, `dip_to_black`.

### 3.7 Audio Mixing & Loudness (`audio.py`)
- **Voice Dialogue Track**: Independent volume gain ($0.0 \dots 4.0$), high-pass filtering (80 Hz default), EQ presence boost (+2.0 dB default), noise suppression level.
- **Dynamic Ducking**:
  - Attenuation: $-18.0 \text{ dB}$ default.
  - Attack: $50 \text{ ms}$ (smooth fade-down).
  - Release: $300 \text{ ms}$ (smooth return).
  - Threshold: $-24.0 \text{ dBFS}$.
- **Mastering**: EBU R128 compliance defaults:
  - Target Integrated Loudness: $-14.0 \text{ LUFS}$ (streaming standard).
  - Maximum True Peak: $-1.0 \text{ dBTP}$.
  - Loudness Range Target (LRA): $7.0 \text{ LU}$.

### 3.8 Delivery Profiles (`delivery.py`)
- **Macroblock Validation**: Output resolutions are strictly validated to even pixel dimensions ($w \pmod 2 = 0$ and $h \pmod 2 = 0$) preventing H.264 / HEVC encoder macroblock alignment failures.
- **Standard Profiles**:
  - `9:16` Portrait: $1080 \times 1920$ (TikTok, IG Reels, Shorts).
  - `1:1` Square: $1080 \times 1080$ (Feed, LinkedIn, Twitter).
  - `4:5` Social Portrait: $1080 \times 1350$ (Instagram feed).
  - `16:9` Landscape: $1920 \times 1080$ (YouTube, Web, Desktop).

---

## 4. Canonical Serialization and Content Hashing

`CompositionSpec` implements deterministic serialization:
1. Export model dump to native Python dict using Pydantic V2.
2. Sort all keys recursively.
3. Serialize to UTF-8 encoded compact JSON (`separators=(',', ':')`).
4. Calculate SHA-256 digest over the canonical byte stream.

```python
spec = CompositionSpec.create_default(
    id="comp_01J...",
    project_id="proj_01J...",
    source_media=SourceMediaMetadata(...)
)
canonical_json = spec.to_canonical_json()
content_hash = spec.compute_content_hash()
# Produces identical SHA-256 hash regardless of platform or dict ordering
```

---

## 5. Semantic Validation Pipeline

The `validate_composition_semantics(spec)` routine executes 10 structural validation stages:
1. **Version Compatibility**: Enforces `schema_version == "1.0.0"`.
2. **Timeline Boundary Coherence**: Ensures `composition_boundary.duration_us <= source_boundary.duration_us`.
3. **Track Temporal Bounds**: Ensures track segments fall within composition duration.
4. **Layout Geometry Bounds**: Verifies all layout slots reside within $[0.0, 1.0]$.
5. **Slot Index Uniqueness**: Prevents duplicate slot IDs in multi-window topologies.
6. **Camera Keyframe Monotonicity**: Checks keyframe timestamps and hold durations.
7. **B-Roll Duration Clamping**: Ensures overlay items do not exceed the timeline.
8. **Subtitle Timing Alignment**: Validates segment and word timestamp ordering.
9. **Audio Gain Limits**: Prevents negative volume gains or destructive levels.
10. **Delivery Profile Dimensions**: Enforces even integer width and height dimensions.
