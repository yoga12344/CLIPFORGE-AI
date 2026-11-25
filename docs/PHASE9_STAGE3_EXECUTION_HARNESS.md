# Phase 9 Stage 3: Execution Harness Specification

## 1. Process Lifecycle & Execution Safety
The rendering engine executes FFmpeg via asynchronous subprocesses managed by `RenderExecutor` and `RenderProcess`:
- **Safe Subprocess Invocations**: Array-based arguments (`List[str]`), strictly prohibiting `shell=True`.
- **Progress Tracking**: Configures `-progress pipe:1` to read realtime metrics:
  - `out_time_us` / `out_time_ms`
  - `frame` count
  - `fps`
  - `total_size`
  - `speed`
  `RenderProgressTracker` calculates true completion percentages (0.0 to 1.0) and publishes them via `JobEventBroadcaster`.
- **Atomic File Replacement**: Writes to `<output_filename>.tmp.mp4` until validation succeeds, then performs an atomic filesystem rename to the target destination.

---

## 2. Cancellation and Process Tree Killing
On Windows, child processes spawned by python or FFmpeg can linger as orphans. `RenderCancellationManager` leverages `FFmpegManager.cancel_process(proc_key)`:
- Invokes Windows `taskkill /F /T /PID <pid>` to terminate the entire process tree.
- Removes orphaned temporary files and marks the job status as `CANCELLED` in the database.

---

## 3. Crash Recovery
On application startup, `RenderRecoveryService.reconcile_interrupted_renders()` queries all renders in `PROCESSING` or `RENDERING` state:
- If the associated OS PID is no longer alive, it cleans up partial `.tmp.mp4` files and transitions the render status to `FAILED` with an informative error message (`"Application terminated unexpectedly during rendering"`).
- Enables the UI and user to retry without dangling lock states.
