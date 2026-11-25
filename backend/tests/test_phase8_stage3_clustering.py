"""
ClipForge AI - Phase 8 Stage 3 Speaker Clustering Test Suite
Tests pure NumPy Agglomerative Hierarchical Clustering (AHC) with average linkage and cosine distance.
"""

from pathlib import Path
import sys
import numpy as np
import pytest

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.ai.audio.speaker_clustering import (
    ClusteringConfig,
    ClusteringResult,
    SpeakerClusterer,
)


class TestSpeakerClusterer:
    """Tests for pure NumPy Agglomerative Hierarchical Clustering."""

    @pytest.fixture
    def clusterer(self):
        return SpeakerClusterer()

    def test_empty_embeddings(self, clusterer):
        res = clusterer.cluster(np.array([], dtype=np.float32))
        assert res.num_clusters == 0
        assert len(res.labels) == 0
        assert res.centroids.shape == (0, 512)

    def test_single_embedding(self, clusterer):
        emb = np.random.randn(512).astype(np.float32)
        emb /= np.linalg.norm(emb)
        res = clusterer.cluster(emb)
        assert res.num_clusters == 1
        assert len(res.labels) == 1
        assert res.labels[0] == 0
        assert np.allclose(res.centroids[0], emb)
        assert res.confidences[0] == 1.0
        assert res.cluster_counts == {0: 1}

    def test_two_distinct_speakers_clustering(self, clusterer):
        D = 512
        np.random.seed(101)
        s1 = np.random.randn(D); s1 /= np.linalg.norm(s1)
        s2 = np.random.randn(D); s2 /= np.linalg.norm(s2)

        # 25 samples from speaker 1, 15 samples from speaker 2
        X = []
        for _ in range(25):
            v = s1 + 0.05 * np.random.randn(D)
            X.append(v / np.linalg.norm(v))
        for _ in range(15):
            v = s2 + 0.05 * np.random.randn(D)
            X.append(v / np.linalg.norm(v))
        X = np.array(X, dtype=np.float32)

        res = clusterer.cluster(X, distance_threshold=0.65)
        assert res.num_clusters == 2
        assert len(res.labels) == 40
        # Speaker 1 has 25 samples, so it should be cluster 0
        assert np.sum(res.labels == 0) == 25
        assert np.sum(res.labels == 1) == 15
        # Verify perfect purity
        assert len(np.unique(res.labels[:25])) == 1
        assert len(np.unique(res.labels[25:])) == 1
        assert res.labels[0] == 0
        assert res.labels[25] == 1
        # Silhouette score must be positive and strong
        assert res.silhouette_score is not None
        assert res.silhouette_score > 0.4

    def test_expected_speakers_parameter(self, clusterer):
        D = 512
        np.random.seed(202)
        s1 = np.random.randn(D); s1 /= np.linalg.norm(s1)
        s2 = np.random.randn(D); s2 /= np.linalg.norm(s2)
        s3 = np.random.randn(D); s3 /= np.linalg.norm(s3)

        X = []
        for _ in range(10):
            X.append(s1 + 0.03 * np.random.randn(D))
        for _ in range(10):
            X.append(s2 + 0.03 * np.random.randn(D))
        for _ in range(10):
            X.append(s3 + 0.03 * np.random.randn(D))
        X = np.array(X, dtype=np.float32)

        res = clusterer.cluster(X, expected_speakers=3)
        assert res.num_clusters == 3
        assert len(res.labels) == 30
        assert res.cluster_counts == {0: 10, 1: 10, 2: 10}

    def test_confidence_values_bounded(self, clusterer):
        D = 512
        np.random.seed(303)
        X = np.random.randn(20, D).astype(np.float32)
        res = clusterer.cluster(X)
        assert np.all(res.confidences >= 0.0)
        assert np.all(res.confidences <= 1.0)

    def test_silhouette_computation(self, clusterer):
        D = 512
        np.random.seed(404)
        s1 = np.random.randn(D); s1 /= np.linalg.norm(s1)
        s2 = np.random.randn(D); s2 /= np.linalg.norm(s2)
        X = np.vstack([
            s1 + 0.01 * np.random.randn(5, D),
            s2 + 0.01 * np.random.randn(5, D),
        ]).astype(np.float32)
        norms = np.linalg.norm(X, axis=1, keepdims=True)
        X /= norms
        labels = np.array([0]*5 + [1]*5, dtype=int)
        score = clusterer.compute_silhouette_score(X, labels)
        assert score > 0.8  # Very tight clusters

    def test_reassign_speaker(self, clusterer):
        labels = np.array([0, 0, 1, 1, 2], dtype=int)
        reassigned = clusterer.reassign_speaker(labels, from_label=2, to_label=1)
        assert np.array_equal(reassigned, np.array([0, 0, 1, 1, 1], dtype=int))
