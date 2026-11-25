# Phase 9 Stage 2: Empirical Test Results

## 1. Test Execution Summary

The Phase 9 Stage 2 test suite was executed against the local environment on Windows 11 with Python 3.11.9, pytest 9.2.0, and SQLite (aiosqlite).
Full regression verification was conducted across all existing Phase 1–8 test suites alongside the new Phase 9 Stage 2 test suite.

| Test Suite Category | File | Tests Run | Passed | Failed | Execution Time |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 9 Stage 2 (New)** | `backend/tests/test_phase9_stage2.py` | 16 | 16 | 0 | 5.27s |
| **Phase 1–8 Regression** | `backend/tests/test_*.py` | 187 | 187 | 0 | 54.78s |
| **Total Test Suite** | **All backend tests** | **203** | **203** | **0** | **60.05s** |

---

## 2. Phase 9 Stage 2 Detailed Test Breakdown

All 16 tests in `backend/tests/test_phase9_stage2.py` passed with 100% pass rate:

1. `test_microseconds_and_seconds_conversion`:
   - Validates microsecond to second conversion ($12{,}500{,}000\ \mu\text{s} \leftrightarrow 12.5\text{ s}$).
   - Validates integer type enforcement and rejection of non-integer/negative inputs.
2. `test_rational_timebase_derivation`:
   - Validates exact frame durations for 24, 25, 29.97, 30, and 60 fps timebases.
   - Verifies NTSC frame duration calculation ($33{,}367\ \mu\text{s}$ per frame).
3. `test_coordinate_system_conversions`:
   - Validates transformation between source timestamps, composition coordinates, and rendered output timestamps with playback speed scaling (1.0x, 1.25x).
4. `test_clip_boundary_validation`:
   - Enforces $t_{\text{in}} \ge 0$, $t_{\text{out}} > t_{\text{in}}$, and rejection of inverted boundaries.
5. `test_valid_asset_uris`:
   - Validates accepted logical URI forms (`asset://videos/vid_001`, `asset://audio/bg_01`, `asset://fonts/montserrat-bold`).
6. `test_rejected_asset_uris_path_traversal`:
   - Validates strict rejection of path traversal (`asset://videos/../../etc/passwd`), Windows drive paths (`asset://videos/C:/Windows`), backslashes (`\`), and query parameters.
7. `test_normalized_rect_validation`:
   - Validates normalized bounding boxes $x, y, w, h \in [0.0, 1.0]$ and rejects rectangles exceeding frame boundaries.
8. `test_layout_config_auto_population`:
   - Validates automatic slot generation for `single_full_frame` and `split_vertical` topologies.
9. `test_delivery_profile_even_dimensions`:
   - Enforces even width and height dimensions for H.264/HEVC macroblock encoding ($1080 \times 1920$, rejecting $1081 \times 1920$ or $1080 \times 1921$).
10. `test_standard_delivery_profiles_lookup`:
    - Validates preset factories for standard profiles (`9:16`, `1:1`, `4:5`, `16:9`).
11. `test_composition_spec_canonical_json_and_hash`:
    - Validates deterministic canonical JSON serialization and consistent SHA-256 digest computation across varied dict key orderings.
12. `test_composition_spec_semantic_validation`:
    - Validates end-to-end semantic pipeline catching duration mismatches, invalid safe margins, and out-of-bounds keyframes.
13. `test_composition_creation_and_versioning`:
    - Validates `CompositionService` and `CompositionVersionService` creating initial versions, optimistic concurrency control (OCC) rejecting stale writes with conflict errors, and non-destructive version restoration.
14. `test_resource_ownership_protection`:
    - Validates project-scoped asset isolation, rejecting cross-project asset references.
15. `test_database_cascade_deletions`:
    - Validates SQLite `ON DELETE CASCADE` removing all composition versions, renders, and artifacts when an owning project is deleted.
16. `test_composition_api_routes`:
    - Validates full FastAPI REST API workflow: `POST /api/compositions`, `GET /api/compositions/{id}`, `POST /api/compositions/{id}/versions`, OCC rejection (HTTP 409), version rollback, and `POST /api/compositions/validate`.

---

## 3. Full Regression Suite Results (Phases 1–8)

All 187 legacy tests passed without regressions:
- `backend/tests/test_api.py` (Phase 1–2 API core)
- `backend/tests/test_audio.py` (Phase 2 Audio extraction & Whisper)
- `backend/tests/test_clips.py` (Phase 3 Rule-based clipping)
- `backend/tests/test_export.py` (Phase 7 Export & FFmpeg render)
- `backend/tests/test_llm.py` (Phase 4 Llama.cpp highlights)
- `backend/tests/test_manual_crops.py` (Phase 6 Crop overrides)
- `backend/tests/test_phase6.py` (Phase 6 Face detection, tracking, reframing, API workflow)
- `backend/tests/test_phase8_audio.py` (Phase 8 Stage 2 Silero VAD, streaming audio, API workflow)
- `backend/tests/test_phase8_stage3.py` (Phase 8 Stage 3 3D-Speaker CAM++ diarization)
- `backend/tests/test_phase8_stage4.py` (Phase 8 Stage 4 MediaPipe landmarks, Light-ASD, AV fusion)
- `backend/tests/test_video.py` (Phase 1 Video probe & ingestion)
