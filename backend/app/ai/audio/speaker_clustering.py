"""
ClipForge AI - Local Speaker Clustering Engine
Performs Agglomerative Hierarchical Clustering (AHC) with average linkage (UPGMA)
and cosine distance on 512-dimensional speaker embeddings.
Pure NumPy, zero external ML dependencies.
"""

from dataclasses import dataclass, field
import logging
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

logger = logging.getLogger("clipforge.ai.audio.clustering")

DEFAULT_DISTANCE_THRESHOLD = 0.65
MIN_SPEAKERS_DEFAULT = 1
MAX_SPEAKERS_DEFAULT = 10
DEFAULT_OUTLIER_THRESHOLD = 0.35  # Cosine similarity below this indicates low confidence


@dataclass
class ClusteringConfig:
    """Configuration parameters for speaker clustering."""
    distance_threshold: float = DEFAULT_DISTANCE_THRESHOLD
    min_speakers: int = MIN_SPEAKERS_DEFAULT
    max_speakers: int = MAX_SPEAKERS_DEFAULT
    expected_speakers: Optional[int] = None
    outlier_threshold: float = DEFAULT_OUTLIER_THRESHOLD


@dataclass
class ClusteringResult:
    """Output structure of speaker clustering."""
    labels: np.ndarray  # Shape: (N,), int cluster indices (0..K-1), or -1 for unassigned
    centroids: np.ndarray  # Shape: (K, D), float32 L2-normalized cluster centroids
    confidences: np.ndarray  # Shape: (N,), float32 similarity to assigned centroid [0, 1]
    cluster_counts: Dict[int, int]  # Cluster ID -> count of segments
    num_clusters: int
    silhouette_score: Optional[float] = None


