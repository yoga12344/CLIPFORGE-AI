# ClipForge AI — AI Highlight & Intelligence Engine Documentation

## Overview

The ClipForge AI Highlight Engine is a local-first, privacy-preserving video intelligence subsystem engineered to automatically detect high-retention moments from speech transcripts. It operates entirely on local hardware (Intel Core i7-13620H + NVIDIA RTX 4060 Laptop GPU) without third-party cloud APIs, external subscriptions, or data telemetry.

The engine analyzes Phase 4 word-level transcripts, groups them into grammatically bounded sentences, divides long discussions into overlapping context chunks, applies a two-stage candidate discovery pipeline (deterministic windowing + local LLM analysis), refines clip boundaries to natural speech pauses, scores candidates across 7 explainable quality dimensions, removes temporal and textual duplicates, and presents ranked short-form clip proposals for user preview, editing, and approval.

---

## 1. Subsystem Architecture

```
backend/app/
├── ai/
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── model_registry.py       # Definitions for Qwen 2.5 3B/1.5B/0.5B & Llama 3.2 3B GGUFs
│   │   ├── model_manager.py        # On-demand download, verification, progress streaming, deletion
│   │   ├── llm_provider.py         # Provider interface + LlamaCppBinaryProvider (sandboxed llama-cli)
│   │   ├── prompt_templates.py     # Content-type prompts (podcast, educational, business, etc.)
│   │   ├── structured_output.py    # Strict JSON extraction, syntax repair, and Pydantic validation
│   │   └── inference_manager.py    # Sequential model lock, RAM/VRAM unloading, timeout management
│   └── highlights/
│       ├── __init__.py
│       ├── transcript_chunker.py   # Word grouping, sentence boundary detection, semantic sliding chunks
│       ├── candidate_generator.py  # Stage A (Deterministic Windows) + Stage B (Local LLM Analysis)
│       ├── boundary_refiner.py     # Sentence & word boundary snapping, hook context preservation
│       ├── highlight_validator.py  # Ground-truth quote verification, duration & timestamp constraints
│       ├── candidate_scorer.py     # Explainable 0-100 scoring across 7 content dimensions
│       ├── duplicate_detector.py   # Temporal IoU & textual Jaccard deduplication and ranking
│       └── highlight_analyzer.py   # Master 10-stage pipeline orchestrator
├── services/
│   └── highlight_service.py        # SQLite persistence, approval/rejection state machine, clip creation
├── api/routes/
│   ├── llm.py                      # LLM model registry, download, and status endpoints
│   └── highlights.py               # Discovery triggers, candidate CRUD, approval, and clip rendering
└── workers/
    └── job_executor.py             # Background worker handler for 'analyze_highlights'
```

---

## 2. Local Model Catalog & GGUF Runtime

### 2.1. Supported Local LLMs
ClipForge AI supports quantized 4-bit (`Q4_K_M`) GGUF models optimized for constrained 16 GB RAM desktop machines:

| Model ID | Parameter Count | Quantization | Disk Size | Context Window | Recommended Use Case |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`qwen-2.5-3b`** *(Default)* | 3.0 Billion | `Q4_K_M` | ~1.93 GB | 8192 tokens | High-reasoning default; excels at structured JSON extraction |
| **`llama-3.2-3b`** | 3.2 Billion | `Q4_K_M` | ~2.02 GB | 8192 tokens | Meta's dialogue model; strong conversational & podcast narrative parsing |
| **`qwen-2.5-1.5b`** | 1.5 Billion | `Q4_K_M` | ~986 MB | 4096 tokens | Fast, memory-conservative option for lower-spec hardware |
| **`qwen-2.5-0.5b`** | 490 Million | `Q4_K_M` | ~397 MB | 4096 tokens | Ultra-lightweight model with sub-second CPU response time |

### 2.2. Isolated Binary Execution (`llama.cpp`)
- Local inference is executed via the standalone, optimized `llama-cli.exe` runtime located under `backend/storage/clipforge_data/bin/llama/`.
- **Zero GIL Contention**: Runs as an isolated native Windows subprocess, eliminating Python threading locks.
- **Immediate Memory Reclamation**: When inference finishes, the process terminates and 100% of the allocated model RAM/VRAM is immediately returned to the OS.
- **Safe Process Termination**: Clean cancellation via `taskkill /F /T /PID` prevents zombie AI processes.

