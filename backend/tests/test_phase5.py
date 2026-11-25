"""
ClipForge AI - Phase 5 Test Suite
Tests AI Clip Intelligence, Local LLM Architecture, Transcript Preprocessing,
Highlight Discovery, Scoring, Boundary Refinement, Deduplication, and Database Persistence.
"""

import asyncio
import json
import os
import sys
import tempfile
import pytest
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import async_session_factory, init_db, engine
from app.db.models import Project, Video, Transcript, TranscriptSegment, HighlightCandidate, Job
from app.ai.llm.model_registry import ModelRegistry, SUPPORTED_LLM_MODELS
from app.ai.llm.model_manager import LLMModelManager, LLMModelStatus
from app.ai.llm.llm_provider import LlamaCppBinaryProvider
from app.ai.llm.structured_output import parse_and_validate_candidates, clean_json_string
from app.ai.llm.inference_manager import LLMInferenceManager
from app.ai.highlights.transcript_chunker import (
    TranscriptChunker, TimedWord, TimedSentence, TranscriptChunk
)
from app.ai.highlights.candidate_generator import CandidateGenerator
from app.ai.highlights.boundary_refiner import BoundaryRefiner
from app.ai.highlights.highlight_validator import HighlightValidator
from app.ai.highlights.candidate_scorer import CandidateScorer
from app.ai.highlights.duplicate_detector import DuplicateDetector, calculate_temporal_iou, calculate_text_jaccard
from app.ai.highlights.highlight_analyzer import HighlightAnalyzer, HighlightAnalysisConfig
from app.services.highlight_service import HighlightService
from app.services.transcript_repository import TranscriptRepository
from app.workers.job_manager import JobManager
from app.workers.cancellation import CancellationToken


@pytest.fixture(autouse=True)
async def setup_test_db():
    await init_db()


@pytest.fixture
def sample_timed_words() -> list[TimedWord]:
    """Generates synthetic timed words spanning ~40 seconds of dialogue."""
    raw_text = (
        "Welcome to ClipForge AI. "
        "Why do most creators struggle to grow on short form video? "
        "The truth is simple: they lack a strong hook in the first three seconds. "
        "Because if you do not grab attention immediately, viewers will scroll away. "
        "Here is the secret formula to fix that right now. "
        "First, lead with a provocative question or shocking fact. "
        "Second, deliver clear practical advice without any fluff. "
        "In conclusion, that is how you transform long videos into viral short clips."
    )
    words = []
    current_time = 0.5
    for w in raw_text.split():
        dur = 0.35 if len(w) > 4 else 0.25
        words.append(TimedWord(
            word=w,
            start=round(current_time, 2),
            end=round(current_time + dur, 2),
            prob=0.95
        ))
        current_time += dur + (0.4 if w.endswith((".", "?", "!")) else 0.08)
    return words


# 1. Local LLM model registry
def test_llm_model_registry():
    models = ModelRegistry.list_models()
    assert len(models) >= 3
    default_m = ModelRegistry.get_default_model()
    assert default_m.id == "qwen-2.5-3b"
    assert "3B" in default_m.name
    llama_m = ModelRegistry.get_model("llama-3.2-3b")
    assert llama_m is not None
    assert llama_m.quantization == "Q4_K_M"


# 2. Model installation validation
def test_model_installation_detection():
    status = LLMModelManager.check_model_status("qwen-2.5-3b")
    assert status.model_id == "qwen-2.5-3b"
    assert status.name == "Qwen 2.5 3B Instruct (Q4_K_M)"
    assert isinstance(status.is_installed, bool)


# 3. Missing model handling
def test_missing_model_handling():
    status = LLMModelManager.check_model_status("non-existent-model")
    assert status.is_installed is False
    assert status.file_path is None


# 4. Model download cancellation
@pytest.mark.asyncio
async def test_model_download_cancellation():
    cancel_token = asyncio.Event()
    cancel_token.set()  # Already cancelled

    with pytest.raises(asyncio.CancelledError):
        await LLMModelManager.download_model("qwen-2.5-0.5b", cancellation_token=cancel_token)


# 5. Transcript preprocessing
def test_transcript_preprocessing(sample_timed_words):
    sentences = TranscriptChunker.group_words_into_sentences(sample_timed_words)
    assert len(sentences) >= 4
    for sent in sentences:
        assert sent.start_time < sent.end_time
        assert len(sent.words) > 0
        assert sent.text.strip() != ""


