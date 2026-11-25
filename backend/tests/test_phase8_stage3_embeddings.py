"""
ClipForge AI - Phase 8 Stage 3 Speaker Embeddings Test Suite
Tests Kaldi-compliant FBankExtractor and 3D-Speaker CAM++ SpeakerEmbeddingExtractor.
"""

from pathlib import Path
import sys
import numpy as np
import pytest

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.ai.audio.speaker_embeddings import (
    FBankConfig,
    FBankExtractor,
    SpeakerEmbeddingExtractor,
    EXPECTED_EMBEDDING_DIM,
    TARGET_SAMPLE_RATE,
)


class TestFBankExtractor:
    """Tests for pure NumPy Kaldi-compliant Mel Filterbank extractor."""

    def test_default_config_properties(self):
        extractor = FBankExtractor()
        assert extractor.sample_rate == 16000
        assert extractor.num_mel_bins == 80
        assert extractor.frame_length == 400  # 25ms @ 16kHz
        assert extractor.frame_shift == 160   # 10ms @ 16kHz
        assert extractor.n_fft == 512
        assert extractor._filterbank.shape == (257, 80)
        assert extractor._window.shape == (400,)

    def test_mel_hz_inversion(self):
        extractor = FBankExtractor()
        for hz in [20.0, 100.0, 1000.0, 4000.0, 7600.0]:
            mel = extractor._hz_to_mel(hz)
            reconstructed_hz = extractor._mel_to_hz(mel)
            assert abs(hz - reconstructed_hz) < 1e-3

    def test_window_types(self):
        for w_type in ["povey", "hamming", "hanning"]:
            cfg = FBankConfig(window_type=w_type)
            ext = FBankExtractor(cfg)
            assert ext._window.shape == (400,)
            assert np.all(ext._window >= 0.0)
            assert np.all(ext._window <= 1.0)

    def test_fbank_empty_or_none(self):
        ext = FBankExtractor()
        empty_feat = ext.compute_fbank(np.array([], dtype=np.float32))
        assert empty_feat.shape == (0, 80)

    def test_fbank_short_audio_padding(self):
        ext = FBankExtractor()
        # 100 samples < 400 frame length; should pad and produce 1 frame
        short_audio = np.ones(100, dtype=np.float32) * 0.5
        feat = ext.compute_fbank(short_audio)
        assert feat.ndim == 2
        assert feat.shape[1] == 80
        assert feat.shape[0] >= 1

    def test_fbank_on_one_second_audio(self):
        ext = FBankExtractor()
        # 1 second = 16000 samples -> (16000 - 400) // 160 + 1 = 98 frames
        audio = np.sin(2 * np.pi * 440 * np.linspace(0, 1.0, 16000)).astype(np.float32)
        feat = ext.compute_fbank(audio)
        assert feat.shape == (98, 80)
        assert feat.dtype == np.float32
        assert not np.isnan(feat).any()
        assert not np.isinf(feat).any()


class TestSpeakerEmbeddingExtractor:
    """Tests for 3D-Speaker CAM++ ONNX model inference and embedding extraction."""

    @pytest.fixture(scope="class")
    def extractor(self):
        ext = SpeakerEmbeddingExtractor.get_instance()
        return ext

    def test_capabilities(self, extractor):
        caps = extractor.get_capabilities()
        assert caps["model_name"] == "3D-Speaker CAM++ (VoxCeleb 16k)"
        assert caps["embedding_dimension"] == EXPECTED_EMBEDDING_DIM
        assert caps["sample_rate"] == TARGET_SAMPLE_RATE
        assert caps["execution_provider"] == "CPUExecutionProvider"
        assert caps["l2_normalized"] is True
        assert caps["model_available"] is True

    def test_singleton_consistency(self):
        ext1 = SpeakerEmbeddingExtractor.get_instance()
        ext2 = SpeakerEmbeddingExtractor.get_instance()
        assert ext1 is ext2

    def test_reject_none_and_empty(self, extractor):
        assert extractor.extract_embedding(None) is None
        assert extractor.extract_embedding(np.array([], dtype=np.float32)) is None

    def test_reject_too_short_audio(self, extractor):
        # 0.1s = 1600 samples < min_duration_sec 0.25s (4000 samples)
        short = np.random.randn(1600).astype(np.float32)
        assert extractor.extract_embedding(short, min_duration_sec=0.25) is None

    def test_reject_silent_audio(self, extractor):
        # 1s of pure zero silence
        silent = np.zeros(16000, dtype=np.float32)
        assert extractor.extract_embedding(silent) is None

    def test_embedding_shape_and_l2_norm(self, extractor):
        # 1.5s synthetic tone
        t = np.linspace(0, 1.5, int(1.5 * 16000), endpoint=False)
        audio = 0.5 * np.sin(2 * np.pi * 300 * t).astype(np.float32)

        emb = extractor.extract_embedding(audio)
        assert emb is not None
        assert emb.shape == (512,)
        assert emb.dtype == np.float32
        norm = float(np.linalg.norm(emb))
        assert abs(norm - 1.0) < 1e-5

    def test_batch_extraction(self, extractor):
        t = np.linspace(0, 1.0, 16000, endpoint=False)
        seg1 = 0.5 * np.sin(2 * np.pi * 200 * t).astype(np.float32)
        seg2 = 0.5 * np.sin(2 * np.pi * 500 * t).astype(np.float32)
        short_seg = np.zeros(500, dtype=np.float32)

        batch_results = extractor.extract_embeddings_batch([seg1, short_seg, seg2])
        assert len(batch_results) == 3
        assert batch_results[0] is not None
        assert batch_results[1] is None  # Too short / silent
        assert batch_results[2] is not None
        assert batch_results[0].shape == (512,)
        assert batch_results[2].shape == (512,)

    def test_cosine_similarity_and_distance_math(self, extractor):
        e1 = np.zeros(512, dtype=np.float32)
        e1[0] = 1.0
        e2 = np.zeros(512, dtype=np.float32)
        e2[0] = 1.0
        e3 = np.zeros(512, dtype=np.float32)
        e3[1] = 1.0

        # Identical
        assert abs(extractor.compute_cosine_similarity(e1, e2) - 1.0) < 1e-6
        assert abs(extractor.compute_cosine_distance(e1, e2) - 0.0) < 1e-6

        # Orthogonal
        assert abs(extractor.compute_cosine_similarity(e1, e3) - 0.0) < 1e-6
        assert abs(extractor.compute_cosine_distance(e1, e3) - 1.0) < 1e-6

        # Distance is symmetric
        assert extractor.compute_cosine_distance(e1, e3) == extractor.compute_cosine_distance(e3, e1)
