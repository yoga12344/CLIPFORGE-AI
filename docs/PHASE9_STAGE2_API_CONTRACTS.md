# Phase 9 Stage 2: Composition REST API Contracts

## 1. Route Hierarchy

All composition endpoints are mounted at `/api/compositions` under the FastAPI application router.
Security is enforced using the standard header `x-session-token: clipforge-secure-session-token` or session authentication.

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/compositions` | Create a new composition (auto-creates Version 1) |
| `GET` | `/api/compositions` | List compositions for a project (with pagination) |
| `GET` | `/api/compositions/{id}` | Get composition details with its latest version |
| `GET` | `/api/compositions/{id}/versions` | List all historical versions of a composition |
| `GET` | `/api/compositions/{id}/versions/{version_number}` | Get a specific historical version snapshot |
| `POST` | `/api/compositions/{id}/versions` | Create a new version snapshot (OCC protected) |
| `POST` | `/api/compositions/{id}/versions/{version_number}/restore` | Non-destructive rollback: restore an earlier version |
| `PATCH` | `/api/compositions/{id}` | Update composition metadata (title, description, status) |
| `DELETE` | `/api/compositions/{id}` | Delete a composition and cascade to all versions/renders |
| `POST` | `/api/compositions/validate` | Dry-run semantic and schema validation of a `CompositionSpec` |
| `GET` | `/api/compositions/projects/{project_id}/assets` | List registered project assets available for composition |

---

## 2. Request and Response Schemas

### 2.1 Create Composition
**Endpoint**: `POST /api/compositions`

**Request Body** (`CreateCompositionRequest`):
```json
{
  "project_id": "proj_01J...",
  "source_video_id": "vid_01J...",
  "title": "Viral Hook Clip #1",
  "description": "Auto-generated 9:16 portrait reframe with split layout",
  "spec": {
    "schema_version": "1.0.0",
    "metadata": {
      "id": "comp_01J...",
      "project_id": "proj_01J...",
      "title": "Viral Hook Clip #1"
    },
    "source_media": {
      "video_id": "vid_01J...",
      "logical_uri": "asset://videos/vid_01J...",
      "width": 1920,
      "height": 1080,
      "fps": {"numerator": 30, "denominator": 1},
      "duration_us": 60000000
    },
    "timeline": {
      "timebase": {"numerator": 30, "denominator": 1},
      "source_boundary": {"in_point_us": 0, "out_point_us": 60000000},
      "composition_boundary": {"in_point_us": 10000000, "out_point_us": 40000000}
    },
    "layout": {
      "topology": "single_full_frame",
      "aspect_ratio": "9:16"
    },
    "camera_plan": {
      "smoothing_strength": 0.85,
      "min_hold_duration_us": 1200000,
      "max_velocity_per_sec": 0.40
    },
    "subtitles": {
      "style_preset": "bold_impact",
      "font_family": "Montserrat",
      "font_size": 42
    },
    "overlays": {},
    "audio": {
      "loudness": {"target_lufs": -14.0, "max_true_peak_dbtp": -1.0}
    },
    "delivery": {
      "aspect_ratio": "9:16",
      "width": 1080,
      "height": 1920,
      "fps": {"numerator": 30, "denominator": 1}
    }
  }
}
```

**Response (HTTP 201 Created)** (`CompositionDetailResponse`):
```json
{
  "id": "comp_01J...",
  "project_id": "proj_01J...",
  "source_video_id": "vid_01J...",
  "title": "Viral Hook Clip #1",
  "description": "Auto-generated 9:16 portrait reframe with split layout",
  "status": "draft",
  "current_version_number": 1,
  "created_at": "2026-11-22T11:00:00Z",
  "updated_at": "2026-11-22T11:00:00Z",
  "latest_version": {
    "id": "ver_01J...",
    "composition_id": "comp_01J...",
    "version_number": 1,
    "parent_version_id": null,
    "schema_version": "1.0.0",
    "title": "Initial version",
    "change_description": "Composition created",
    "author_type": "user",
    "spec": { ... },
    "content_hash": "a1b2c3d4...",
    "created_at": "2026-11-22T11:00:00Z"
  }
}
```

---

### 2.2 Create New Version (OCC Protected)
**Endpoint**: `POST /api/compositions/{id}/versions`

**Request Body** (`CreateCompositionVersionRequest`):
```json
{
  "expected_version_number": 1,
  "title": "Adjusted safe area and subtitles",
  "change_description": "Moved subtitles upward to avoid TikTok bottom action buttons",
  "author_type": "user",
  "spec": { ... }
}
```

**Optimistic Concurrency Control (OCC) Error Response (HTTP 409 Conflict)**:
```json
{
  "detail": "Version conflict: expected version 1, but current version is 2. Please reload the latest composition."
}
```

---

### 2.3 Restore Earlier Version
**Endpoint**: `POST /api/compositions/{id}/versions/{version_number}/restore`

Restores the AST from historical `version_number` as a **brand new version** ($N + 1$), preserving all intermediate versions and maintaining audit trails.

**Response (HTTP 200 OK)** (`CompositionVersionResponse`):
```json
{
  "id": "ver_01J_NEW...",
  "composition_id": "comp_01J...",
  "version_number": 3,
  "parent_version_id": "ver_01J_OLD...",
  "schema_version": "1.0.0",
  "title": "Restore to version 1",
  "change_description": "Restored from version 1",
  "author_type": "user",
  "spec": { ... },
  "content_hash": "a1b2c3d4...",
  "created_at": "2026-11-22T11:05:00Z"
}
```

---

### 2.4 Validate Composition (Dry Run)
**Endpoint**: `POST /api/compositions/validate`

Performs structural and semantic checks without writing to disk or database.

**Response (HTTP 200 OK)** (`CompositionValidationResponse`):
```json
{
  "is_valid": true,
  "errors": [],
  "warnings": [
    {
      "code": "SAFE_AREA_SUBTITLE_PROXIMITY",
      "message": "Subtitles are within 5% of bottom margin",
      "field": "subtitles.margin_bottom"
    }
  ]
}
```