# 6. Sentence boundary detection
def test_sentence_boundary_detection(sample_timed_words):
    sentences = TranscriptChunker.group_words_into_sentences(sample_timed_words)
    question_sentence = [s for s in sentences if "?" in s.text]
    assert len(question_sentence) > 0
    assert "Why do most creators struggle" in question_sentence[0].text
    assert question_sentence[0].has_terminal_punct is True


# 7. Long transcript chunking
def test_long_transcript_chunking(sample_timed_words):
    sentences = TranscriptChunker.group_words_into_sentences(sample_timed_words)
    chunks = TranscriptChunker.create_overlapping_chunks(
        sentences,
        target_chunk_duration=15.0,  # Small duration to force multi-chunk
        overlap_sentences=1
    )
    assert len(chunks) >= 1
    assert all(c.word_count > 0 for c in chunks)
    assert all(len(c.formatted_text_with_timestamps) > 0 for c in chunks)


# 8. Candidate window generation (Stage A)
def test_stage_a_candidate_generation(sample_timed_words):
    sentences = TranscriptChunker.group_words_into_sentences(sample_timed_words)
    candidates = CandidateGenerator.generate_stage_a_windows(
        sentences=sentences,
        target_duration_min=10.0,
        target_duration_max=40.0,
        max_windows=5
    )
    assert len(candidates) > 0
    c0 = candidates[0]
    assert c0.duration_seconds >= 10.0
    assert c0.start_time < c0.end_time
    assert c0.generation_method == "deterministic_stage_a"


# 9. LLM structured output validation
def test_llm_structured_output_validation():
    valid_json = """
    ```json
    {
      "candidates": [
        {
          "start_time": 5.2,
          "end_time": 25.4,
          "title": "Why Creators Struggle",
          "hook": "Why do most creators struggle to grow?",
          "summary": "Explains the critical role of opening hooks.",
          "reason": "Addresses high-volume creator pain point.",
          "category": "educational",
          "key_quote": "they lack a strong hook in the first three seconds",
          "strengths": ["Strong hook", "Actionable advice"],
          "weaknesses": []
        }
      ]
    }
    ```
    """
    resp = parse_and_validate_candidates(valid_json)
    assert len(resp.candidates) == 1
    c = resp.candidates[0]
    assert c.title == "Why Creators Struggle"
    assert c.start_time == 5.2
    assert c.end_time == 25.4


# 10. Invalid JSON handling and repair
def test_invalid_json_handling():
    # JSON with trailing commas and surrounding text
    trailing_comma_json = """
    Here are the discovered highlights from the clip:
    {
      "candidates": [
        {
          "start_time": 10.0,
          "end_time": 30.0,
          "title": "Fix Your Hook",
          "hook": "Here is the secret formula,",
        },
      ]
    }
    Hope this helps!
    """
    resp = parse_and_validate_candidates(trailing_comma_json)
    assert len(resp.candidates) == 1
    assert resp.candidates[0].title == "Fix Your Hook"

    # Completely broken non-JSON string
    with pytest.raises(ValueError):
        parse_and_validate_candidates("Sorry, I could not find any clips in this video.")


# 11. Timestamp validation
def test_timestamp_validation():
    is_valid, errors = HighlightValidator.validate_candidate(
        start_time=5.0,
        end_time=35.0,
        total_video_duration=60.0,
        min_duration=20.0,
        max_duration=60.0
    )
    assert is_valid is True
    assert len(errors) == 0

    # Inverted timestamps
    is_valid_inv, errors_inv = HighlightValidator.validate_candidate(
        start_time=35.0,
        end_time=15.0,
        total_video_duration=60.0
    )
    assert is_valid_inv is False


# 12. Quote verification
def test_quote_verification():
    excerpt = "They lack a strong hook in the first three seconds because viewers will scroll away."
    valid_quote = "lack a strong hook in the first three seconds"
    is_valid, score, verified = HighlightValidator.verify_quote(valid_quote, excerpt)
    assert is_valid is True
    assert score >= 0.8
    assert verified is not None

    hallucinated_quote = "You must spend five thousand dollars on a fancy camera."
    is_valid_hal, score_hal, verified_hal = HighlightValidator.verify_quote(hallucinated_quote, excerpt)
    assert is_valid_hal is False
    assert verified_hal is None


# 13. Candidate scoring
def test_candidate_scoring():
    text = (
        "Why do creators struggle to grow? "
        "Because if you do not grab attention immediately with a hook, viewers scroll away. "
        "First, lead with a provocative question. Second, provide practical value. "
        "In conclusion, that is how you win on short form video."
    )
    hook = "Why do creators struggle to grow?"
    score_data = CandidateScorer.score_candidate(
        text=text,
        hook_phrase=hook,
        duration=35.0,
        target_min_duration=30.0,
        target_max_duration=60.0
    )
    assert 60 <= score_data.overall_score <= 100
    assert score_data.hook_strength >= 12
    assert score_data.content_value >= 12
    assert score_data.narrative_completeness >= 14
    assert len(score_data.strengths) > 0