---

## 3. Transcript Preprocessing & Semantic Chunking

Located in `backend/app/ai/highlights/transcript_chunker.py`.

1. **Word-Level Parsing**: Ingests Phase 4 timestamped words (`word`, `start`, `end`, `prob`).
2. **Grammatical Sentence Grouping**: Groups words into natural sentences based on terminal punctuation (`.`, `?`, `!`), inter-word pauses exceeding 0.65 seconds, or a maximum threshold of 30 words per run.
3. **Overlapping Context Windows**: For long videos (e.g. 30–120 minutes), sentences are batched into 120-second semantic blocks with a 3-sentence overlap between adjacent chunks. This prevents cutting stories, jokes, or explanations that span across chunk boundaries.

---

## 4. Two-Stage Candidate Discovery

Located in `backend/app/ai/highlights/candidate_generator.py`.

### Stage A: Deterministic Window Generation
- Assembles valid candidate windows from adjacent sentences matching the user's desired duration (e.g. 15–30s, 30–45s, 30–60s, 60–90s).
- Ensures that every window begins on a capitalized sentence start and terminates on a sentence ending.
- Acts as an automatic fallback if an LLM model is not yet installed or if inference encounters an error.

### Stage B: Local LLM Semantic Analysis
- Passes structured chunk prompts to the local LLM requesting strict JSON with:
  - `start_time` and `end_time`
  - `title` (under 8 words)
  - `hook` (magnetic opening sentence)
  - `summary` (concise 1–2 sentence overview)
  - `reason` (retention justification)
  - `category` (content focus: podcast, tutorial, educational, etc.)
  - `key_quote` (verbatim excerpt from transcript)
- Output is sanitized and repaired by `structured_output.py` to handle markdown wrappers or trailing commas.

---

## 5. Boundary Refinement & Quote Validation

### 5.1. Boundary Refinement (`boundary_refiner.py`)
- Raw model timestamps are snapped to the nearest sentence start and sentence end.
- Looks backward by up to 1.5 seconds if needed to include opening context before a hook.
- Aligns final start and end timestamps to exact word boundaries, guaranteeing no cut-off words.

### 5.2. Ground-Truth Quote Verification (`highlight_validator.py`)
- Verifies that every `key_quote` produced by the LLM exists verbatim within the candidate's transcript segment.
- Computes an n-gram word overlap ratio; candidates with fabricated quotes receive a -15 point penalty.
- Validates duration boundaries and timeline bounds ($0 \le \text{start} < \text{end} \le \text{total\_duration}$).

---

## 6. Multi-Factor Scoring Engine

Located in `backend/app/ai/highlights/candidate_scorer.py`.

Candidates are evaluated on an explainable **0–100 score** across 7 distinct dimensions:

| Dimension | Max Points | Evaluation Criteria |
| :--- | :---: | :--- |
| **Hook Strength** | **20** | Provocative opening questions, direct viewer address ("you"), curiosity gap triggers |
| **Content Value** | **20** | Informational density, reasoning keywords ("because", "strategy", "lesson", "steps") |
| **Narrative Flow** | **20** | Clean sentence start and decisive terminal punctuation; penalizes mid-sentence cuts |
| **Standalone Context** | **15** | Self-contained thought; penalizes dangling pronouns ("and so", "like I said before") |
| **Interest & Depth** | **10** | Strong emotional, intellectual, or transformative vocabulary |
| **Conciseness** | **10** | Optimal speech delivery cadence (2.2–3.8 words/sec); penalizes excessive dead air |
| **Ending Quality** | **5** | Strong punchline, takeaway, or summarizing conclusion |

The complete point breakdown, alongside detected strengths and penalties, is persisted and presented in the UI via `<HighlightScoreBreakdown />`.

---

## 7. Deduplication & Ranking

Located in `backend/app/ai/highlights/duplicate_detector.py`.

1. **Temporal IoU**: Calculates Intersection over Union of time intervals between candidate pairs:
   $$\text{IoU} = \frac{\max(0, \min(e_1, e_2) - \max(s_1, s_2))}{\max(e_1, e_2) - \min(s_1, s_2)}$$
