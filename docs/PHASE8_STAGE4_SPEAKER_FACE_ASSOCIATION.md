# ClipForge AI — Multi-Turn Speaker-Face Identity Association

## Mathematical Modeling, Negative Penalties & User Override Safeguards

### 1. The Global Identity Problem

Acoustic speaker diarization (Phase 8 Stage 3) produces temporal speech turns labeled with cluster identifiers:
$$\mathcal{S} = \{S_1, S_2, \dots, S_M\}$$
Visual face tracking (Phase 6) produces continuous face tracks:
$$\mathcal{T} = \{T_1, T_2, \dots, T_K\}$$

The objective of Concept B is to find the optimal assignment matrix $A \in \{0, 1\}^{M \times K}$ mapping each acoustic speaker $S_i$ to a visible face track $T_j$ (or explicitly designating $S_i$ as an off-screen speaker).

---

### 2. Multi-Turn Aggregation & Formulation

Single-turn coincidence is insufficient in multi-speaker video, because a silent listener may nod, smile, or open their mouth momentarily while another person is speaking. To ensure robust matching, ClipForge AI aggregates evidence across all dialogue turns.

#### 1. Positive Overlap Matrix
For speaker $S_i$ having $N_i$ acoustic turns $\{u_1^{(i)}, u_2^{(i)}, \dots, u_{N_i}^{(i)}\}$:
$$O(S_i, T_j) = \sum_{k=1}^{N_i} \text{Duration}\left(u_k^{(i)} \cap \text{ActiveSegments}(T_j)\right)$$

#### 2. Negative Co-occurrence Penalty
If face track $T_j$ was vocalizing during turns belonging to *competing* speakers $S_m$ ($m \ne i$), this provides strong negative evidence that $T_j$ is not $S_i$:
$$P_{\text{neg}}(S_i, T_j) = \sum_{m \ne i} \sum_{l=1}^{N_m} \text{Duration}\left(u_l^{(m)} \cap \text{ActiveSegments}(T_j)\right)$$

#### 3. Turn Consistency Ratio
We calculate the fraction of speaker $S_i$'s total turns where face track $T_j$ was actively vocalizing for $\ge 30\%$ of the turn duration:
$$C(S_i, T_j) = \frac{\sum_{k=1}^{N_i} \mathbb{I}\left[\text{Overlap}(u_k^{(i)}, T_j) \ge 0.30 \cdot \text{Duration}(u_k^{(i)})\right]}{N_i}$$

#### 4. Net Association Score
$$\text{Score}(S_i, T_j) = \frac{\max\left(0, O(S_i, T_j) - 0.50 \cdot P_{\text{neg}}(S_i, T_j)\right)}{\text{TotalDuration}(S_i)}$$

---

### 3. Classification Status Tiers

Associations are categorized into four explicit status tiers:

1. **`confirmed`**:
   - $N_i \ge 2$ speaker turns.
   - Turn consistency $C(S_i, T_j) \ge 0.70$.
   - Net association score $\text{Score}(S_i, T_j) \ge 0.50$.
   - High-confidence match suitable for automatic camera reframing.

2. **`provisional`**:
   - $N_i = 1$ speaker turn, or moderate consistency ($0.35 \le C < 0.70$).
   - Net score in range $[0.30, 0.50)$.
   - Displayed with provisional badge in UI until more turns are observed.

3. **`off_screen`**:
   - Best net score $\text{Score}(S_i, T_j) < 0.25$, or no visible face active during turns.
   - Assigned `face_track_id = None`, `is_off_screen = True`.
   - Never force-matched to a silent listener.

4. **`unknown` / Ambiguous**:
   - Multiple face tracks have similar scores within 0.05 of each other (e.g. choir or simultaneous chorus).

---

### 4. User Manual Overrides

ClipForge AI strictly guarantees that user manual overrides are permanently preserved:
- When a user assigns $S_i \to T_j$ or marks $S_i$ as `off_screen` via the frontend UI or API (`PUT /api/videos/{video_id}/speakers/{speaker_id}/associate`):
  - Database record `SpeakerFaceAssociation.is_manual` is set to `True`.
  - Confidence is locked at `1.0`.
  - The fusion and clustering engine checks manual overrides before running bipartite matching, permanently excluding assigned speakers and tracks from algorithmic re-clustering.
