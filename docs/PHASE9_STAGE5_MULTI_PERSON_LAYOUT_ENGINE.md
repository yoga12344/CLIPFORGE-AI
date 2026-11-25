# Phase 9 Stage 5: Multi-Person Layout Engine

## Overview
Phase 9 Stage 5 implements the multi-person spatial composition and layout engine for ClipForge AI. When long-form content features conversational dialogues, podcast debates, co-hosts, or interviews, single-subject reframing cuts out non-verbal reactions and creates excessive camera switching. The Multi-Person Layout Engine automatically plans, synthesizes, and compiles multi-subject video filter graphs for standard vertical (9:16) and landscape/square output formats.

---

## 1. Architecture & Capabilities

The multi-person layout engine operates across three core architectural components:

### A. Dynamic Layout Selector (`layout_selector.py`)
Analyzes active face tracks, diarization turns, and spatial proximity across temporal windows to choose the optimal layout template:
- **`single_speaker_reframed`**: 1 active subject; speaker-aware smooth framing.
- **`split_vertical`**: 2 active co-speakers/debaters (stacked top and bottom in 9:16; 1080x960 each for 1080x1920 output).
- **`split_horizontal`**: 2 side-by-side subjects (common in 16:9 or 1:1 formats).
- **`grid_2x2` / `xstack`**: 3 to 4 simultaneous speakers arranged in an even quadrant grid.
- **`picture_in_picture` (PiP)**: Dominant primary speaker with secondary reaction inset.
- **`blurred_background`**: Landscape video centered over a full-screen blurred version of itself.

### B. Extended Filter Graph Nodes (`nodes.py` & `filter_compiler.py`)
Added first-class FFmpeg filter graph node representations for multi-stream spatial layouts:
- `SplitNode` (`split=N`): Clones input video stream into $N$ identical streams without disk I/O.
- `OverlayNode` (`overlay=x:y`): Composites secondary streams over primary base layers with coordinate positioning.
- `VStackNode` (`vstack=inputs=N`): Vertically stacks $N$ video streams of matching width.
- `HStackNode` (`hstack=inputs=N`): Horizontally stacks $N$ video streams of matching height.
- `XStackNode` (`xstack=inputs=N:layout=...`): General $N$-stream 2D matrix stacking.
- `BoxBlurNode` (`boxblur=luma_radius:luma_power`): Fast spatial blur filter for blurred background presentation.

### C. Graph Builder Integration (`graph_builder.py`)
`CompositionToGraphBuilder` compiles `MultiPersonLayoutSpec` directly into non-linear acyclic filter graphs:
- In `split_vertical`: Clones the source stream via `SplitNode`, crops Subject 1 and Subject 2 independently to target dimensions, and stacks them with `VStackNode`.
- In `blurred_background`: Clones source stream, scales and blurs background stream via `BoxBlurNode`, scales foreground preserving aspect ratio, and overlays foreground onto blurred canvas via `OverlayNode`.
- In `picture_in_picture`: Scales secondary crop and overlays at configured `(x, y)` coordinate offset with optional border padding.

---

## 2. Layout Specifications

| Layout Mode | Target Dimensions (9:16) | Component Nodes | Typical Use Case |
| :--- | :--- | :--- | :--- |
| `split_vertical` | 1080x1920 (stacked 1080x960) | Split, Crop x2, Scale x2, VStack | Dialogue, two-host podcasts, interviews |
| `blurred_background` | 1080x1920 | Split, Scale x2, BoxBlur, Overlay | Landscape b-roll, non-crop horizontal clips |
| `picture_in_picture` | 1080x1920 (inset ~360x640) | Split, Crop x2, Scale x2, Overlay | Reaction videos, tutorials, secondary host |
| `grid_2x2` | 1080x1920 (4x 540x960) | Split, Crop x4, Scale x4, XStack | Group podcasts, panel discussions |

---

## 3. Real Rendering Verification

All multi-person layouts generate valid single-pass complex filtergraphs:
```
[0:v]split=2[split_0][split_1];
[split_0]crop=w=640:h=540:x=0:y=180,scale=w=1080:h=960[crop_0];
[split_1]crop=w=640:h=540:x=640:y=180,scale=w=1080:h=960[crop_1];
[crop_0][crop_1]vstack=inputs=2[vstack_out]
```

Tested with real synthetic video fixtures and verified by `OutputValidator` and `ffprobe`.
