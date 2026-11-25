# Phase 9 Stage 3: Graph Node Specification

## 1. Supported Node Types

### Input Nodes
- **`VideoInputNode`**: Declares a video file input (`input_index`, `filepath`). Ports: `video_out` (`VIDEO`). Emits `-i <filepath>`.
- **`AudioInputNode`**: Declares an audio source input (`input_index`, `filepath`). Ports: `audio_out` (`AUDIO`). Emits `-i <filepath>`.
- **`ImageInputNode`**: Declares a static image or overlay input. Ports: `image_out` (`IMAGE`). Emits `-loop 1 -i <filepath>`.

### Timeline & Geometry Nodes
- **`VideoTrimNode`**: Trims video segment by PTS or microseconds (`start_sec`, `end_sec`). Ports: `video_in` -> `video_out`. Filter: `trim=start=X:end=Y,setpts=PTS-STARTPTS`.
- **`AudioTrimNode`**: Trims audio segment (`start_sec`, `end_sec`). Ports: `audio_in` -> `audio_out`. Filter: `atrim=start=X:end=Y,asetpts=PTS-STARTPTS`.
- **`CropNode`**: Performs precise bounding box cropping (`w`, `h`, `x`, `y`). Ports: `video_in` -> `video_out`. Filter: `crop=w:h:x:y`.
- **`ScaleNode`**: Rescales stream to target resolution (`width`, `height`, `flags="bicubic"`). Ports: `video_in` -> `video_out`. Filter: `scale=w:h:flags=...`.
- **`PadNode`**: Adds letterbox or pillarbox padding (`w`, `h`, `x`, `y`, `color`). Ports: `video_in` -> `video_out`. Filter: `pad=w:h:x:y:color`.
- **`FPSNormalizeNode`**: Enforces target frame rate (`fps=30.0`). Filter: `fps=fps=X`.
- **`SARNormalizeNode`**: Resets Sample Aspect Ratio to 1:1 (`setsar=1`). Filter: `setsar=1`.
- **`PixelFormatConvertNode`**: Converts pixel format (`format=pix_fmt`). Filter: `format=yuv420p`.

### Audio Processing Nodes
- **`AudioResampleNode`**: Enforces sample rate and channel layout (`sample_rate`, `channels`). Filter: `aresample=48000,aformat=channel_layouts=stereo`.
- **`AudioGainNode`**: Applies volume adjustments (`gain_db`). Filter: `volume=XdB`.
- **`AudioFadeNode`**: Adds audio in/out fades (`fade_in_sec`, `fade_out_sec`). Filter: `afade=...`.
- **`LoudnessNormalizeNode`**: EBU R128 normalization (`integrated_lufs`, `true_peak_dbtp`, `loudness_range_lu`). Filter: `loudnorm=I=X:TP=Y:LRA=Z`.

### Subtitle & Overlay Nodes
- **`SubtitleBurnNode`**: Burns styled subtitles via libass (`subtitle_path`, `original_size`). Filter: `ass=filename='...':original_size=WxH`. Escapes Windows backslashes and drive colons properly (`C\\:/...`).

### Muxing & Container Nodes
- **`VideoAudioMuxNode`**: Merges video and audio streams for container export. Ports: `video_in`, `audio_in` -> `mux_out` (`ENCODED_OUTPUT`).
- **`OutputContainerNode`**: Represents target file container (`output_path`, `format="mp4"`).

---

## 2. Unsupported Node Handling
Nodes planned for later stages or unsupported in Stage 3 (e.g. `TemporalReframeNode`, `MultiTrackMixerNode`, `SpatialAudioNode`) raise an explicit `UnsupportedNodeError` during graph construction or validation, preventing invalid pipelines from running.