# 14. Duplicate detection and ranking
def test_duplicate_detection():
    from app.ai.highlights.highlight_analyzer import EnrichedHighlightCandidate

    c1 = EnrichedHighlightCandidate(
        start_time=10.0,
        end_time=40.0,
        duration_seconds=30.0,
        title="High Scoring Clip",
        hook="Why hooks matter",
        summary="Discussion on hooks",
        reason="Good insight",
        category="general",
        key_quote="hooks matter",
        transcript_excerpt="Why hooks matter in video",
        overall_score=92,
        score_breakdown=CandidateScorer.score_candidate("Why hooks matter in video", "Why hooks matter", 30.0)
    )

    # c2 overlaps heavily with c1 (12s to 42s = ~80% overlap) with lower score
    c2 = EnrichedHighlightCandidate(
        start_time=12.0,
        end_time=42.0,
        duration_seconds=30.0,
        title="Duplicate Clip",
        hook="Why hooks matter",
        summary="Discussion on hooks",
        reason="Good insight",
        category="general",
        key_quote="hooks matter",
        transcript_excerpt="Why hooks matter in video",
        overall_score=75,
        score_breakdown=CandidateScorer.score_candidate("Why hooks matter in video", "Why hooks matter", 30.0)
    )

    # c3 is distinct (50s to 80s)
    c3 = EnrichedHighlightCandidate(
        start_time=50.0,
        end_time=80.0,
        duration_seconds=30.0,
        title="Distinct Advice",
        hook="Second principle",
        summary="Different topic",
        reason="Fresh content",
        category="general",
        key_quote="second principle",
        transcript_excerpt="Here is the second principle",
        overall_score=85,
        score_breakdown=CandidateScorer.score_candidate("Here is the second principle", "Second principle", 30.0)
    )

    filtered, total_disc, remaining = DuplicateDetector.filter_and_rank_candidates(
        [c1, c2, c3],
        max_temporal_iou=0.60
    )
    assert total_disc == 3
    assert remaining == 2
    assert filtered[0].title == "High Scoring Clip"
    assert filtered[1].title == "Distinct Advice"


# 15. Candidate persistence
@pytest.mark.asyncio
async def test_candidate_database_persistence():
    async with async_session_factory() as db:
        proj = Project(name="Highlight Test Project")
        db.add(proj)
        await db.commit()
        await db.refresh(proj)

        vid = Video(
            project_id=proj.id,
            filename="test.mp4",
            file_path="C:/dummy/test.mp4",
            file_size_bytes=1000,
            duration_seconds=60.0
        )
        db.add(vid)
        await db.commit()
        await db.refresh(vid)

        from app.ai.highlights.highlight_analyzer import EnrichedHighlightCandidate
        sb = CandidateScorer.score_candidate("Test excerpt", "Test hook", 30.0)
        candidate_item = EnrichedHighlightCandidate(
            start_time=10.0,
            end_time=40.0,
            duration_seconds=30.0,
            title="Saved Candidate",
            hook="Test hook",
            summary="Test summary",
            reason="Test reason",
            category="general",
            key_quote="Test hook",
            transcript_excerpt="Test excerpt",
            overall_score=88,
            score_breakdown=sb
        )

        saved = await HighlightService.save_candidates(
            db=db,
            video_id=vid.id,
            project_id=proj.id,
            candidates=[candidate_item]
        )
        assert len(saved) == 1
        assert saved[0].id is not None
        assert saved[0].title == "Saved Candidate"
        candidate_id = saved[0].id

        # Query back
        loaded = await HighlightService.get_by_id(db, candidate_id)
        assert loaded is not None
        assert loaded.overall_score == 88


# 16. Approval and rejection state machine
@pytest.mark.asyncio
async def test_approval_and_rejection_state_machine():
    async with async_session_factory() as db:
        proj = Project(name="Approval Test Project")
        db.add(proj)
        await db.commit()

        vid = Video(project_id=proj.id, filename="v.mp4", file_path="C:/v.mp4", file_size_bytes=1000, duration_seconds=60.0)
        db.add(vid)
        await db.commit()

        candidate = HighlightCandidate(
            project_id=proj.id,
            video_id=vid.id,
            start_time=5.0,
            end_time=35.0,
            duration_seconds=30.0,
            title="State Machine Test",
            overall_score=80,
            status="discovered"
        )
        db.add(candidate)
        await db.commit()
        await db.refresh(candidate)

        # Approve
        app_cand = await HighlightService.update_status(db, candidate.id, "approved")
        assert app_cand.status == "approved"

        # Reject
        rej_cand = await HighlightService.update_status(db, candidate.id, "rejected")
        assert rej_cand.status == "rejected"


