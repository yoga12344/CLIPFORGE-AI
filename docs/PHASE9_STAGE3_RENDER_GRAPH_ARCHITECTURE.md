# Phase 9 Stage 3: Render Graph Architecture

## 1. Overview & Architectural Goals
Phase 9 Stage 3 implements a deterministic, directed acyclic graph (DAG) representation of video compositions. The compiler and execution harness translate high-level `CompositionSpec` definitions into verified FFmpeg filter complexes and safe process executions.

Key architectural properties:
- **Declarative Representation**: Compositions are defined by nodes (operations) and edges (strongly typed audio/video/subtitle streams).
- **Type-Safe Validation**: 12 graph validation rules ensure ports, stream types, and topological validity prior to compilation.
- **Deterministic Sort**: Kahn's topological sort with lexicographical tie-breaking produces byte-for-byte identical filter expressions given identical graphs.
- **Safety**: Safe `-filter_complex_script` file generation bypasses Windows command line 32k length limits.
- **Resilience**: Automatic hardware fallback from NVENC (`h264_nvenc`) to CPU (`libx264`), graceful crash recovery for interrupted render jobs, and process tree termination (`taskkill /F /T /PID`).

---

## 2. Directed Acyclic Graph (DAG) Structure

```
[VideoInputNode] ---> [VideoTrimNode] ---> [CropNode] ---> [ScaleNode] ---> [SubtitleBurnNode] ---\
                                                                                                    ---> [VideoAudioMuxNode] ---> [OutputContainerNode]
[AudioInputNode] ---> [AudioTrimNode] ---> [AudioGainNode] ---> [LoudnessNormalizeNode] ------------/
```

### Graph Components
- **Nodes**: Inherit from `BaseNode`. Maintain `input_ports` and `output_ports` with strict `StreamType` constraints (`VIDEO`, `AUDIO`, `IMAGE`, `SUBTITLE`, `ENCODED_OUTPUT`).
- **Edges**: Connect an output port of a source node to an input port of a target node. Carry explicit stream labels (e.g. `[v_trim]`, `[a_norm]`).
- **RenderGraph**: Encapsulates nodes and edges, exposes query methods for incoming/outgoing edges, sources, sinks, and structural cycle detection.

---

## 3. Data Flow and Execution Flow

1. **Composition Version**: Input `CompositionSpec` v1.0.0.
2. **Graph Builder (`CompositionToGraphBuilder`)**: Converts composition layout, camera bounding boxes, audio ducking/gain, and subtitle burns into a typed `RenderGraph`.
3. **Graph Validator (`RenderGraphValidator`)**: Enforces acyclicity, connectivity, single sink, and port type compatibility.
4. **Topological Sorter (`topological_sort`)**: Produces deterministic evaluation order.
5. **Render Graph Compiler (`RenderGraphCompiler`)**: Emits `-filter_complex` expressions or writes `.ffscript` filter scripts, maps input/output streams, and evaluates hardware encoders.
6. **Execution Harness (`RenderExecutor` & `RenderProcess`)**: Launches FFmpeg with `-progress pipe:1`, parses frame progress, handles cancellation, and falls back to CPU if NVENC is unavailable.
7. **Validation & Finalization (`OutputValidator`)**: Runs `FFprobeManager` post-flight verification (codec, dimensions, duration, A/V delta) before atomically renaming temporary output `.tmp.mp4` to the final destination file and registering `RenderArtifact`.