2. **Textual Jaccard Similarity**: Measures word-set overlap between candidate summaries and quotes.
3. **Greedy Filtering**: Candidates are sorted in descending order of `overall_score`. If a candidate has $\text{IoU} \ge 0.55$ or $\text{Jaccard} \ge 0.70$ with a higher-scoring candidate, it is suppressed to prevent repetitive clips.

---

## 8. Database Schema & Persistence

Stored in SQLite via `HighlightCandidate` model:

- `id`: Primary key (UUID string)
- `project_id`: Foreign key to `projects.id`
- `video_id`: Foreign key to `videos.id`
- `transcript_id`: Foreign key to `transcripts.id`
- `clip_id`: Foreign key to `clips.id` (populated when clip is rendered)
- `start_time`, `end_time`, `duration_seconds`: Verified float timestamps
- `title`, `hook`, `summary`, `reason`, `category`, `key_quote`: Structured textual metadata
- `overall_score`: Integer (0–100)
- `score_breakdown`: JSON dictionary storing individual dimension scores, penalties, and strengths
- `status`: `'discovered'`, `'approved'`, `'rejected'`, `'edited'`, `'ready_for_render'`
- `model_name`: LLM model used for analysis
- `generation_method`: `'llm'` or `'deterministic_stage_a'`

---

## 9. Background Job Lifecycle (`analyze_highlights`)

The `analyze_highlights` background job executes 10 discrete stages, streaming real-time progress over WebSockets (`/ws/jobs`):

1. **10%**: Loading transcript words
2. **20%**: Preprocessing sentences and punctuation
3. **30%**: Chunking transcript for context analysis
4. **45%**: Analyzing transcript with local AI
5. **55%**: Generating deterministic candidate windows (fallback/augmentation)
6. **70%**: Refining boundaries to sentence terminals
7. **80%**: Calculating multi-factor engagement scores
8. **90%**: Filtering duplicate overlapping windows
9. **95%**: Persisting candidates into SQLite
10. **100%**: Completed successfully

---

## 10. REST API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/ai/llm/models` | List all supported GGUF models and installation states |
| `POST` | `/api/ai/llm/models/{name}/download` | Start asynchronous background download of a GGUF model |
| `DELETE`| `/api/ai/llm/models/{name}` | Delete a downloaded GGUF model from disk |
| `GET` | `/api/ai/llm/status` | Runtime status of the local LLM subsystem |
| `POST` | `/api/videos/{video_id}/analyze-highlights` | Enqueue `analyze_highlights` background job |
| `GET` | `/api/videos/{video_id}/highlight-candidates` | List candidates for video (supports `status` filter & `sort_by`) |
| `GET` | `/api/projects/{project_id}/highlights` | List all candidates across a project |
| `GET` | `/api/highlights/{id}` | Get candidate details by ID |
| `PATCH`| `/api/highlights/{id}` | Manually edit candidate start/end times or title |
| `POST` | `/api/highlights/{id}/approve` | Mark candidate as approved |
| `POST` | `/api/highlights/{id}/reject` | Mark candidate as rejected |
| `POST` | `/api/highlights/{id}/create-clip` | Convert approved candidate into a `Clip` and enqueue render |
| `DELETE`| `/api/highlights/{id}` | Delete a highlight candidate |

---

## 11. React UI Components

Located under `src/components/highlights/`:

1. **`HighlightAnalysisPanel`**: Master container integrated as a tab in `ProjectStudio.tsx`. Provides discover triggers, candidate lists, and render modals.
2. **`HighlightCandidateCard`**: Rich candidate card featuring dynamic score badges, hook quotes, duration chips, and action controls.
3. **`HighlightCandidateList`**: Status filter tabs (`All`, `Approved`, `Discovered`, `Rejected`), sort dropdowns (`Highest Score`, `Start Time`, `Duration`), and empty states.
4. **`HighlightScoreBreakdown`**: Expandable component rendering progress bars across all 7 score dimensions, strengths, and penalties.
5. **`HighlightSettingsModal`**: Configuration dialog for model selection, content type, target duration presets, and candidate counts.