# 17. Manual timestamp editing
@pytest.mark.asyncio
async def test_manual_timestamp_editing():
    async with async_session_factory() as db:
        proj = Project(name="Edit Test Project")
        db.add(proj)
        await db.commit()

        vid = Video(project_id=proj.id, filename="v.mp4", file_path="C:/v.mp4", file_size_bytes=1000, duration_seconds=60.0)
        db.add(vid)
        await db.commit()

        candidate = HighlightCandidate(
            project_id=proj.id,
            video_id=vid.id,
            start_time=10.0,
            end_time=40.0,
            duration_seconds=30.0,
            title="Before Edit",
            status="discovered"
        )
        db.add(candidate)
        await db.commit()
        await db.refresh(candidate)

        # Edit start and end
        updated = await HighlightService.update_candidate(
            db=db,
            candidate_id=candidate.id,
            start_time=12.5,
            end_time=45.0,
            title="After Edit"
        )
        assert updated.start_time == 12.5
        assert updated.end_time == 45.0
        assert updated.duration_seconds == 32.5
        assert updated.title == "After Edit"
        assert updated.status == "edited"


# 18. Background job integration
@pytest.mark.asyncio
async def test_analyze_highlights_job_lifecycle():
    jm = JobManager.get_instance()
    await jm.start()

    async with async_session_factory() as db:
        proj = Project(name="Highlight Job Project")
        db.add(proj)
        await db.commit()
        await db.refresh(proj)

        vid = Video(
            project_id=proj.id,
            filename="speech.mp4",
            file_path="C:/dummy/speech.mp4",
            file_size_bytes=1000,
            duration_seconds=45.0
        )
        db.add(vid)
        await db.commit()
        await db.refresh(vid)

        # Add a transcript
        tr = Transcript(
            video_id=vid.id,
            language="en",
            status="completed",
            full_text="Why do creators struggle to grow? Because hooks are critical. Here is how to fix it."
        )
        db.add(tr)
        await db.commit()
        await db.refresh(tr)

        # Add transcript segments with words
        seg1 = TranscriptSegment(
            transcript_id=tr.id,
            segment_index=0,
            start_time=0.0,
            end_time=15.0,
            text="Why do creators struggle to grow?",
            words=[
                {"word": "Why", "start": 0.0, "end": 0.5, "prob": 0.9},
                {"word": "do", "start": 0.5, "end": 1.0, "prob": 0.9},
                {"word": "creators", "start": 1.0, "end": 2.0, "prob": 0.9},
                {"word": "struggle?", "start": 2.0, "end": 3.0, "prob": 0.9}
            ]
        )
        seg2 = TranscriptSegment(
            transcript_id=tr.id,
            segment_index=1,
            start_time=15.0,
            end_time=35.0,
            text="Because hooks are critical. Here is how to fix it.",
            words=[
                {"word": "Because", "start": 15.0, "end": 16.0, "prob": 0.9},
                {"word": "hooks", "start": 16.0, "end": 17.0, "prob": 0.9},
                {"word": "are", "start": 17.0, "end": 18.0, "prob": 0.9},
                {"word": "critical.", "start": 18.0, "end": 19.0, "prob": 0.9}
            ]
        )
        db.add_all([seg1, seg2])
        await db.commit()

        video_id = vid.id
        project_id = proj.id

    job = await jm.enqueue_job(
        job_type="analyze_highlights",
        project_id=project_id,
        params={
            "video_id": video_id,
            "target_duration_min": 10.0,
            "target_duration_max": 40.0,
            "max_candidates": 3
        }
    )
    assert job.status in ["queued", "running", "completed"]

    # Wait for completion
    for _ in range(50):
        await asyncio.sleep(0.2)
        async with async_session_factory() as db:
            j = await db.get(Job, job.id)
            if j.status in ["completed", "failed"]:
                assert j.status == "completed", f"Job failed: {j.error_message}"
                assert j.progress_percent == 100
                assert j.result_data["candidates_count"] > 0
                break


# 19. Job cancellation
@pytest.mark.asyncio
async def test_job_cancellation_token():
    token = CancellationToken("test-job-cancel-id")
    assert token.is_cancelled is False
    token.cancel()
    assert token.is_cancelled is True


