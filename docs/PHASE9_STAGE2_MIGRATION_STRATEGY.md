# Phase 9 Stage 2: Database Migration & Backward Compatibility Strategy

## 1. Migration Overview

ClipForge AI is an offline-first Windows desktop application utilizing an embedded SQLite database (`storage/clipforge_data/clipforge.db`).
Because the application runs locally without a remote DBA or external migration server, schema evolution must follow strict principles:
1. **Zero Data Loss**: Existing project records, imported videos, transcripts, face tracking trajectories, and exported clips from Phases 1–8 must remain completely unharmed.
2. **Backward Compatibility**: Any existing Phase 1–8 workflow (e.g. standard video import, Silero VAD analysis, CAM++ diarization, Light-ASD active speaker detection) must continue functioning without modification.
3. **Idempotent Initialization**: Schema setup scripts must safely execute on fresh installs and existing installations without crashing on pre-existing tables or constraints.

---

## 2. Table Creation and Foreign Key Strategy

### 2.1 New Phase 9 Entities
Phase 9 Stage 2 introduces 5 new database tables:
- `compositions`
- `composition_versions`
- `composition_assets`
- `composition_renders`
- `render_artifacts`

These tables are defined in `backend/app/db/models.py` using standard SQLAlchemy `Base` declarative mapping.
On application startup (`init_db()` in `backend/app/core/database.py`), SQLAlchemy runs:
```python
await conn.run_sync(Base.metadata.create_all)
```
In SQLite, `CREATE TABLE IF NOT EXISTS` creates missing tables while leaving existing tables untouched.

### 2.2 Foreign Key Constraints in SQLite
SQLite does not enforce foreign key constraints by default. To support `ON DELETE CASCADE` for compositions:
- SQLite connection event listener:
  ```python
  @event.listens_for(engine.sync_engine, "connect")
  def set_sqlite_pragma(dbapi_connection, connection_record):
      cursor = dbapi_connection.cursor()
      cursor.execute("PRAGMA foreign_keys=ON")
      cursor.close()
  ```
- Startup initialization: `PRAGMA foreign_keys = ON;` is executed before `create_all`.

---

## 3. Backward Compatibility with Phases 1–8

### 3.1 Non-Destructive Association with Existing Entities
The Phase 9 `Composition` table references existing `projects` and `videos` tables:
- `project_id`: Foreign key referencing `projects.id` with `ON DELETE CASCADE`. If a user deletes a project in ClipForge AI, all associated compositions, version histories, and renders are cleanly purged.
- `source_video_id`: Foreign key referencing `videos.id` with `ON DELETE SET NULL`. If a source video file record is removed or unlinked, the composition specification remains intact for inspection or re-linking to an updated asset.

### 3.2 Legacy Clip Compatibility
Phase 7 and Phase 8 produced clips using direct FFmpeg commands and metadata in `clips` and `exported_clips`.
Phase 9 introduces `CompositionSpec` as the modern engine for Phase 9 Stages 3–10. Legacy clips remain queryable and playable in the UI, and future migrations can synthesize a `CompositionSpec` v1.0.0 from legacy clip parameters if needed.

---

## 4. Rollback and Recovery Plan

Because `composition_versions` is strictly append-only:
- Every mutation to a composition creates a new version record.
- If an erroneous edit is made or a bug occurs in an upstream service, the user can immediately invoke the restore endpoint:
  ```http
  POST /api/compositions/{id}/versions/{version_number}/restore
  ```
  This creates a new version containing the historical spec, enabling instant rollback without data loss or transaction rollbacks.