class SpeakerClusterer:
    """
    Local Agglomerative Hierarchical Clustering (AHC) using cosine distance and average linkage.
    Identifies distinct speakers from temporal speech embedding vectors.
    """

    def __init__(self, config: Optional[ClusteringConfig] = None) -> None:
        self.config = config or ClusteringConfig()

    def cluster(
        self,
        embeddings: np.ndarray,
        expected_speakers: Optional[int] = None,
        distance_threshold: Optional[float] = None,
    ) -> ClusteringResult:
        """
        Cluster N speaker embeddings into K speakers.
        
        Args:
            embeddings: (N, D) float32 matrix of L2-normalized embeddings.
            expected_speakers: optional explicit target speaker count.
            distance_threshold: optional cosine distance cutoff threshold.
            
        Returns:
            ClusteringResult containing labels, centroids, confidences, and metrics.
        """
        if embeddings is None or len(embeddings) == 0:
            return ClusteringResult(
                labels=np.array([], dtype=int),
                centroids=np.zeros((0, 512), dtype=np.float32),
                confidences=np.array([], dtype=np.float32),
                cluster_counts={},
                num_clusters=0,
                silhouette_score=None,
            )

        X = np.asarray(embeddings, dtype=np.float32)
        if X.ndim == 1:
            X = np.expand_dims(X, axis=0)

        n, dim = X.shape

        # Normalize rows to unit sphere if not already normalized
        norms = np.linalg.norm(X, axis=1, keepdims=True)
        X = X / np.maximum(norms, 1e-12)

        # Single embedding edge case
        if n == 1:
            return ClusteringResult(
                labels=np.array([0], dtype=int),
                centroids=X.copy(),
                confidences=np.array([1.0], dtype=np.float32),
                cluster_counts={0: 1},
                num_clusters=1,
                silhouette_score=None,
            )

        threshold = (
            distance_threshold
            if distance_threshold is not None
            else self.config.distance_threshold
        )
        target_k = (
            expected_speakers
            if expected_speakers is not None
            else self.config.expected_speakers
        )
        min_speakers = self.config.min_speakers
        max_speakers = self.config.max_speakers

        # Run Agglomerative Hierarchical Clustering
        labels, centroids = self._agglomerative_hierarchical_clustering(
            X,
            distance_threshold=threshold,
            expected_speakers=target_k,
            min_speakers=min_speakers,
            max_speakers=max_speakers,
        )

        num_clusters = len(centroids)

        # Calculate per-segment confidence (cosine similarity to assigned centroid)
        confidences = np.zeros(n, dtype=np.float32)
        for i in range(n):
            lbl = labels[i]
            if 0 <= lbl < num_clusters:
                sim = float(np.dot(X[i], centroids[lbl]))
                confidences[i] = float(np.clip(sim, 0.0, 1.0))
            else:
                confidences[i] = 0.0

        # Tally cluster counts
        cluster_counts: Dict[int, int] = {}
        for lbl in labels:
            if lbl >= 0:
                cluster_counts[lbl] = cluster_counts.get(lbl, 0) + 1

        # Calculate silhouette score if 2 <= K < N
        silhouette = None
        if 2 <= num_clusters < n:
            silhouette = self.compute_silhouette_score(X, labels)

        return ClusteringResult(
            labels=labels,
            centroids=centroids,
            confidences=confidences,
            cluster_counts=cluster_counts,
            num_clusters=num_clusters,
            silhouette_score=silhouette,
        )

    def _agglomerative_hierarchical_clustering(
        self,
        X: np.ndarray,
        distance_threshold: float,
        expected_speakers: Optional[int],
        min_speakers: int,
        max_speakers: int,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Pure NumPy UPGMA (Unweighted Pair Group Method with Arithmetic Mean) clustering.
        """
        n, dim = X.shape
        max_nodes = 2 * n

        # Preallocate distance matrix for up to 2n nodes
        dist_matrix = np.full((max_nodes, max_nodes), np.inf, dtype=np.float32)

        # Initial pairwise cosine distances: 1.0 - X @ X.T
        initial_dists = np.clip(1.0 - np.dot(X, X.T), 0.0, 2.0)
        dist_matrix[:n, :n] = initial_dists
        for i in range(n):
            dist_matrix[i, i] = np.inf

        clusters: Dict[int, List[int]] = {i: [i] for i in range(n)}
        sizes = np.zeros(max_nodes, dtype=np.int32)
        sizes[:n] = 1
        active = set(range(n))
        next_node = n

        target_k = expected_speakers if expected_speakers is not None else min_speakers

        while len(active) > target_k:
            active_list = sorted(active)
            idx = np.array(active_list, dtype=np.int32)
            sub = dist_matrix[np.ix_(idx, idx)]

            # Only inspect strictly upper triangular elements to find min distance
            triu_i, triu_j = np.triu_indices(len(active_list), k=1)
            if len(triu_i) == 0:
                break

            triu_vals = sub[triu_i, triu_j]
            min_pos = int(np.argmin(triu_vals))
            min_d = float(triu_vals[min_pos])

            # Stop condition 1: No valid distances left (all inf)
            if np.isinf(min_d):
                break

            # Stop condition 2: In threshold mode, distance exceeds cutoff and K <= max_speakers
            if expected_speakers is None:
                if min_d > distance_threshold and len(active) <= max_speakers:
                    break

            c_a = active_list[triu_i[min_pos]]
            c_b = active_list[triu_j[min_pos]]

            new_c = next_node
            next_node += 1

            clusters[new_c] = clusters[c_a] + clusters[c_b]
            s_a = int(sizes[c_a])
            s_b = int(sizes[c_b])
            s_new = s_a + s_b
            sizes[new_c] = s_new

            active.remove(c_a)
            active.remove(c_b)

            # UPGMA Lance-Williams update for average linkage:
            # d(A u B, K) = (s_A * d(A, K) + s_B * d(B, K)) / (s_A + s_B)
            if active:
                rem_arr = np.array(list(active), dtype=np.int32)
                d_a = dist_matrix[c_a, rem_arr]
                d_b = dist_matrix[c_b, rem_arr]
                d_new = (s_a * d_a + s_b * d_b) / float(s_new)
                dist_matrix[new_c, rem_arr] = d_new
                dist_matrix[rem_arr, new_c] = d_new

            dist_matrix[new_c, new_c] = np.inf
            dist_matrix[c_a, :] = np.inf
            dist_matrix[:, c_a] = np.inf
            dist_matrix[c_b, :] = np.inf
            dist_matrix[:, c_b] = np.inf

            active.add(new_c)

        # Enforce max_speakers cap if clustering didn't stop naturally
        while len(active) > max_speakers:
            active_list = sorted(active)
            idx = np.array(active_list, dtype=np.int32)
            sub = dist_matrix[np.ix_(idx, idx)]
            triu_i, triu_j = np.triu_indices(len(active_list), k=1)
            if len(triu_i) == 0:
                break
            min_pos = int(np.argmin(sub[triu_i, triu_j]))
            c_a = active_list[triu_i[min_pos]]
            c_b = active_list[triu_j[min_pos]]

            new_c = next_node
            next_node += 1
            clusters[new_c] = clusters[c_a] + clusters[c_b]
            s_a = int(sizes[c_a])
            s_b = int(sizes[c_b])
            s_new = s_a + s_b
            sizes[new_c] = s_new
            active.remove(c_a)
            active.remove(c_b)
            if active:
                rem_arr = np.array(list(active), dtype=np.int32)
                d_new = (s_a * dist_matrix[c_a, rem_arr] + s_b * dist_matrix[c_b, rem_arr]) / float(s_new)
                dist_matrix[new_c, rem_arr] = d_new
                dist_matrix[rem_arr, new_c] = d_new
            dist_matrix[new_c, new_c] = np.inf
            dist_matrix[c_a, :] = np.inf
            dist_matrix[:, c_a] = np.inf
            dist_matrix[c_b, :] = np.inf
            dist_matrix[:, c_b] = np.inf
            active.add(new_c)

        # Sort clusters by size (largest speaker receives label 0, then 1, ...)
        active_sorted = sorted(active, key=lambda c: len(clusters[c]), reverse=True)
        labels = np.zeros(n, dtype=int)
        centroids_list: List[np.ndarray] = []

        for new_label, c in enumerate(active_sorted):
            members = clusters[c]
            labels[members] = new_label

            # Compute L2-normalized centroid
            c_vec = np.mean(X[members], axis=0)
            c_norm = float(np.linalg.norm(c_vec))
            if c_norm > 1e-12:
                c_vec = c_vec / c_norm
            centroids_list.append(c_vec.astype(np.float32))

        centroids = np.array(centroids_list, dtype=np.float32)
        return labels, centroids

    @staticmethod
    def compute_silhouette_score(X: np.ndarray, labels: np.ndarray) -> float:
        """
        Compute mean silhouette coefficient for clustering quality assessment.
        Value in [-1.0, 1.0], higher indicates tighter, better-separated clusters.
        """
        n = len(X)
        unique_labels = [lbl for lbl in np.unique(labels) if lbl >= 0]
        if len(unique_labels) < 2 or n < 2:
            return 0.0

        # Pairwise cosine distances
        dist = np.clip(1.0 - np.dot(X, X.T), 0.0, 2.0)

        silhouette_scores = []
        for i in range(n):
            lbl_i = labels[i]
            same_cluster_indices = np.where(labels == lbl_i)[0]

            # a(i): mean intra-cluster distance
            if len(same_cluster_indices) <= 1:
                a_i = 0.0
            else:
                intra_dists = dist[i, same_cluster_indices]
                a_i = float(np.sum(intra_dists) / (len(same_cluster_indices) - 1))

            # b(i): minimum mean distance to any other cluster
            b_i = float("inf")
            for other_lbl in unique_labels:
                if other_lbl == lbl_i:
                    continue
                other_indices = np.where(labels == other_lbl)[0]
                if len(other_indices) > 0:
                    mean_other_dist = float(np.mean(dist[i, other_indices]))
                    if mean_other_dist < b_i:
                        b_i = mean_other_dist

            max_ab = max(a_i, b_i)
            if max_ab > 0:
                s_i = (b_i - a_i) / max_ab
            else:
                s_i = 0.0
            silhouette_scores.append(s_i)

        return float(np.mean(silhouette_scores))

    @staticmethod
    def reassign_speaker(labels: np.ndarray, from_label: int, to_label: int) -> np.ndarray:
        """User manual override helper to merge or reassign speaker turns."""
        updated = labels.copy()
        updated[updated == from_label] = to_label
        return updated
