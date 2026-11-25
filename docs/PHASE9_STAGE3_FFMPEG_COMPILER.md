# Phase 9 Stage 3: FFmpeg Compiler Specification

## 1. Compiler Overview
The `RenderGraphCompiler` translates a verified `RenderGraph` DAG into an `FFmpegExecutionPlan`.

The compilation pipeline operates as follows:
1. **Topological Order**: Sorts graph nodes using Kahn's algorithm to ensure dependencies are resolved prior to emission.
2. **Stream Label Generation**: Allocates deterministic stream labels (e.g. `[v0_crop]`, `[v0_scale]`, `[v_out]`, `[a_out]`).
3. **Filter Chain Assembly**: Emits individual filter chains separated by semicolons (`;`).
4. **Script Scripting vs CLI Argument**: When the filter complex length exceeds threshold (or by default on Windows), writes a `.ffscript` file and specifies `-filter_complex_script <path>`, completely eliminating Windows command length buffer overflows.
5. **Hardware Acceleration Evaluation**: Probes NVENC capability via `FFmpegManager`. Configures `-c:v h264_nvenc` with `-preset p5` when supported, or falls back to `-c:v libx264` with `-preset medium -crf 18`.

---

## 2. Windows Path Escaping Rules
FFmpeg's filter complex parser requires double-escaping for Windows absolute paths containing drive colons and backslashes (e.g., subtitle files in `ass=filename='...'`):
- Forward slashes are substituted: `C:\path\to\file.ass` -> `C:/path/to/file.ass`
- Colons are escaped: `C:/path` -> `C\:/path`
- Single quotes and special characters are escaped as `\'`.
The implementation in `backend/app/composition/render/compiler/filter_compiler.py` formats these paths deterministically and is verified across Windows paths.
