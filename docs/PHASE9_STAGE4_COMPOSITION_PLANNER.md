# Phase 9 Stage 4: Composition Planner Specification

## 1. Overview & Architecture
Phase 9 Stage 4 delivers the **Intelligent Composition Planner**, bridging raw multi-modal AI analysis (Whisper transcripts, YuNet face tracks, Silero VAD, CAM++ diarization, MediaPipe landmarks, and Light-ASD active speaker detection) into a valid, editable `CompositionSpec` v1.0.0.

Key Architectural Responsibilities:
1. **Multi-Modal Subject Evaluation (`SubjectEvaluator`)**: Combines visual active speaker state, acoustic speaker turns, face scale, and centrality into a composite importance score.
2. **Shot Framing & Pacing (`ShotSelector`)**: Classifies shots into Close-Up (`CU`), Medium Shot (`MS`), or Wide Shot (`WS`), while enforcing cinematic minimum hold durations ($\ge 1.2\text{s}$) to avoid rapid jitter cuts.
3. **Smooth Reframing Trajectories (`TransitionPlanner`)**: Calculates target 9:16 aspect ratio normalized crop rectangles, applies velocity clamping ($\le 0.40$ screen widths/s), Exponential Moving Average (EMA) smoothing ($\alpha = 0.15$), and cut transitions on dialogue speaker changes.
4. **End-to-End Orchestration (`CompositionPlannerService`)**: Translates approved HighlightCandidates into complete multi-track timeline specifications with word-level subtitles, audio mastering presets, and persistent versioned database storage.
5. **REST API Interface**: Exposes `POST /api/compositions/auto-plan`.

---

## 2. Multi-Modal Weighting Formula
The subject importance score $S(f, t)$ for face track $f$ at timestamp $t$ is calculated as:
$$S(f, t) = w_{active} \cdot S_{active} + w_{diar} \cdot S_{diar} + w_{area} \cdot S_{area} + w_{center} \cdot S_{center}$$
Default weights:
- $w_{active} = 0.50$ (Active speaker visual state)
- $w_{diar} = 0.20$ (Acoustic diarization speaker turn alignment)
- $w_{area} = 0.15$ (Relative face size)
- $w_{center} = 0.15$ (Horizontal centrality)