# 20. Application restart recovery
@pytest.mark.asyncio
async def test_application_restart_persistence():
    async with async_session_factory() as db:
        proj = Project(name="Restart Test Project")
        db.add(proj)
        await db.commit()

        vid = Video(project_id=proj.id, filename="restart.mp4", file_path="C:/v.mp4", file_size_bytes=1000, duration_seconds=60.0)
        db.add(vid)
        await db.commit()

        candidate = HighlightCandidate(
            project_id=proj.id,
            video_id=vid.id,
            start_time=5.0,
            end_time=35.0,
            duration_seconds=30.0,
            title="Persisted Across Shutdown",
            overall_score=85
        )
        db.add(candidate)
        await db.commit()
        cand_id = candidate.id

    # Simulate shutdown
    await engine.dispose()

    # Re-initialize
    await init_db()
    async with async_session_factory() as db:
        reloaded = await HighlightService.get_by_id(db, cand_id)
        assert reloaded is not None
        assert reloaded.title == "Persisted Across Shutdown"
        assert reloaded.overall_score == 85


# 21. API integration
@pytest.mark.asyncio
async def test_phase5_api_endpoints():
    token = "test-token-phase5"
    os.environ["CLIPFORGE_SESSION_TOKEN"] = token

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"x-session-token": token}

        # 1. LLM Models
        res_models = await ac.get("/api/ai/llm/models", headers=headers)
        assert res_models.status_code == 200
        models_data = res_models.json()
        assert len(models_data) >= 3

        # 2. LLM Status
        res_status = await ac.get("/api/ai/llm/status", headers=headers)
        assert res_status.status_code == 200
        status_data = res_status.json()
        assert "llama_binary_available" in status_data

        # 3. Create Project & Video for Highlights
        res_proj = await ac.post("/api/projects", json={"name": "API Highlight Proj"}, headers=headers)
        assert res_proj.status_code == 201
        proj_id = res_proj.json()["id"]

        async with async_session_factory() as db:
            vid = Video(
                project_id=proj_id,
                filename="api_test.mp4",
                file_path="C:/dummy/api_test.mp4",
                file_size_bytes=1000,
                duration_seconds=60.0
            )
            db.add(vid)
            await db.commit()
            await db.refresh(vid)
            vid_id = vid.id

            cand = HighlightCandidate(
                project_id=proj_id,
                video_id=vid_id,
                start_time=10.0,
                end_time=40.0,
                duration_seconds=30.0,
                title="API Candidate",
                overall_score=82
            )
            db.add(cand)
            await db.commit()
            await db.refresh(cand)
            cand_id = cand.id

        # 4. List candidates
        res_cands = await ac.get(f"/api/videos/{vid_id}/highlight-candidates", headers=headers)
        assert res_cands.status_code == 200
        assert len(res_cands.json()) >= 1

        # 5. Approve candidate
        res_app = await ac.post(f"/api/highlights/{cand_id}/approve", headers=headers)
        assert res_app.status_code == 200
        assert res_app.json()["status"] == "approved"

        # 6. Reject candidate
        res_rej = await ac.post(f"/api/highlights/{cand_id}/reject", headers=headers)
        assert res_rej.status_code == 200
        assert res_rej.json()["status"] == "rejected"

        # 7. Edit candidate
        res_edit = await ac.patch(
            f"/api/highlights/{cand_id}",
            json={"start_time": 15.0, "end_time": 45.0, "title": "Updated API Title"},
            headers=headers
        )
        assert res_edit.status_code == 200
        assert res_edit.json()["start_time"] == 15.0
        assert res_edit.json()["title"] == "Updated API Title"


# 22. Real local LLM inference (executed only if model is installed)
@pytest.mark.asyncio
async def test_real_llm_inference_if_installed():
    """
    Executes actual local LLM inference if any GGUF model is downloaded and installed.
    If no model is installed, explicitly skips as mandated by prompt guidelines.
    """
    installed_models = [m for m in ModelRegistry.list_models() if LLMModelManager.check_model_status(m.id).is_installed]

    if not installed_models:
        pytest.skip("No local GGUF model installed on disk. Real-inference test skipped explicitly per specification.")

    test_model = installed_models[0]
    prompt = "Identify the main topic of this sentence: 'ClipForge AI automates vertical video highlights.'"
    output = await LLMInferenceManager.get_instance().execute_inference(
        model_id=test_model.id,
        prompt=prompt,
        max_tokens=64
    )
    assert len(output) > 0
    print(f"Real LLM Inference Output ({test_model.id}): {output[:100]}...")
